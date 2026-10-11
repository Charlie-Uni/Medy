"""PgTaskStore on migration 0010 under the application LOGIN user: idempotent creation (same key wins once, a
concurrent duplicate raises IdempotencyRace and leaves the transaction usable), atomic claims with leases,
late reports from a worker that lost its lease are ignored, attempts are recorded, exhausted tasks fail closed,
and the read-only role has no access."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege

from medops.application.contracts import TaskStatus
from medops.application.tasks import IdempotencyRace, TaskRecord
from medops.domain.common import Dept
from medops.infrastructure.db.tasks import PgTaskStore
from tests.integration.lexical_adapter_suite import make_database

NOW = datetime(
    2026, 9, 23, 12, 0, tzinfo=UTC
)  # fixed for stored timestamps; idempotency expiry is relative to the DB clock (expires_at > now())
PRINCIPAL = "0123456789abcdef" * 2  # pseudonyms are hex (migration 0010 check)


@pytest.fixture
def db(admin_dsn: str) -> Iterator[dict]:
    """One fresh database per test: tasks are never deleted, so leftovers would be claimable by the next test."""
    yield from make_database(admin_dsn)


def record(task_id: str, text: str = "hi", max_attempts: int = 3) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        principal=PRINCIPAL,
        dept=Dept.PV,
        skill_name="echo_skill",
        skill_version="1.0.0",
        input={"text": text},
        status=TaskStatus.queued,
        created_at=NOW,
        updated_at=NOW,
        max_attempts=max_attempts,
    )


def test_idempotent_create_and_race(db):
    import uuid

    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTaskStore(conn)
        store.create(record(t1), ("POST /v1/tasks", "key-1", datetime.now(UTC) + timedelta(days=1)))
        conn.commit()
        found = store.find_idempotent(PRINCIPAL, "POST /v1/tasks", "key-1")
        assert found is not None and found[1] == t1 and len(found[0]) == 64
        with pytest.raises(IdempotencyRace):
            store.create(record(t2), ("POST /v1/tasks", "key-1", datetime.now(UTC) + timedelta(days=1)))
        # the outer transaction survived the losing insert (savepoint)
        assert store.get(t1) is not None and store.get(t2) is None
        conn.commit()
        assert (
            store.find_idempotent("fedcba9876543210" * 2, "POST /v1/tasks", "key-1") is None
        )  # other principal, other scope


def test_claim_lease_finish_and_lost_report(db):
    import uuid

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as a, psycopg.connect(db["users"]["app"]) as b:
        sa, sb = PgTaskStore(a), PgTaskStore(b)
        sa.create(record(tid), None)
        a.commit()
        claimed = sa.claim_next("w1", 60, NOW)
        a.commit()
        assert claimed is not None and claimed.task_id == tid and claimed.attempts == 1 and claimed.lease_owner == "w1"
        assert sb.claim_next("w2", 60, NOW) is None  # leased
        b.rollback()
        reclaimed = sb.claim_next("w2", 60, NOW + timedelta(seconds=61))
        b.commit()
        assert reclaimed is not None and reclaimed.attempts == 2 and reclaimed.lease_owner == "w2"
        assert sa.complete(tid, "w1", 1, "a" * 32, {"x": 1}, NOW + timedelta(seconds=62)) is False  # w1 lost the lease
        a.rollback()
        assert sb.complete(tid, "w2", 2, "b" * 32, {"skill": "echo_skill@1.0.0"}, NOW + timedelta(seconds=70)) is True
        b.commit()
        final = sa.get(tid)
        assert final is not None and final.status is TaskStatus.completed and final.trace_id == "b" * 32
        rows = a.execute(
            "select attempt, worker, outcome from task_attempts where task_id = %s order by attempt", (tid,)
        ).fetchall()
        assert rows == [(1, "w1", "lost"), (2, "w2", "completed")]


def test_exhausted_tasks_fail_closed_and_requeue_only_from_failed(db):
    import uuid

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTaskStore(conn)
        store.create(record(tid, max_attempts=1), None)
        conn.commit()
        assert store.claim_next("w1", 10, NOW) is not None
        conn.commit()
        assert store.claim_next("w2", 10, NOW + timedelta(seconds=11)) is None  # lease expired, attempts exhausted
        conn.commit()
        failed = store.get(tid)
        assert failed is not None and failed.status is TaskStatus.failed and failed.error["retryable"] is False
        assert store.requeue(tid, NOW) is not None and store.get(tid).status is TaskStatus.queued
        assert store.requeue(tid, NOW) is None  # not failed any more
        conn.rollback()


def test_read_only_role_has_no_access(db):
    with psycopg.connect(db["users"]["readonly"]) as ro:
        for table in ("tasks", "task_attempts", "idempotency_keys"):
            with pytest.raises(InsufficientPrivilege):
                ro.execute(f"select count(*) from {table}")  # noqa: S608 - fixed table names
            ro.rollback()


def test_expired_unclaimed_lease_refuses_finish_and_records_only_old_attempt(db):
    import uuid

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTaskStore(conn)
        store.create(record(tid), None)
        conn.commit()
        store.claim_next("same-worker", 10, NOW)
        conn.commit()
        assert store.owns_lease(tid, "same-worker", 1, NOW)
        assert not store.record_lost(tid, "same-worker", 1, "a" * 32, NOW)
        expired = NOW + timedelta(seconds=10)
        assert not store.owns_lease(tid, "same-worker", 1, expired)
        assert not store.complete(tid, "same-worker", 1, "a" * 32, {}, expired)
        assert not store.fail(tid, "same-worker", 1, "a" * 32, {"code": "forbidden"}, expired)
        assert store.record_lost(tid, "same-worker", 1, "a" * 32, expired)
        conn.commit()
        assert store.claim_next("same-worker", 60, expired).attempts == 2
        conn.commit()
        assert not store.record_lost(tid, "impostor", 1, "b" * 32, expired)
        assert not store.record_lost(tid, "same-worker", 1, "b" * 32, expired)
        assert store.record_lost(tid, "same-worker", 1, "a" * 32, expired + timedelta(seconds=1))
        assert store.owns_lease(tid, "same-worker", 2, expired)
        assert store.complete(tid, "same-worker", 2, "b" * 32, {}, expired)
        conn.commit()
        rows = conn.execute(
            "select attempt, outcome, trace_id, finished_at from task_attempts where task_id=%s order by attempt",
            (tid,),
        ).fetchall()
        assert rows == [(1, "lost", "a" * 32, expired), (2, "completed", "b" * 32, expired)]


def test_polling_skips_locked_expired_task_without_marking_its_attempt(db):
    import uuid

    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as a, psycopg.connect(db["users"]["app"]) as b:
        sa, sb = PgTaskStore(a), PgTaskStore(b)
        sa.create(record(t1), None)
        a.commit()
        sa.claim_next("w1", 10, NOW)
        a.commit()
        sa.create(record(t2), None)
        a.commit()
        a.execute("select task_id from tasks where task_id=%s for update", (t1,))
        b.execute("set local statement_timeout = '500ms'")
        claimed = sb.claim_next("w2", 60, NOW + timedelta(seconds=11))
        assert claimed.task_id == t2
        assert b.execute("select outcome from task_attempts where task_id=%s", (t1,)).fetchone() == ("running",)
        b.commit()
        a.rollback()
        assert sb.claim_next("w3", 60, NOW + timedelta(seconds=11)).task_id == t1


def test_finish_rechecks_database_clock_after_waiting_for_row_lock(db):
    import time
    import uuid
    from concurrent.futures import ThreadPoolExecutor

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as a, psycopg.connect(db["users"]["app"]) as b:
        sa, sb = PgTaskStore(a), PgTaskStore(b)
        sa.create(record(tid), None)
        a.commit()
        claimed = sa.claim_next("w1", 0.5)  # real database clock, not worker-supplied test time
        a.commit()
        assert sa.owns_lease(tid, "w1", 1)
        a.execute("select task_id from tasks where task_id=%s for update", (tid,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(sb.complete, tid, "w1", 1, "a" * 32, {})
            try:
                until = time.monotonic() + 2
                waiting = False
                while time.monotonic() < until:
                    a.execute("select pg_stat_clear_snapshot()")
                    row = a.execute(
                        "select wait_event_type from pg_stat_activity where pid=%s", (b.info.backend_pid,)
                    ).fetchone()
                    if row and row[0] == "Lock":
                        waiting = True
                        break
                    time.sleep(0.005)
                assert waiting
                seconds = max(0, (claimed.lease_until - datetime.now(UTC)).total_seconds()) + 0.05
                a.execute("select pg_sleep(%s)", (seconds,))
            finally:
                a.rollback()
            assert pending.result(timeout=5) is False
        b.rollback()
        assert sa.get(tid).status is TaskStatus.running and not sa.owns_lease(tid, "w1", 1)


@pytest.mark.parametrize("unknown_first_response", [False, True])
def test_two_real_workers_keep_lost_costs_and_new_result_separate(db, unknown_first_response):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event

    from medops.application.tasks import TaskRunner, TaskService
    from medops.core.errors import MedOpsError
    from medops.domain.skill import SkillStatus
    from medops.infrastructure.db.audit import PgTraceStore
    from medops.infrastructure.llm.budget import BudgetedGateway, PostgresSpendLedger
    from medops.infrastructure.llm.gateway import OPENAI_PRICES, ModelTimeout, PriceTable
    from tests.unit.application.test_task_lease import PaidFakeEnv
    from tests.unit.application.test_tasks import EchoOut, registry, req, user
    from tests.unit.infrastructure.test_llm_gateway import _FixedCost
    from tests.unit.infrastructure.test_llm_gateway import req as model_request

    entered, release = Event(), Event()
    u = user(uid=PRINCIPAL)
    ledger = PostgresSpendLedger(db["users"]["app"])

    class Provider(_FixedCost):
        def complete(self, request):
            if self.calls == 0 and unknown_first_response:
                self.calls += 1
                raise ModelTimeout()
            return super().complete(request)

    provider = Provider(0.00001)
    gateway = BudgetedGateway(
        provider, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=10, require_execution_budget=True
    )

    def handler(ctx, inp):
        try:
            ctx.deps.gateway.complete(model_request())
        except ModelTimeout:
            pass  # unknown billed usage remains reserved and recorded for this attempt
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
            with pytest.raises(MedOpsError):
                ctx.deps.gateway.complete(model_request())
        return EchoOut(status=SkillStatus.completed, text=ctx.trace_id)

    reg = registry(handler)

    class PgEnv(PaidFakeEnv):
        @contextmanager
        def connection(self):
            with psycopg.connect(db["users"]["app"], options="-c statement_timeout=3000") as conn:
                yield conn

        def task_store(self, conn):
            return PgTaskStore(conn)

        def trace_store(self, conn):
            return PgTraceStore(conn)

    env = PgEnv(None, reg, {u.user_id: u}, gateway)
    with env.connection() as conn:
        task = TaskService(store=PgTaskStore(conn)).create(u, req(), None)
    a = TaskRunner(env=env, registry=reg, worker_id="w1", lease_s=0.3)
    b = TaskRunner(env=env, registry=reg, worker_id="w2", lease_s=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(a.run_once)
        try:
            assert entered.wait(5)
            assert b.run_once() is None
            with env.connection() as conn:
                lease_until = PgTaskStore(conn).get(task.task_id).lease_until
                seconds = max(0, (lease_until - datetime.now(UTC)).total_seconds()) + 0.02
                conn.execute("select pg_sleep(%s)", (seconds,))
            replacement = b.run_once()
        finally:
            release.set()
        stale = pending.result(timeout=5)
    assert stale.outcome == "lost" and stale.attempt == 1 and stale.record is None
    assert replacement.outcome == "completed" and replacement.attempt == 2
    assert provider.calls == 2
    with env.connection() as conn:
        current = PgTaskStore(conn).get(task.task_id)
        assert current.trace_id == replacement.trace_id and current.result["output"]["text"] == replacement.trace_id
        attempts = conn.execute(
            "select attempt, outcome, trace_id from task_attempts where task_id=%s order by attempt", (task.task_id,)
        ).fetchall()
        assert attempts == [(1, "lost", stale.trace_id), (2, "completed", replacement.trace_id)]
        traces = conn.execute(
            "select trace_id, model_calls, cost_usd, outcome from traces where task_id=%s", (task.task_id,)
        ).fetchall()
        assert len(traces) == 2 and sum(t[1] for t in traces) == 2
        assert sum(float(t[2]) for t in traces) == pytest.approx(
            ledger.month_total(datetime.now(UTC).strftime("%Y-%m")), abs=0.000001
        )
    with psycopg.connect(db["owner"]) as admin:
        receipts = admin.execute(
            "select call_context,call_receipt from llm_spend_reservations where call_context->>'trace_id' = any(%s)",
            ([stale.trace_id, replacement.trace_id],),
        ).fetchall()
        assert len(receipts) == 2
        assert all(r[0]["attempt_id"].startswith(f"task:{task.task_id}:") for r in receipts)
        old_receipt = next(r[1] for r in receipts if r[0]["trace_id"] == stale.trace_id)
        assert old_receipt["cost_basis"] == ("conservative_reservation" if unknown_first_response else "reported_usage")
        assert old_receipt["accounted_cost_usd"] > 0 and old_receipt["settlement_status"] == "settled"
