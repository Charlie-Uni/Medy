"""Actual durable driver, fake providers and PUBLIC PG evidence; no hosted calls."""

import json
import os
import subprocess
import sys
import time

import psycopg
import pytest

from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.agent_runtime import runtime_case
from tests.support.pv_agent import proposal
from tests.support.pv_loop import terminal
from tests.support.pv_review import material_verdict


def crash(case, mode):
    env = dict(os.environ, MEDOPS_TEST_AGENT_APP_URL=case["db"]["users"]["app"], PYTHONPATH=os.pathsep.join(sys.path))
    body = json.dumps(
        {
            "run": case["run"].model_dump(mode="json"),
            "binding": case["binding"].model_dump(mode="json"),
            "chunk": case["chunk"],
            "mode": mode,
        }
    ).encode()
    result = subprocess.run(
        [sys.executable, "-m", "tests.support.agent_crash"], input=body, capture_output=True, env=env, timeout=20
    )
    assert result.returncode == 83, result.stderr.decode()
    time.sleep(3.1)


@pytest.mark.parametrize("mode,parent_calls", [("decision", 2), ("planning_receipt", 1), ("tool_commit", 1)])
def test_process_death_recovers_same_decision_or_committed_result_without_repeating_calls(db, mode, parent_calls):
    fake = FakeModelGateway({"agent_plan": [proposal(), terminal()] if mode == "decision" else [terminal()]})
    case = runtime_case(db, fake)
    crash(case, mode)
    with case["runtime"].recover(case["context"]) as execution:
        before = execution.driver.root.snapshot()
        result = execution.run()
        assert result.reason == "completed" and result.run.decisions_consumed == 2
        assert len(result.outcomes) == 1 and len(result.evidence_registry) == 1
        assert execution.driver.root.snapshot().accounted_tokens >= before.accounted_tokens
        assert execution.driver.root.remaining_timeout(125) < 124
        assert result.run.started_at == case["run"].started_at and result.run.expires_at == case["run"].expires_at
        with case["connection"]() as conn:
            conn.execute("select set_config('medops.dept','PV',true)")
            events = execution.driver._store(conn).events()
            assert len([e for e in events if e.kind == "tool_committed"]) == 1
    assert len(fake.calls) == parent_calls


def test_unknown_inflight_call_is_preserved_and_never_resent(db):
    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    crash(case, "inflight")
    with case["runtime"].recover(case["context"]) as execution:
        reserved = execution.driver.root.snapshot()
        assert reserved.reserved_tokens > 0 and reserved.reserved_cost_usd > 0
        result = execution.run()
        assert result.reason == "unsupported_recovery" and not fake.calls
        assert result.run.budget.reserved_tokens == reserved.reserved_tokens
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        head = execution.driver._store(conn).read()
        assert head.budget.pending and head.body.loop.phase == "handoff"
        assert head.body.loop.stop_reason == "unsupported_recovery"


def test_real_runtime_commits_before_provider_and_stores_complete_handoff(db):
    fake = FakeModelGateway({"agent_plan": [proposal(), terminal()]})
    case = runtime_case(db, fake)
    original = fake.complete

    def complete(request):
        assert getattr(case["open"], "count", 0) == 0
        with psycopg.connect(db["owner"]) as conn:
            row = conn.execute(
                "select budget_state from agent_runtime_heads where run_id=%s", (case["run"].context.identity.run_id,)
            ).fetchone()
            assert row is not None
            assert request.call.call_id in {p["call_id"] for p in row[0]["pending"]}
            assert (
                conn.execute(
                    "select count(*) from agent_runtime_events where run_id=%s and kind='call_admitted' and item_id=%s",
                    (case["run"].context.identity.run_id, request.call.call_id),
                ).fetchone()[0]
                == 1
            )
        return original(request)

    fake.complete = complete
    with case["runtime"].start(case["run"]) as execution:
        result = execution.run()
        assert result.reason == "completed" and result.run.decisions_consumed == 2
        assert result.run.terminal is None and result.run.status == "running"
        assert len(result.evidence_registry) == 1
        assert execution.driver.head.body.loop.phase == "handoff"
        assert execution.driver.head.body.loop.history[0].outcome == result.outcomes[0]
    assert len(fake.calls) == 2
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        store = execution.driver._store(conn)
        head = store.read()
        assert head.body.run.budget == result.run.budget
        assert len(store.calls()) == 2
        assert len([e for e in store.events() if e.kind == "tool_committed"]) == 1


