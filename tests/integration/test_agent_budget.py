"""Frozen root/PG one-time handoff, actual transactions and fake provider accounting."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from threading import Event

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege, RestrictViolation

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.bootstrap.agent_budget import persist_agent_budget, restore_agent_budget
from medops.core.money import usd_to_microusd
from medops.domain.agent_execution import AgentBudget
from medops.infrastructure.db.agent_control import PgAgentControl
from medops.infrastructure.llm.execution_budget import (
    BudgetProtection,
    ExecutionBudgetExceeded,
    execution_scope,
    finalization_scope,
)
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.agent_control import control_data
from tests.support.model_gateway import _FixedCost, req
from tests.support.pv_tools import parent


@pytest.fixture
def case(db):
    db, run, binding = control_data(db)

    def connection():
        return psycopg.connect(db["users"]["app"])

    with connection() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        control = PgAgentControl(conn, run.context, database_binding=binding)
        control.create(run)
        lease = control.claim(30)
    return dict(db=db, run=run, binding=binding, connection=connection, lease=lease)


def updated(run, budget):
    s = budget.snapshot()
    return run.model_copy(
        update={
            "budget": AgentBudget(
                accounted_tokens=s.accounted_tokens,
                reserved_tokens=s.reserved_tokens,
                accounted_cost_microusd=usd_to_microusd(s.accounted_cost_usd),
                reserved_cost_microusd=usd_to_microusd(s.reserved_cost_usd),
            )
        }
    )


def save(case, **kw):
    return persist_agent_budget(
        case["connection"],
        run=case["run"],
        lease=case["lease"],
        expected_revision=kw.get("revision", 0),
        database_binding=case["binding"],
    )


def restore(case, **kw):
    return restore_agent_budget(
        kw.get("connection", case["connection"]),
        run=kw.get("run", case["run"]),
        lease=kw.get("lease", case["lease"]),
        expected_revision=kw.get("revision", 1),
        database_binding=case["binding"],
    )


def checkpoint(case, *, timeout=10):
    with parent(timeout_s=timeout) as budget:
        budget.protect_remaining(BudgetProtection(tokens=1000, cost_usd=0.05))
        MeteredGateway(_FixedCost(0.001)).complete(req())
        case["run"] = updated(case["run"], budget)
        record = save(case)
    return budget, record


def test_actual_root_recovers_once_with_cost_floor_and_decreasing_deadline(case):
    old, record = checkpoint(case)
    time.sleep(0.03)
    restored = restore(case)
    assert restored.budget.snapshot() == old.snapshot()
    assert restored.budget.remaining_timeout(100) < record.state.remaining_timeout_s
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case)
    with execution_scope(restored.budget.limits, budget=restored.budget):
        MeteredGateway(_FixedCost(0.001)).complete(req())
        case["run"] = updated(case["run"], restored.budget)
        next_record = save(case, revision=1)
    assert next_record.revision == 2 and next_record.expires_at <= record.expires_at
    next_root = restore(case, revision=2).budget
    assert next_root.snapshot().accounted_tokens == 30 and next_root.snapshot().accounted_cost_usd == pytest.approx(
        0.002
    )
    assert next_root.protection() == old.protection()
    with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
        old.check()


def test_two_workers_cannot_claim_the_same_checkpoint(case):
    checkpoint(case)

    def consume(_):
        try:
            return restore(case)
        except AgentLoopAbort as exc:
            return exc.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert sum(r == "unsupported_recovery" for r in results) == 1
    assert sum(hasattr(r, "budget") for r in results) == 1


def test_expired_lease_new_generation_can_take_unconsumed_checkpoint_without_reset(case):
    old, _ = checkpoint(case)
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        conn.execute(
            "update agent_run_control set lease_until=clock_timestamp()-interval '1 second' where run_id=%s",
            (case["lease"].run_id,),
        )
        new = PgAgentControl(conn, case["run"].context, database_binding=case["binding"]).claim(30)
    with pytest.raises(AgentLoopAbort, match="lease_lost"):
        restore(case)
    recovered = restore(case, lease=new)
    assert recovered.budget.snapshot() == old.snapshot() and recovered.revision == 1


def test_cancelled_run_cannot_recover(case):
    old, _ = checkpoint(case)
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        PgAgentControl(conn, case["run"].context, database_binding=case["binding"]).cancel()
    with pytest.raises(AgentLoopAbort, match="cancelled"):
        restore(case)
    assert old.snapshot().accounted_cost_usd == 0.001


def test_missing_checkpoint_is_never_a_zero_budget_fallback(case):
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case)


@pytest.mark.parametrize("outcome", ["rollback", "committed"])
def test_no_engine_returned_when_claim_commit_is_failed_or_uncertain(case, outcome):
    checkpoint(case)

    @contextmanager
    def broken():
        with case["connection"]() as conn:
            yield conn
            if outcome == "rollback":
                conn.rollback()
            else:
                conn.commit()
            raise RuntimeError("PUBLIC lost commit acknowledgement")

    with pytest.raises(RuntimeError):
        restore(case, connection=broken)
    if outcome == "rollback":
        assert restore(case).budget.snapshot().accounted_tokens == 15
    else:
        with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
            restore(case)


def test_persistence_failure_permanently_stops_original_budget_and_keeps_fee(case):
    def unavailable():
        raise RuntimeError("PUBLIC unavailable")

    with parent() as budget:
        MeteredGateway(_FixedCost(0.001)).complete(req())
        case["run"] = updated(case["run"], budget)
        with pytest.raises(RuntimeError):
            persist_agent_budget(
                unavailable, run=case["run"], lease=case["lease"], expected_revision=0, database_binding=case["binding"]
            )
        with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
            budget.check()
        assert budget.snapshot().accounted_cost_usd == 0.001
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case)


def test_mismatching_run_budget_does_not_consume_recovery_right(case):
    checkpoint(case)
    wrong = case["run"].model_copy(update={"budget": case["run"].budget.model_copy(update={"accounted_tokens": 0})})
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case, run=wrong)
    assert restore(case).budget.snapshot().accounted_tokens == 15


def test_downtime_consumes_original_budget_deadline(case):
    checkpoint(case, timeout=1.0)
    time.sleep(1.05)
    with pytest.raises(AgentLoopAbort, match="timeout"):
        restore(case)


def test_recovery_in_a_new_python_process_uses_persistent_image_and_consumes_it(case):
    checkpoint(case)
    script = """
