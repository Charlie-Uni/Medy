"""Real temporary PostgreSQL, separate workers and physical-call guards; zero hosted calls."""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege, RestrictViolation, UniqueViolation

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.bootstrap.agent_control import agent_lease_guard
from medops.core.errors import BusinessError
from medops.infrastructure.db.agent_control import PgAgentControl
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.agent_control import control_data
from tests.support.model_gateway import req
from tests.support.pv_loop import setup_loop, terminal
from tests.support.pv_tools import parent


@pytest.fixture
def data(db):
    return control_data(db)


@contextmanager
def connection(data, *, role="app", dept="PV", context=None):
    db, current, binding = data
    with psycopg.connect(db["users"][role]) as conn:
        conn.execute("select set_config('medops.dept',%s,true)", (dept,))
        yield conn, PgAgentControl(conn, context or current.context, database_binding=binding)


def created(data, lease_s=30):
    with connection(data) as (_, store):
        store.create(data[1])
        return store.claim(lease_s)


def reason(expected, operation):
    with pytest.raises(AgentLoopAbort) as error:
        operation()
    assert error.value.reason == expected


def test_cancel_is_durable_idempotent_and_blocks_every_write_and_reclaim(data):
    lease = created(data)
    with connection(data) as (_, store):
        first = store.cancel()
    with connection(data) as (_, store):
        assert store.cancel() == first
        assert store.get().cancelled_at is not None
        for operation in (
            lambda: store.assert_owned(lease),
            lambda: store.fence(lease),
            lambda: store.renew(lease, 10),
            lambda: store.consume_decision(lease, expected_decisions=0),
            lambda: store.claim(10),
        ):
            reason("cancelled", operation)
        assert store.get().decisions_consumed == 0


def test_cancel_rollback_does_not_report_persistent_cancellation(data):
    lease = created(data)
    with connection(data) as (conn, store):
        store.cancel()
        conn.rollback()
    with connection(data) as (_, store):
        store.assert_owned(lease)
        assert store.get().cancelled_at is None


def test_reclaim_preserves_steps_binding_and_absolute_deadline_and_fences_old_worker(data):
    old = created(data, 0.25)
    with connection(data) as (conn, store):
        assert store.consume_decision(old, expected_decisions=0) == 1
        original = store.get()
        conn.commit()
        conn.execute("select pg_sleep(0.3)")
    with connection(data) as (_, store):
        new = store.claim(125)
        after = store.get()
        assert after.decisions_consumed == 1
        assert (after.started_at, after.expires_at) == (original.started_at, original.expires_at)
        assert after.lease_until == after.expires_at
        assert new.generation == old.generation + 1 and new.lease_id != old.lease_id
        for operation in (
            lambda: store.assert_owned(old),
            lambda: store.renew(old, 10),
            lambda: store.fence(old),
            lambda: store.consume_decision(old, expected_decisions=1),
        ):
            reason("lease_lost", operation)
        assert store.consume_decision(new, expected_decisions=1) == 2
        reason("unsupported_recovery", lambda: store.consume_decision(new, expected_decisions=1))
        assert store.get().decisions_consumed == 2


def test_eight_steps_survive_connections_and_neither_duplicate_nor_ninth_step_is_free(data):
    lease = created(data)
    for expected in range(8):
        with connection(data) as (_, store):
            assert store.consume_decision(lease, expected_decisions=expected) == expected + 1
            reason(
                "unsupported_recovery",
                lambda expected=expected: store.consume_decision(lease, expected_decisions=expected),
            )
    with connection(data) as (_, store):
        reason("step_limit", lambda: store.consume_decision(lease, expected_decisions=8))
        assert store.get().decisions_consumed == 8


def test_live_lease_cannot_be_stolen_and_renewal_cannot_shorten_or_extend_deadline(data):
    lease = created(data, 20)
    with connection(data) as (_, store):
        before = store.get()
        reason("lease_lost", lambda: store.claim(125))
        store.renew(lease, 1)
        assert store.get().lease_until == before.lease_until
        store.renew(lease, 125)
        assert store.get().lease_until == before.expires_at


def test_concurrent_duplicate_decision_is_consumed_once(data):
    lease = created(data)

    def consume():
        with connection(data) as (_, store):
            try:
                return store.consume_decision(lease, expected_decisions=0)
            except AgentLoopAbort as error:
                return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert results.count(1) == results.count("unsupported_recovery") == 1
    with connection(data) as (_, store):
        assert store.get().decisions_consumed == 1


def test_direct_sql_department_rls_and_admin_read_only_grants(data):
    lease = created(data)
    with connection(data, dept="MA") as (conn, _):
        assert conn.execute("select run_id from agent_run_control where run_id=%s", (lease.run_id,)).fetchone() is None
    with connection(data, role="admin") as (conn, _):
        assert (
            conn.execute("select run_id from agent_run_control where run_id=%s", (lease.run_id,)).fetchone()[0]
            == lease.run_id
        )
        with pytest.raises(InsufficientPrivilege):
            conn.execute("update agent_run_control set cancelled_at=clock_timestamp() where run_id=%s", (lease.run_id,))


