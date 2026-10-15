import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from medops.contracts_export import render
from medops.domain.agent_actions import PlannerProposal
from medops.domain.agent_execution import AgentContext, AgentObservation, AgentProfile, PVAgentRun, TerminalRecord
from tests.support.pv_agent import DIGEST, NOW, proposal, run, stopped, uid


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_synthetic_marker_requires_explicit_true(value):
    current = run()
    data = current.context.model_dump(mode="python")
    data["synthetic"] = value
    with pytest.raises(ValidationError):
        AgentContext.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_decision_steps", 9),
        ("token_cap", 24000),
        ("cost_cap_microusd", 1200000),
        ("timeout_ms", 250000),
        ("same_no_progress_limit", 3),
        ("final_reserve_tokens", 0),
        ("final_reserve_cost_microusd", True),
    ],
)
def test_profile_cannot_increase_approved_limits_or_omit_final_reserve(field, value):
    values = run().context.profile.model_dump()
    values[field] = value
    with pytest.raises(ValidationError):
        AgentProfile.model_validate(values)


def test_private_run_json_roundtrip_and_terminal_receipt_are_structural_not_execution_proof():
    current = run()
    restored = PVAgentRun.model_validate_json(current.model_dump_json())
    assert restored == current
    completed = stopped(current)
    restored = PVAgentRun.model_validate_json(completed.model_dump_json())
    assert restored.status == "completed" and restored.terminal.verification_ref == uid(23)
    with pytest.raises(ValidationError):
        current.status = "completed"
    with pytest.raises(ValidationError):
        PVAgentRun.model_validate({**current.model_dump(), "status": "completed"})


@pytest.mark.parametrize(
    "status,reason",
    [
        ("awaiting_clarification", "clarification_required"),
        ("escalated", "insufficient_evidence"),
        ("failed", "timeout"),
        ("cancelled", "cancelled"),
    ],
)
def test_terminal_states_preserve_distinct_business_and_system_reasons(status, reason):
    current = stopped(run(), status, reason)
    assert PVAgentRun.model_validate_json(current.model_dump_json()).terminal.reason == reason
    bad = current.terminal.model_copy(update={"reason": "completed"})
    with pytest.raises(ValidationError):
        TerminalRecord.model_validate(bad.model_dump())


@pytest.mark.parametrize(
    "change",
    [
        "late_completion",
        "overspend",
        "unsettled",
        "wrong_run",
        "naive_time",
        "deadline_extension",
        "running_with_terminal",
    ],
)
def test_run_state_rejects_illegal_completion_or_rebudgeting(change):
    from datetime import timedelta

    current = stopped(run())
    if change == "late_completion":
        current = current.model_copy(update={"stopped_at": current.expires_at + timedelta(seconds=1)})
    elif change == "overspend":
        current = current.model_copy(update={"budget": current.budget.model_copy(update={"accounted_tokens": 12001})})
    elif change == "unsettled":
        current = current.model_copy(update={"budget": current.budget.model_copy(update={"reserved_cost_microusd": 1})})
    elif change == "wrong_run":
        current = current.model_copy(
            update={
                "terminal": current.terminal.model_copy(
                    update={"binding": current.terminal.binding.model_copy(update={"run_id": uid(99)})}
                )
            }
        )
    elif change == "naive_time":
        current = current.model_copy(update={"started_at": NOW.replace(tzinfo=None)})
    elif change == "deadline_extension":
        current = current.model_copy(update={"expires_at": current.expires_at + timedelta(seconds=1)})
    else:
        current = current.model_copy(update={"status": "running"})
    with pytest.raises(ValidationError):
        PVAgentRun.model_validate(current.model_dump())


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "empty", "new_legal_information": True},
        {"kind": "denied_or_unavailable", "evidence_handles": (uid(1),)},
        {"result_sha256": None},
        {"retryable": True},
        {"new_legal_information": 1},
    ],
)
def test_observation_does_not_turn_failures_into_progress_or_expose_body_fields(changes):
    from medops.application.agent_contracts import context_binding

    data = dict(
        action_id=uid(10),
        binding=context_binding(run().context),
        action="search_documents",
        kind="ok",
        result_ref=uid(50),
        result_sha256=DIGEST,
        new_legal_information=False,
        retryable=False,
    )
    data.update(changes)
    with pytest.raises(ValidationError):
        AgentObservation.model_validate(data)
    data.update(
        kind="dependency_error",
        evidence_handles=(),
        new_legal_information=False,
        result_ref=None,
        result_sha256=None,
        retryable=True,
    )
    assert AgentObservation.model_validate(data).kind == "dependency_error"