import json,os,sys,psycopg
from medops.bootstrap.agent_budget import restore_agent_budget
from medops.domain.agent_execution import PVAgentRun
from medops.infrastructure.db.agent_control import AgentLease
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
p=json.load(sys.stdin)
r=restore_agent_budget(lambda:psycopg.connect(os.environ['MEDOPS_RECOVERY_TEST_DSN']),
 run=PVAgentRun.model_validate(p['run']),lease=AgentLease.model_validate(p['lease']),expected_revision=1,
 database_binding=FactDatabaseBinding.model_validate(p['binding']))
print(r.budget.snapshot().model_dump_json())
"""
    payload = json.dumps(
        dict(
            run=case["run"].model_dump(mode="json"),
            lease=case["lease"].model_dump(mode="json"),
            binding=case["binding"].model_dump(mode="json"),
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
        env=dict(os.environ, MEDOPS_RECOVERY_TEST_DSN=case["db"]["users"]["app"]),
    )
    snapshot = json.loads(result.stdout)
    assert snapshot["accounted_tokens"] == 15 and snapshot["accounted_cost_usd"] == 0.001
    assert snapshot["protected_tokens"] == 1000 and snapshot["protected_cost_usd"] == 0.05
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case)


def test_existing_parent_cannot_be_replaced_and_claim_remains_unconsumed(case):
    checkpoint(case)
    with parent():
        with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
            restore(case)
    assert restore(case).budget.snapshot().accounted_tokens == 15


def test_a_new_empty_root_cannot_erase_checkpointed_spending(case):
    checkpoint(case)
    restore(case)
    with parent() as empty:
        case["run"] = updated(case["run"], empty)
        with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
            save(case, revision=1)
        with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
            empty.check()


def test_step_mismatch_cannot_consume_checkpoint(case):
    checkpoint(case)
    wrong = case["run"].model_copy(update={"decisions_consumed": 1})
    with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
        restore(case, run=wrong)
    assert restore(case).budget.snapshot().accounted_tokens == 15


@pytest.mark.parametrize("role", ["readonly", "restricted", "loop", "admin"])
def test_new_table_grants_are_minimal_and_department_rls_is_forced(case, role):
    checkpoint(case)
    with psycopg.connect(case["db"]["users"][role]) as conn:
        if role == "admin":
            assert (
                conn.execute(
                    "select count(*) from agent_budget_handoffs where run_id=%s", (case["lease"].run_id,)
                ).fetchone()[0]
                == 1
            )
            with pytest.raises(InsufficientPrivilege):
                conn.execute("update agent_budget_handoffs set revision=revision+1")
        else:
            with pytest.raises(InsufficientPrivilege):
                conn.execute("select * from agent_budget_handoffs")
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','MA',true)")
        assert conn.execute("select count(*) from agent_budget_handoffs").fetchone()[0] == 0


def test_database_prevents_resetting_a_claim_or_extending_revision_deadline(case):
    checkpoint(case)
    restore(case)
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        with pytest.raises(RestrictViolation):
            conn.execute(
                "update agent_budget_handoffs set claimed_lease=null,claimed_generation=null where run_id=%s",
                (case["lease"].run_id,),
            )


def test_inflight_reservation_is_persistent_and_quarantined_after_late_response(case):
    entered, release = Event(), Event()

    class Provider(_FixedCost):
        def complete(self, request):
            entered.set()
            assert release.wait(5)
            return super().complete(request)

    meter = MeteredGateway(Provider(0.001))
    with parent() as budget, ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(copy_context().run, meter.complete, req())
        assert entered.wait(2)
        case["run"] = updated(case["run"], budget)
        record = save(case)
        release.set()
        with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
            task.result(timeout=3)
        assert budget.snapshot().accounted_cost_usd == 0.001
    restored = restore(case).budget
    assert restored.snapshot().reserved_tokens == record.state.snapshot.reserved_tokens > 0
    assert restored.snapshot().reserved_cost_usd == record.state.snapshot.reserved_cost_usd > 0
    with pytest.raises(ExecutionBudgetExceeded, match="recovery_inflight"):
        restored.check()


def test_final_slots_remain_sealed_after_postgresql_handoff(case):
    request = req()
    with parent() as budget:
        budget.protect_remaining(BudgetProtection(tokens=1000, cost_usd=0.05))
        with finalization_scope((request,) * 2):
            MeteredGateway(_FixedCost(0.00001)).complete(request)
        case["run"] = updated(case["run"], budget)
        record = save(case)
    restored = restore(case).budget
    final = restored.finalization_snapshot()
    assert final.state == "closed" and final.admitted_calls == 1 and final.profile == record.state.final_phase.profile
    provider = _FixedCost(0.00001)
    with execution_scope(restored.limits, budget=restored):
        with pytest.raises(ExecutionBudgetExceeded, match="finalization_sealed"):
            MeteredGateway(provider).complete(request)
    assert provider.calls == 0 and restored.snapshot().accounted_cost_usd == 0.00001
