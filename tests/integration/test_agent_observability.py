"""Actual PG Agent spans: closed metadata, provenance and recovery; no hosted calls."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from medops.core import telemetry
from medops.core.tracing import bind_trace_id, current_trace_id
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from tests.support.agent_runtime import runtime_case
from tests.support.agent_terminal import retrieval_terminal_case, terminal_case
from tests.support.pv_loop import terminal


@pytest.fixture
def spans():
    previous = telemetry._provider
    exporter = InMemorySpanExporter()
    provider = telemetry.install_exporter(exporter, batch=False)
    try:
        yield exporter
    finally:
        telemetry.set_tracer_provider(previous)
        provider.shutdown()


def roots(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == "agent.execution"]


def test_actual_tools_plan_final_check_and_receipts_form_one_private_body_free_trace(db, spans):
    case, fake = retrieval_terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
    actual = spans.get_finished_spans()
    by_name = {name: [s for s in actual if s.name == name] for name in {s.name for s in actual}}
    (root,) = roots(spans)
    (loop,) = by_name["agent.loop"]
    (tool,) = by_name["agent.tool"]
    (final,) = by_name["agent.terminal"]
    (review,) = by_name["agent.final_review"]
    assert result.run.status == "completed" and len(fake.calls) == 3
    assert loop.parent == final.parent == root.context
    assert tool.parent == loop.context and review.parent == final.context
    assert all(s.parent == loop.context for s in by_name["agent.plan"])
    assert len(by_name["agent.plan"]) == 2 and len(by_name["llm.call"]) == 3
    assert {s.context.trace_id for s in actual} == {int(case["context"].identity.trace_id, 16)}
    assert tool.attributes["medops.agent.action_id"] == str(execution.driver.head.body.loop.history[0].action.action_id)
    assert root.attributes["medops.agent.business_committed"] is True
    assert root.attributes["medops.agent.business_status"] == "completed"
    assert (
        root.attributes["medops.agent.model_calls_total"]
        == root.attributes["medops.agent.model_calls_this_session"]
        == 3
    )
    assert root.attributes["medops.agent.accounted_tokens"] == result.run.budget.accounted_tokens
    assert (
        root.attributes["medops.agent.verification_policy_sha256"]
        == case["context"].versions.verification_policy_sha256
    )
    assert tool.attributes["langfuse.observation.type"] == "tool"
    assert root.attributes["langfuse.observation.type"] == "chain"
    blob = "\n".join(s.to_json() for s in actual)
    assert case["context"].narrative not in blob
    assert "PUBLIC runtime clause" not in blob and '"messages"' not in blob and '"proposal"' not in blob
    assert all(not s.events for s in actual)
    assert all(s.end_time >= s.start_time for s in actual)
    assert current_trace_id() is None


@pytest.mark.parametrize(
    "kind,status", [("finish", "completed"), ("clarify", "awaiting_clarification"), ("escalate", "escalated")]
)
def test_committed_business_status_and_only_fixed_metadata_are_exported(db, spans, kind, status):
    case, fake = terminal_case(db, kind)
    with case["runtime"].start(case["run"]) as execution:
        delivery = execution.execute()
    (root,) = roots(spans)
    assert delivery.run.status == root.attributes["medops.agent.business_status"] == status
    assert root.attributes["medops.agent.business_committed"] is True and len(fake.calls) == 2
    blob = "\n".join(s.to_json() for s in spans.get_finished_spans())
    assert case["context"].narrative not in blob
    for q in delivery.material.questions:
        assert q.question not in blob and q.reason not in blob
    assert root.attributes["medops.case_id"] == str(case["context"].identity.case_id)
    assert root.attributes["medops.task_id"] == str(case["context"].identity.task_id)


def test_internal_finish_handoff_is_never_reported_as_committed_business_completion(db, spans):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
    (root,) = roots(spans)
    assert root.attributes["medops.agent.business_committed"] is False
    assert root.attributes["medops.agent.business_status"] == "unconfirmed"
    assert not any(s.name == "agent.terminal" for s in spans.get_finished_spans())
    assert len(fake.calls) == 1


def test_actual_timeout_keeps_known_and_conservative_accounting_without_provider_error_text(db, spans):
    secret = "PRIVATE_PROVIDER_BODY_AUDIT220"
    case, fake = terminal_case(db, "clarify", reply=ModelTimeout(secret))
    with case["runtime"].start(case["run"]) as execution:
        delivery = execution.execute()
    snapshot = execution.driver.root.snapshot()
    (root,) = roots(spans)
    assert delivery.run.status == root.attributes["medops.agent.business_status"] == "failed"
    assert root.status.status_code is StatusCode.ERROR
    assert root.attributes["error_code"] == delivery.material.reason
    assert root.attributes["medops.agent.accounted_cost_usd"] == snapshot.accounted_cost_usd
    assert root.attributes["medops.agent.known_cost_usd"] == snapshot.known_cost_usd
    assert snapshot.accounted_cost_usd >= snapshot.known_cost_usd
    assert root.attributes["medops.agent.model_calls_total"] == 2 and len(fake.calls) == 2
    assert any(s.status.status_code is StatusCode.ERROR for s in spans.get_finished_spans())
    assert secret not in "\n".join(s.to_json() for s in spans.get_finished_spans())


def test_caller_exception_is_sanitized_and_does_not_fabricate_a_business_result(db, spans):
    secret = "PRIVATE_CALLER_TEXT_AUDIT220"
    case, _ = terminal_case(db)
    with pytest.raises(ValueError, match=secret):
        with case["runtime"].start(case["run"]) as execution:
            execution.run()
            raise ValueError(secret)
    (root,) = roots(spans)
    assert root.status.status_code is StatusCode.ERROR
    assert root.attributes["medops.agent.exception_raised"] is True
    assert root.attributes["medops.agent.business_committed"] is False
    assert root.status.description == "ValueError"
    assert secret not in "\n".join(s.to_json() for s in spans.get_finished_spans())


@pytest.mark.parametrize("after_commit", [False, True])
def test_terminal_rollback_or_lost_acknowledgement_cannot_export_a_confirmed_completion(
    db, spans, monkeypatch, after_commit
):
    from medops.infrastructure.db.agent_control import PgAgentControl

    case, fake = terminal_case(db)
    armed = {"value": False}
    original_seal = PgAgentControl.seal

    def seal(*args, **kwargs):
        value = original_seal(*args, **kwargs)
        armed["value"] = True
        return value

    with pytest.raises(RuntimeError, match="PRIVATE_SAVE_ACK"), case["runtime"].start(case["run"]) as execution:
        execution.run()
        execution.review()
        original_connection = execution.driver.connection

        @contextmanager
        def connection():
            with original_connection() as conn:
                yield conn
                if armed["value"]:
                    armed["value"] = False
                    if after_commit:
                        conn.commit()
                    raise RuntimeError("PRIVATE_SAVE_ACK")

        monkeypatch.setattr(PgAgentControl, "seal", seal)
        execution.driver.connection = connection
        execution.finish()
    (root,) = roots(spans)
    assert root.attributes["medops.agent.business_committed"] is False
    assert root.attributes["medops.agent.business_status"] == "unconfirmed"
    assert root.status.status_code is StatusCode.ERROR
    assert "PRIVATE_SAVE_ACK" not in "\n".join(s.to_json() for s in spans.get_finished_spans())
    assert len(fake.calls) == 2
    if after_commit:
        assert case["runtime"].result(case["context"], user=case["context"].principal).run.status == "completed"


def test_recovery_roots_share_persistent_identity_without_repeating_calls_or_resetting_totals(db, spans):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        execution.review()
    with case["runtime"].recover(case["context"]) as recovered:
        assert recovered.execute().run.status == "completed"
    first, second = roots(spans)
    assert first.context.trace_id == second.context.trace_id == int(case["context"].identity.trace_id, 16)
    assert first.context.span_id != second.context.span_id
    assert first.attributes["medops.agent.recovered"] is False and second.attributes["medops.agent.recovered"] is True
    assert first.attributes["medops.agent.lease_generation"] + 1 == second.attributes["medops.agent.lease_generation"]
    assert first.attributes["medops.agent.model_calls_this_session"] == 2
    assert second.attributes["medops.agent.model_calls_this_session"] == 0
    assert second.attributes["medops.agent.model_calls_total"] == 2 and len(fake.calls) == 2
    assert first.attributes["medops.agent.business_committed"] is False
    assert second.attributes["medops.agent.business_committed"] is True


def test_foreign_parent_is_linked_and_its_context_restored(db, spans):
    case, _ = terminal_case(db)
    with bind_trace_id("f" * 32), telemetry.span("PUBLIC.foreign_request") as parent:
        with case["runtime"].start(case["run"]) as execution:
            execution.execute()
        assert current_trace_id() == "f" * 32
    (root,) = roots(spans)
    assert root.parent is None and len(root.links) == 1
    assert root.links[0].context == parent.get_span_context()
    assert root.context.trace_id == int(case["context"].identity.trace_id, 16)
    assert current_trace_id() is None


def test_fresh_python_process_correlates_recovery_with_original_runtime_without_model_calls(db, spans):
    fake = FakeModelGateway({"agent_plan": [terminal()]})
    case = runtime_case(db, fake)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
    (first,) = roots(spans)
    payload = dict(
        run=case["run"].model_dump(mode="json"), binding=case["binding"].model_dump(mode="json"), chunk=case["chunk"]
    )
    env = dict(os.environ, MEDOPS_TEST_AGENT_APP_URL=db["users"]["app"], PYTHONPATH=os.pathsep.join(sys.path))
    child = subprocess.run(
        [sys.executable, "-m", "tests.support.agent_observability_process"],
        input=json.dumps(payload).encode(),
        capture_output=True,
        env=env,
        timeout=25,
    )
    assert child.returncode == 0, child.stderr.decode()
    observed = json.loads(child.stdout)
    assert observed["trace_id"] == case["context"].identity.trace_id
    assert observed["span_id"] != format(first.context.span_id, "016x")
    assert (
        observed["attributes"]["medops.agent.lease_generation"] == first.attributes["medops.agent.lease_generation"] + 1
    )
    assert observed["attributes"]["medops.agent.model_calls_this_session"] == 0 and observed["calls"] == 0
    assert observed["attributes"]["medops.agent.model_calls_total"] == 1
    assert observed["attributes"]["medops.agent.accounted_tokens"] == first.attributes["medops.agent.accounted_tokens"]
    assert observed["started_at"] == case["run"].started_at.isoformat()


def test_no_exporter_keeps_business_and_budget_guards_unchanged(db):
    previous = telemetry._provider
    telemetry.set_tracer_provider(None)
    try:
        case, fake = terminal_case(db)
        with case["runtime"].start(case["run"]) as execution:
            delivery = execution.execute()
        assert delivery.run.status == "completed" and len(fake.calls) == 2
        assert delivery.run.budget.accounted_tokens == execution.driver.root.snapshot().accounted_tokens
        assert not execution.heartbeat.thread.is_alive()
    finally:
        telemetry.set_tracer_provider(previous)


def test_repeated_finish_read_after_session_close_keeps_original_business_trace(db, spans):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        delivery = execution.execute()
    assert execution.finish() == delivery
    (read,) = [s for s in spans.get_finished_spans() if s.name == "agent.result"]
    assert read.context.trace_id == int(case["context"].identity.trace_id, 16)
    assert read.attributes["medops.run_id"] == str(case["context"].identity.run_id)
    assert len(fake.calls) == 2 and current_trace_id() is None


def test_zero_call_budget_stop_has_an_explicit_failure_reason_without_claiming_business_commit(db, spans):
    from medops.infrastructure.llm.execution_budget import ExecutionLimits

    case, fake = terminal_case(db)
    case["runtime"].limits = ExecutionLimits(token_limit=1, cost_limit_usd=0.6, timeout_s=125)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.run()
    (root,) = roots(spans)
    assert result.reason == "budget_exceeded"
    assert root.attributes["medops.agent.handoff_reason"] == "budget_exceeded"
    assert root.attributes["error_code"] == "budget_exceeded" and root.status.status_code is StatusCode.ERROR
    assert root.attributes["medops.agent.business_committed"] is False
    assert root.attributes["medops.agent.business_status"] == "unconfirmed"
    assert root.attributes["medops.agent.model_calls_this_session"] == 0 and not fake.calls