@pytest.mark.parametrize("mutation", ["cancel", "revoke", "version", "archive", "acl", "content"])
def test_drift_or_cancel_after_provider_retains_fee_but_cannot_continue(db, mutation):
    fake = FakeModelGateway({"agent_plan": [proposal(), terminal()]})
    case = runtime_case(db, fake)
    original = fake.complete

    def complete(request):
        response = original(request)
        with psycopg.connect(db["owner"]) as conn:
            if mutation == "cancel":
                conn.execute(
                    "update agent_run_control set cancelled_at=clock_timestamp() where run_id=%s",
                    (case["context"].identity.run_id,),
                )
            elif mutation == "revoke":
                conn.execute(
                    "update principals set active=false where sub_pseudonym=%s", (case["context"].principal.user_id,)
                )
            elif mutation == "version":
                case["bindings_valid"] = False
            elif mutation == "archive":
                conn.execute("select set_config('medops.actor','PUBLIC-test',true)")
                conn.execute("update documents set status='archived' where doc_id=%s", (case["doc"],))
            elif mutation == "acl":
                conn.execute("delete from document_acl where doc_id=%s", (case["doc"],))
        return response

    fake.complete = complete
    with case["runtime"].start(case["run"]) as execution:
        if mutation == "content":
            execute = execution.driver.execute_tool

            def changed(*args, **kwargs):
                outcome = execute(*args, **kwargs)
                with psycopg.connect(db["owner"]) as conn:
                    # Privileged corruption fixture: normal chunk writes are immutable.
                    conn.execute("alter table chunks disable trigger user")
                    conn.execute(
                        "update chunks set content='PUBLIC changed content' where chunk_id=%s", (case["chunk"],)
                    )
                    conn.execute("alter table chunks enable trigger user")
                return outcome

            execution.driver.execute_tool = changed
        result = execution.run()
        assert result.reason != "completed" and len(fake.calls) == 1
        assert result.run.decisions_consumed == 1
        assert execution.driver.root.snapshot().calls == 1
        with case["connection"]() as conn:
            conn.execute("select set_config('medops.dept','PV',true)")
            calls = execution.driver._store(conn).calls()
            assert len(calls) == 1 and calls[0].receipt.usage.total_tokens > 0


def test_heartbeat_keeps_lease_and_closed_root_cannot_restart(db):
    from medops.infrastructure.llm.execution_budget import ExecutionBudgetExceeded

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake, lease_s=2)
    original = fake.complete

    def complete(request):
        time.sleep(2.5)
        with case["connection"]() as conn:
            control = case["runtime"]._control(conn, case["context"])
            with pytest.raises(Exception, match="lease"):
                control.claim(2)
        return original(request)

    fake.complete = complete
    with case["runtime"].start(case["run"]) as execution:
        root = execution.driver.root
        assert execution.run().reason == "completed"
    assert not execution.heartbeat.thread.is_alive()
    with pytest.raises(ExecutionBudgetExceeded):
        root.check()
    with case["runtime"].recover(case["context"]) as recovered:
        assert recovered.run().reason == "completed"
    assert len(fake.calls) == 1


def test_changed_versions_on_recovery_never_yield_engine(db):
    from medops.application.agent_loop_ports import AgentLoopAbort

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
    case["bindings_valid"] = False
    with pytest.raises(AgentLoopAbort):
        with case["runtime"].recover(case["context"]):
            pytest.fail("must not yield a recovered engine")
    assert len(fake.calls) == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_admission_commit_failure_never_calls_provider_or_resets_uncertain_reservation(db, after_commit):
    from contextlib import contextmanager

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    with case["runtime"].start(case["run"]) as execution:
        driver = execution.driver
        connection, save = driver.connection, driver._save
        fault = {"saves": 0, "armed": False}

        @contextmanager
        def unreliable():
            with connection() as conn:
                yield conn
                if fault["armed"]:
                    fault["armed"] = False
                    if after_commit:
                        conn.commit()  # commit succeeded but its acknowledgement was lost
                    raise RuntimeError("PUBLIC injected commit acknowledgement failure")

        def arm(store, body):
            head = save(store, body)
            fault["saves"] += 1
            if fault["saves"] == 2:  # decision committed; next save is write-ahead admission
                fault["armed"] = True
            return head

        driver.connection, driver._save = unreliable, arm
        result = execution.run()
        assert result.reason != "completed" and not fake.calls
    with case["runtime"].recover(case["context"]) as recovered:
        snapshot = recovered.driver.root.snapshot()
        result = recovered.run()
        if after_commit:
            assert snapshot.reserved_tokens > 0 and result.reason == "unsupported_recovery" and not fake.calls
        else:
            assert snapshot.reserved_tokens == 0 and result.reason == "completed" and len(fake.calls) == 1
        assert result.run.decisions_consumed == 1