def test_wrong_startup_database_binding_cannot_claim_existing_control(data):
    lease = created(data)
    with connection(data) as (conn, _):
        wrong_binding = data[2].model_copy(update={"connection_identity": "b" * 64})
        wrong = PgAgentControl(conn, data[1].context, database_binding=wrong_binding)
        reason("version_conflict", lambda: wrong.assert_owned(lease))


@pytest.mark.parametrize("seconds", [True, 0, -1, 126, float("inf"), float("nan")])
def test_invalid_lease_duration_is_rejected_before_state_mutation(data, seconds):
    lease = created(data)
    with connection(data) as (_, store):
        before = store.get()
        with pytest.raises(ValueError, match="invalid_agent_lease"):
            store.renew(lease, seconds)
        with pytest.raises(ValueError, match="invalid_agent_lease"):
            store.claim(seconds)
        assert store.get() == before


def test_duplicate_creation_cannot_reset_cancel_or_steps(data):
    lease = created(data)
    with connection(data) as (_, store):
        store.consume_decision(lease, expected_decisions=0)
        store.cancel()
    with connection(data) as (conn, store):
        with pytest.raises(UniqueViolation), conn.transaction():
            store.create(data[1])
        assert store.get().decisions_consumed == 1 and store.get().cancelled_at is not None


@pytest.mark.parametrize("change", ["principal", "context", "fact_database", "dept"])
def test_context_owner_department_or_fact_plane_change_cannot_read_or_cancel(data, change):
    created(data)
    current = data[1].context
    dept = "PV"
    if change == "principal":
        current = current.model_copy(
            update={"principal": current.principal.model_copy(update={"user_id": uuid4().hex * 2})}
        )
    elif change == "context":
        current = current.model_copy(update={"narrative": current.narrative + " changed"})
    elif change == "fact_database":
        current = current.model_copy(
            update={"versions": current.versions.model_copy(update={"fact_database_id": uuid4()})}
        )
    else:
        dept = "MA"
    with connection(data, dept=dept, context=current) as (_, store):
        with pytest.raises((AgentLoopAbort, BusinessError)):
            store.cancel()
    with connection(data) as (_, store):
        assert store.get().cancelled_at is None


def test_revoked_directory_identity_cannot_renew_or_write(data):
    lease = created(data)
    db, current, binding = data
    with psycopg.connect(db["owner"]) as conn:
        conn.execute("update principals set active=false where sub_pseudonym=%s", (current.context.principal.user_id,))
    with connection(data) as (_, store):
        with pytest.raises(BusinessError):
            store.renew(lease, 125)
    guard = agent_lease_guard(
        lambda: psycopg.connect(db["users"]["app"]), current.context, lease, database_binding=binding
    )
    reason("lease_lost", guard)


@pytest.mark.parametrize("role", ["readonly", "restricted", "loop"])
def test_unrelated_roles_cannot_read_control_metadata(data, role):
    created(data)
    with connection(data, role=role) as (conn, _):
        with pytest.raises(InsufficientPrivilege):
            conn.execute("select * from agent_run_control")


@pytest.mark.parametrize(
    "sql",
    [
        "update agent_run_control set expires_at=expires_at+interval '1 second' where run_id=%s",
        "update agent_run_control set context_sha256=repeat('b',64) where run_id=%s",
        "update agent_run_control set decisions_consumed=0 where run_id=%s",
        "update agent_run_control set decisions_consumed=3 where run_id=%s",
    ],
)
def test_database_rejects_rebinding_or_step_reset_even_from_trusted_application(data, sql):
    lease = created(data)
    with connection(data) as (_, store):
        store.consume_decision(lease, expected_decisions=0)
    with connection(data) as (conn, _):
        with pytest.raises(RestrictViolation):
            conn.execute(sql, (lease.run_id,))


def test_cancel_flag_is_irreversible_even_with_direct_application_sql(data):
    lease = created(data)
    with connection(data) as (_, store):
        store.cancel()
    with connection(data) as (conn, _):
        with pytest.raises(RestrictViolation):
            conn.execute("update agent_run_control set cancelled_at=null where run_id=%s", (lease.run_id,))


def test_fence_rechecks_clock_after_waiting_for_row_lock(data):
    lease = created(data, 0.3)
    entered = Event()

    def stale_writer():
        with connection(data) as (_, store):
            entered.set()
            reason("lease_lost", lambda: store.fence(lease))

    with connection(data) as (conn, _), ThreadPoolExecutor(max_workers=1) as pool:
        conn.execute("select run_id from agent_run_control where run_id=%s for update", (lease.run_id,))
        pending = pool.submit(stale_writer)
        assert entered.wait(2)
        time.sleep(0.4)
        conn.commit()
        pending.result(timeout=3)


