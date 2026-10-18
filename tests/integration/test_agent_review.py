"""Real PG commit/recovery/permission tests for PRIVATE review; no hosted calls."""

from contextlib import contextmanager

import psycopg
import pytest

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_tool_ports import AgentToolFault
from medops.core.errors import BusinessError
from medops.infrastructure.llm.fake import FakeModelGateway, Truncated
from tests.support.agent_runtime import runtime_case
from tests.support.pv_agent import draft
from tests.support.pv_loop import terminal
from tests.support.pv_review import final_config, material_verdict


def case_for(db, *, empty=False, response=None):
    finish = terminal()
    if not empty:
        finish["proposal"]["draft"] = draft()
        finish["proposal"]["draft"]["guideline_claims"] = []
    verdict = material_verdict(
        draft_value=finish["proposal"]["draft"], requirements=[{"requirement_id": "event", "complete": True}]
    )
    fake = FakeModelGateway(
        {"agent_plan": [finish], "agent_final_material": [response if response is not None else verdict]}
    )
    case = runtime_case(
        db, fake, final_config=final_config(max_review_user_bytes=1500, max_citation_judges=0), narrative_only=True
    )
    return case, fake


def events_for(case, execution):
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        return [
            e
            for e in execution.driver._store(conn).events()
            if e.kind == "checkpoint" and e.body.get("kind") in {"final_material_check", "final_review_rejected"}
        ]


@pytest.mark.parametrize("empty", [False, True])
def test_review_is_committed_encrypted_and_reused_after_recovery_without_new_call(db, empty):
    case, fake = case_for(db, empty=empty)
    with case["runtime"].start(case["run"]) as execution:
        handoff = execution.run()
        prepared = execution.review()
        assert prepared.completion_eligible is not empty
        assert handoff.run.status == execution.driver.head.body.run.status == "running"
        assert execution.driver.head.body.run.terminal is None
        assert execution.review() == prepared
        events = events_for(case, execution)
        assert len(events) == 1 and events[0].body["prepared_review"] == prepared.model_dump(mode="json")
        if empty:
            assert prepared.gates.narrative_supported == "not_run" and not prepared.call_receipt_ids
        else:
            assert len(prepared.call_receipt_ids) == 1 and prepared.narrative_facts
        assert execution.driver.root.finalization_snapshot().state == "closed"
    with psycopg.connect(db["owner"]) as conn:
        rows = conn.execute(
            "select ciphertext from agent_runtime_events where run_id=%s", (case["context"].identity.run_id,)
        ).fetchall()
        assert rows and all(case["context"].narrative.encode() not in bytes(r[0]) for r in rows)
    with case["runtime"].recover(case["context"]) as recovered:
        assert recovered.run().reason == "completed"  # saved finish proposal only
        assert recovered.review() == prepared
        assert recovered.driver.head.body.run.terminal is None
        assert len(events_for(case, recovered)) == 1
    assert [r.purpose for r in fake.calls] == (["agent_plan"] if empty else ["agent_plan", "agent_final_material"])


@pytest.mark.parametrize("mutation", ["cancel", "revoke", "version", "archive", "acl"])
def test_drift_after_final_provider_retains_receipt_but_returns_no_review(db, mutation):
    case, fake = case_for(db)
    original = fake.complete

    def changed(request):
        reply = original(request)
        if request.purpose == "agent_final_material":
            with psycopg.connect(db["owner"]) as conn:
                if mutation == "cancel":
                    conn.execute(
                        "update agent_run_control set cancelled_at=clock_timestamp() where run_id=%s",
                        (case["context"].identity.run_id,),
                    )
                elif mutation == "revoke":
                    conn.execute(
                        "update principals set active=false where sub_pseudonym=%s",
                        (case["context"].principal.user_id,),
                    )
                elif mutation == "version":
                    case["bindings_valid"] = False
                elif mutation == "archive":
                    conn.execute("select set_config('medops.actor','PUBLIC-test',true)")
                    conn.execute("update documents set status='archived' where doc_id=%s", (case["doc"],))
                else:
                    conn.execute("delete from document_acl where doc_id=%s", (case["doc"],))
        return reply

    fake.complete = changed
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        with pytest.raises((AgentLoopAbort, AgentToolFault, BusinessError)):
            execution.review()
        assert execution.driver._prepared_review is None and execution.driver.head.body.run.terminal is None
        assert not events_for(case, execution)
    with psycopg.connect(db["owner"]) as conn:
        assert (
            conn.execute(
                "select count(*) from agent_runtime_events where kind='call_settled' and run_id=%s",
                (case["context"].identity.run_id,),
            ).fetchone()[0]
            == 2
        )
    assert len(fake.calls) == 2


@pytest.mark.parametrize(
    "response",
    [{"narrative_supported": True, "complete": True, "scope_safe": True}, Truncated('{"narrative_supported":true')],
)
def test_bad_final_reply_seals_phase_and_cannot_retry_on_recovery(db, response):
    case, fake = case_for(db, response=response)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        with pytest.raises(AgentToolFault):
            execution.review()
        assert not events_for(case, execution)
        assert execution.driver.root.finalization_snapshot().state == "closed"
    with case["runtime"].recover(case["context"]) as recovered:
        recovered.run()
        with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
            recovered.review()
    assert len(fake.calls) == 2


@pytest.mark.parametrize("after_commit", [False, True])
def test_material_commit_failure_never_returns_uncommitted_review_or_repeats_provider(db, after_commit):
    case, fake = case_for(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        driver = execution.driver
        connection, save = driver.connection, driver._save
        armed = {"value": False}

        @contextmanager
        def unreliable():
            with connection() as conn:
                yield conn
                if armed["value"]:
                    armed["value"] = False
                    if after_commit:
                        conn.commit()
                    raise RuntimeError("PUBLIC material commit acknowledgement failure")

        def arm(store, body):
            head = save(store, body)
            if (
                driver.root.finalization_snapshot() is not None
                and driver.root.finalization_snapshot().state == "closed"
            ):
                armed["value"] = True
            return head

        driver.connection, driver._save = unreliable, arm
        with pytest.raises(RuntimeError, match="material commit"):
            execution.review()
        driver.connection, driver._save = connection, save
        assert driver._prepared_review is None
        assert len(events_for(case, execution)) == int(after_commit)
    with case["runtime"].recover(case["context"]) as recovered:
        recovered.run()
        if after_commit:
            assert recovered.review().completion_eligible
        else:
            with pytest.raises(AgentLoopAbort, match="unsupported_recovery"):
                recovered.review()
    assert len(fake.calls) == 2


def test_revoked_identity_cannot_read_cached_review(db):
    case, fake = case_for(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        assert execution.review().completion_eligible
        with psycopg.connect(db["owner"]) as conn:
            conn.execute(
                "update principals set active=false where sub_pseudonym=%s", (case["context"].principal.user_id,)
            )
        with pytest.raises((AgentLoopAbort, AgentToolFault, BusinessError)):
            execution.review()
    assert len(fake.calls) == 2