def test_late_receipt_after_lease_loss_is_retained_without_advancing_old_head(db):
    from uuid import uuid4

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    original = fake.complete

    def complete(request):
        response = original(request)
        with psycopg.connect(db["owner"]) as conn:
            conn.execute(
                "update agent_run_control set lease_id=%s, lease_generation=lease_generation+1, "
                "lease_until=clock_timestamp() where run_id=%s",
                (uuid4(), case["context"].identity.run_id),
            )
        return response

    fake.complete = complete
    with case["runtime"].start(case["run"]) as execution:
        result = execution.run()
        assert result.reason != "completed" and len(fake.calls) == 1
        with case["connection"]() as conn:
            conn.execute("select set_config('medops.dept','PV',true)")
            store = execution.driver._store(conn)
            head, calls = store.read(), store.calls()
            assert head.budget.pending and head.budget.snapshot.accounted_tokens == 0
            assert calls[0].receipt.usage.total_tokens > 0
    with case["runtime"].recover(case["context"]) as recovered:
        root = recovered.driver.root.snapshot()
        assert not root.reserved_tokens and root.known_tokens > 0 and root.calls == 1
        assert recovered.run().reason == "unsupported_recovery"  # no progress accepted from the old lease
    assert len(fake.calls) == 1


@pytest.mark.parametrize("table", ["agent_runtime_heads", "agent_runtime_events"])
def test_runtime_encryption_and_privileges_fail_closed(db, table):
    from psycopg.errors import InsufficientPrivilege, RestrictViolation

    from medops.application.agent_loop_ports import AgentLoopAbort

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
    with psycopg.connect(db["owner"]) as conn:
        (ciphertext,) = conn.execute(
            f"select ciphertext from {table} where run_id=%s limit 1", (case["context"].identity.run_id,)
        ).fetchone()
        assert b"PUBLIC" not in bytes(ciphertext) and case["context"].narrative.encode() not in bytes(ciphertext)
    for role in ("readonly", "admin"):
        with psycopg.connect(db["users"][role]) as conn, pytest.raises(InsufficientPrivilege):
            conn.execute(f"select * from {table}")
    with case["connection"]() as conn, pytest.raises((InsufficientPrivilege, RestrictViolation)):
        conn.execute("select set_config('medops.dept','PV',true)")
        conn.execute(f"delete from {table} where run_id=%s", (case["context"].identity.run_id,))
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','MA',true)")
        assert conn.execute(f"select count(*) from {table}").fetchone()[0] == 0
    with psycopg.connect(db["owner"]) as conn:
        conn.execute(f"alter table {table} disable trigger user")
        conn.execute(
            f"update {table} set ciphertext=decode('0000','hex') where run_id=%s", (case["context"].identity.run_id,)
        )
        conn.execute(f"alter table {table} enable trigger user")
    with pytest.raises((AgentLoopAbort, ValueError)):
        with case["runtime"].recover(case["context"]):
            pytest.fail("tampered encrypted body must not yield an engine")
    assert len(fake.calls) == 1


def test_derived_final_floor_is_consumed_by_real_durable_final_gate_and_cannot_reopen(db):
    from medops.application.agent_final_gate import FinalGateConfig

    cfg = FinalGateConfig(
        model_id="gpt-6-sol",
        max_output_tokens=128,
        timeout_s=20,
        max_review_user_bytes=1500,
        max_citation_user_bytes=500,
        max_citation_judges=0,
    )
    from tests.support.pv_agent import draft

    finish = terminal()
    finish["proposal"]["draft"] = draft()
    finish["proposal"]["draft"]["guideline_claims"] = []
    fake = FakeModelGateway(
        {
            "agent_plan": [finish],
            "agent_final_material": [
                material_verdict(
                    draft_value=finish["proposal"]["draft"],
                    requirements=[{"requirement_id": "event", "complete": True}],
                )
            ],
        }
    )
    case = runtime_case(db, fake, final_config=cfg, narrative_only=True)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.run()
        assert result.reason == "completed"
        proof = execution.driver.verify_final()
        assert proof.material_check.semantic_supported and proof.material_check.citations_supported
        assert execution.driver.root.finalization_snapshot().state == "closed"
        assert execution.driver.head.budget.final_phase.closed
        assert execution.driver.head.body.run.status == "running"  # terminal publication remains AGENT-05/06
    with case["runtime"].recover(case["context"]) as recovered:
        result = recovered.run()
        assert result.reason == "completed"  # replay the saved finish request only, not business completion
        assert recovered.driver.root.finalization_snapshot().state == "closed"
        from medops.infrastructure.llm.execution_budget import ExecutionBudgetExceeded

        with pytest.raises(ExecutionBudgetExceeded):
            recovered.driver.verify_final()
    assert [r.purpose for r in fake.calls] == ["agent_plan", "agent_final_material"]