def test_commit_fence_serializes_cancellation_with_atomic_audit_write(data):
    lease = created(data)
    entered = Event()

    def cancelling():
        with connection(data) as (_, store):
            entered.set()
            return store.cancel()

    with connection(data) as (conn, store), ThreadPoolExecutor(max_workers=1) as pool:
        store.fence(lease)
        pending = pool.submit(cancelling)
        assert entered.wait(2)
        # Another writer cannot cancel between the fence and this transaction's commit.
        assert not pending.done()
        assert store.consume_decision(lease, expected_decisions=0) == 1
        conn.commit()
        assert pending.result(timeout=3).cancelled_at is not None
    with connection(data) as (_, store):
        assert store.get().decisions_consumed == 1
        reason("cancelled", lambda: store.fence(lease))


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("control", ["cancel", "replace"])
def test_cancel_during_physical_model_call_retains_known_or_unknown_usage_and_stops_loop(data, failure, control):
    db, stored, binding = data
    current, loop, driver, fake, meter = setup_loop({"agent_plan": [terminal("clarify")]})
    context = current.context.model_copy(
        update={
            "identity": stored.context.identity,
            "principal": stored.context.principal,
            "versions": current.context.versions.model_copy(
                update={"fact_database_id": stored.context.versions.fact_database_id}
            ),
        }
    )
    current = current.model_copy(
        update={"context": context, "started_at": stored.started_at, "expires_at": stored.expires_at}
    )
    data = db, current, binding
    lease = created(data)
    driver.context = driver.facts.context = context
    driver.clock = lambda: current.started_at + timedelta(seconds=2)
    original_checkpoint = driver.checkpoint

    def checkpoint(event):
        if event.phase == "decision_started":
            with connection(data) as (_, store):
                store.consume_decision(lease, expected_decisions=event.run.decisions_consumed - 1)
        original_checkpoint(event)

    driver.checkpoint = checkpoint
    physical = fake.complete

    def cancelling_provider(request):
        with connection(data) as (conn, store):
            if control == "cancel":
                store.cancel()
            else:
                # Fault injection: the in-flight worker's lease elapsed while its
                # provider ran. A different worker acquires a real new generation.
                conn.execute(
                    "update agent_run_control set lease_until=clock_timestamp()-interval '1 second' where run_id=%s",
                    (lease.run_id,),
                )
                store.claim(30)
        if failure:
            fake.calls.append(request)
            raise ModelTimeout("PUBLIC unknown provider usage")
        return physical(request).model_copy(update={"cost_usd": 0.0001})

    fake.complete = cancelling_provider
    guard = agent_lease_guard(lambda: psycopg.connect(db["users"]["app"]), context, lease, database_binding=binding)
    with parent() as budget, call_scope(before_call=guard):
        result = loop.run(current)
        snapshot = budget.snapshot()
    assert len(fake.calls) == 1 and len(meter.receipts) == 1 and not driver.actions
    stopped_reason = "cancelled" if control == "cancel" else "lease_lost"
    assert result.reason == ("timeout" if failure else stopped_reason)
    assert result.run.status == "running" and result.run.terminal is None
    assert result.run.decisions_consumed == 1 and snapshot.calls == 1
    assert snapshot.accounted_tokens > 0
    assert snapshot.accounted_cost_usd > 0
    assert meter.receipts[0].provider_started
    assert (meter.receipts[0].usage is None) == failure
    assert (snapshot.known_tokens == 0) == failure
    with connection(data) as (_, store):
        assert store.get().decisions_consumed == 1
        reason(stopped_reason, lambda: store.fence(lease))


def test_cancelled_guard_stops_model_before_first_physical_call_and_closes_connection(data):
    db, current, binding = data
    lease = created(data)
    with connection(data) as (_, store):
        store.cancel()
    connections = []

    def connect():
        conn = psycopg.connect(db["users"]["app"])
        connections.append(conn)
        return conn

    guard = agent_lease_guard(connect, current.context, lease, database_binding=binding)
    provider = FakeModelGateway(default=["PUBLIC reply"])
    meter = MeteredGateway(provider)
    with parent() as budget, call_scope(before_call=guard):
        reason("cancelled", lambda: meter.complete(req()))
    assert not provider.calls and budget.snapshot().calls == 0
    assert len(meter.receipts) == 1 and not meter.receipts[0].provider_started
    assert len(connections) == 1 and connections[0].closed


def test_guard_connection_failure_has_only_fixed_error_code(data):
    lease = created(data)

    def unavailable():
        raise RuntimeError("PRIVATE-CONNECTION-STRING")

    guard = agent_lease_guard(unavailable, data[1].context, lease, database_binding=data[2])
    reason("dependency_error", guard)