def test_exported_action_schema_rejects_unknown_nested_fields_and_allows_exact_seven_actions():
    schema = json.loads(render()["agent/PlannerProposal.schema.json"])
    validator = Draft202012Validator(schema)
    for name in (
        "extract_ae",
        "search_documents",
        "read_evidence",
        "verify_citations",
        "clarify",
        "finish",
        "escalate",
    ):
        value = proposal(name)
        assert validator.is_valid(value) and PlannerProposal.model_validate(value).proposal.action == name
        value["proposal"]["principal"] = {"user_id": "PUBLIC-forged"}
        assert not validator.is_valid(value)
    assert set(schema["properties"]["proposal"]["discriminator"]["mapping"]) == {
        "extract_ae",
        "search_documents",
        "read_evidence",
        "verify_citations",
        "clarify",
        "finish",
        "escalate",
    }


@pytest.mark.parametrize(
    "change",
    [
        "missing_terminal",
        "wrong_terminal_status",
        "wrong_reason",
        "missing_verification",
        "running_with_terminal",
        "unresolved_source",
    ],
)
def test_exported_run_schema_enforces_expressible_status_and_source_rules(change):
    current = stopped(run()).model_dump(mode="json")
    if change == "missing_terminal":
        current["terminal"] = None
    elif change == "wrong_terminal_status":
        current["terminal"]["status"] = "failed"
    elif change == "wrong_reason":
        current["terminal"]["reason"] = "timeout"
    elif change == "missing_verification":
        current["terminal"]["verification_ref"] = None
    elif change == "running_with_terminal":
        current["status"] = "running"
    else:
        current["context"]["source_scope"]["resolution"] = "ambiguous"
    validator = Draft202012Validator(json.loads(render()["agent/PVAgentRun.schema.json"]))
    assert validator.is_valid(stopped(run()).model_dump(mode="json"))
    assert not validator.is_valid(current)
    with pytest.raises(ValidationError):
        PVAgentRun.model_validate(current)


@pytest.mark.parametrize(
    "change",
    ["missing_result", "half_result", "failure_progress", "failure_handles", "wrong_retry", "duplicate_handles"],
)
def test_exported_observation_schema_rejects_false_success_and_retry(change):
    from medops.application.agent_contracts import context_binding

    current = AgentObservation(
        action_id=uid(12),
        binding=context_binding(run().context),
        action="search_documents",
        kind="ok",
        result_ref=uid(50),
        result_sha256=DIGEST,
        new_legal_information=True,
        retryable=False,
    ).model_dump(mode="json")
    validator = Draft202012Validator(json.loads(render()["agent/AgentObservation.schema.json"]))
    assert validator.is_valid(current)
    if change == "missing_result":
        del current["result_ref"]
    elif change == "half_result":
        current.update(result_ref=None, result_sha256=DIGEST)
    elif change == "failure_progress":
        current["kind"] = "empty"
    elif change == "failure_handles":
        current.update(kind="denied_or_unavailable", new_legal_information=False, evidence_handles=[str(uid(10))])
    elif change == "wrong_retry":
        current["retryable"] = True
    else:
        current["evidence_handles"] = [str(uid(10)), str(uid(10))]
    assert not validator.is_valid(current)
    with pytest.raises(ValidationError):
        AgentObservation.model_validate(current)