def test_no_progress_counter_is_rebuilt_after_actual_process_death(db):
    fake = FakeModelGateway({"agent_plan": [proposal()]})
    case = runtime_case(db, fake)
    crash(case, "tool_commit")
    with case["runtime"].recover(case["context"]) as execution:
        result = execution.run()
        assert result.reason == "no_progress" and result.run.decisions_consumed == 2
        assert len(result.outcomes) == 2
    assert len(fake.calls) == 1  # second observation, never a new 8-step run


def test_stricter_original_budget_deadline_cannot_be_extended_by_recovery(db):
    from medops.application.agent_loop_ports import AgentLoopAbort
    from medops.infrastructure.llm.execution_budget import ExecutionLimits

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake, limits=ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=2))
    with case["runtime"].start(case["run"]) as execution:
        time.sleep(2.1)
    with pytest.raises(AgentLoopAbort, match="timeout"):
        with case["runtime"].recover(case["context"]):
            pytest.fail("an expired original root must not be replaced")
    assert not fake.calls and execution.driver.root.snapshot().calls == 0


def test_original_absolute_deadline_is_cryptographically_bound_even_if_metadata_is_corrupted(db):
    from medops.application.agent_loop_ports import AgentLoopAbort

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
    with psycopg.connect(db["owner"]) as conn:
        conn.execute("alter table agent_runtime_heads disable trigger user")
        conn.execute(
            "update agent_runtime_heads set budget_deadline=budget_deadline+interval '1 second' where run_id=%s",
            (case["context"].identity.run_id,),
        )
        conn.execute("alter table agent_runtime_heads enable trigger user")
    with pytest.raises((AgentLoopAbort, ValueError)):
        with case["runtime"].recover(case["context"]):
            pytest.fail("corrupted absolute deadline must never create an executable root")
    assert len(fake.calls) == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_recovery_does_not_construct_an_executable_root_before_commit_confirmation(db, monkeypatch, after_commit):
    from contextlib import contextmanager

    import medops.bootstrap.agent_execution as owner

    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake, lease_s=3)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
        original_tokens = execution.driver.root.snapshot().accounted_tokens
    runtime = case["runtime"]
    connection, resources, restore = runtime.connection, runtime.resources, owner.restore_consumed_budget
    flags = {"armed": False, "roots": 0}

    @contextmanager
    def unreliable():
        with connection() as conn:
            yield conn
            if flags["armed"]:
                flags["armed"] = False
                if after_commit:
                    conn.commit()
                raise RuntimeError("PUBLIC recovery commit confirmation failure")

    def arm(*args):
        result = resources(*args)
        flags["armed"] = True
        return result

    def count(*args, **kwargs):
        flags["roots"] += 1
        return restore(*args, **kwargs)

    runtime.connection, runtime.resources = unreliable, arm
    monkeypatch.setattr(owner, "restore_consumed_budget", count)
    with pytest.raises(RuntimeError):
        with runtime.recover(case["context"]):
            pytest.fail("an unconfirmed commit cannot yield an engine")
    assert flags["roots"] == 0 and len(fake.calls) == 1
    runtime.connection, runtime.resources = connection, resources
    if after_commit:
        time.sleep(3.1)
    with runtime.recover(case["context"]) as recovered:
        assert recovered.driver.root.snapshot().accounted_tokens == original_tokens
        assert recovered.run().reason == "completed"
    assert flags["roots"] == 1 and len(fake.calls) == 1


def test_cleanup_failure_still_permanently_suspends_the_original_root(db):
    from medops.infrastructure.llm.execution_budget import ExecutionBudgetExceeded

    case = runtime_case(db, FakeModelGateway())
    with pytest.raises(RuntimeError, match="PUBLIC heartbeat cleanup"):
        with case["runtime"].start(case["run"]) as execution:
            root = execution.driver.root
            stop = execution.heartbeat.stop

            def broken_stop():
                stop()
                raise RuntimeError("PUBLIC heartbeat cleanup")

            execution.heartbeat.stop = broken_stop
    with pytest.raises(ExecutionBudgetExceeded):
        root.check()
    assert not execution.heartbeat.thread.is_alive() and root.snapshot().calls == 0
