from datetime import timedelta

import pytest

from medops.application.agent_contracts import (
    AgentContractError,
    admit_action,
    context_binding,
    validate_observation,
    validate_run_snapshot,
)
from medops.domain.agent_execution import AgentObservation
from tests.support.pv_agent import CANARY, DIGEST, NOW, handle, proposal, run, stopped, uid, wire


def admit(current=None, value=None, registry=None, **changes):
    current = current or run()
    options = dict(
        run=current, action_id=uid(100), evidence_registry=(handle(current),) if registry is None else registry, now=NOW
    )
    options.update(changes)
    return admit_action(wire(proposal() if value is None else value), **options)


@pytest.mark.parametrize(
    "name", ["extract_ae", "search_documents", "read_evidence", "verify_citations", "clarify", "finish", "escalate"]
)
def test_seven_actions_bind_to_server_context_without_running_a_tool_or_completing(name):
    current = run()
    before = current.model_dump_json()
    result = admit(current, proposal(name))
    assert result.proposal.action == name and result.binding == context_binding(current.context)
    assert result.action_id == uid(100) and result.decision_index == 1
    assert current.model_dump_json() == before and current.status == "running"


@pytest.mark.parametrize(
    "field,value",
    [
        ("principal", {"user_id": CANARY}),
        ("run_id", str(uid(90))),
        ("source_selector", CANARY),
        ("model", CANARY),
        ("token_cap", 999999),
        ("status", "completed"),
    ],
)
def test_planner_cannot_override_server_fields(field, value):
    value0 = proposal()
    value0["proposal"][field] = value
    with pytest.raises(AgentContractError, match="^invalid_agent_payload$") as error:
        admit(value=value0)
    assert CANARY not in str(error.value)


@pytest.mark.parametrize("bad", ["unknown", "shell", "browse", "send_email", "release_policy"])
def test_unknown_or_unapproved_action_is_rejected(bad):
    with pytest.raises(AgentContractError, match="^invalid_agent_payload$"):
        admit(value={"proposal": {"action": bad, "rationale": CANARY}})


@pytest.mark.parametrize(
    "body",
    [
        '{"proposal":{"action":"search_documents","query":"x","query":"y","rationale":"x"}}',
        '{"proposal":{},"proposal":{}}',
        '{"proposal": NaN}',
        "[1,2]",
        "{bad",
        b"\xff",
        '{"proposal":{"action":"search_documents","query":"\\ud800","rationale":"x"}}',
    ],
)
def test_malformed_duplicate_or_private_payload_errors_never_echo_body(body):
    with pytest.raises(AgentContractError, match="^invalid_agent_payload$") as error:
        admit_action(body, run=run(), action_id=uid(1), evidence_registry=(), now=NOW)
    assert CANARY not in str(error.value) and error.value.__suppress_context__


@pytest.mark.parametrize("body", ["x" * 65537, "中" * 22000])
def test_size_limit_applies_to_utf8_bytes(body):
    with pytest.raises(AgentContractError, match="^agent_payload_limit$"):
        admit_action(body, run=run(), action_id=uid(1), evidence_registry=(), now=NOW)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "other_task",
        "other_user",
        "changed_query_context",
        "changed_prompt",
        "wrong_source",
        "wrong_version",
        "wrong_source_hash",
        "expired",
        "future_effective",
        "archived_without_history",
    ],
)
def test_forged_cross_run_outdated_or_wrong_source_handle_is_unavailable(change):
    from medops.domain.common import DocStatus

    current = run()
    record = handle(current)
    registry = (record,)
    if change == "missing":
        registry = ()
    elif change == "other_task":
        record = record.model_copy(update={"binding": record.binding.model_copy(update={"task_id": uid(99)})})
    elif change == "other_user":
        current = current.model_copy(
            update={
                "context": current.context.model_copy(
                    update={"principal": current.context.principal.model_copy(update={"user_id": "PUBLIC-other"})}
                )
            }
        )
    elif change == "changed_query_context":
        current = current.model_copy(
            update={
                "context": current.context.model_copy(
                    update={
                        "query_context": current.context.query_context.model_copy(update={"historical_requested": True})
                    }
                )
            }
        )
    elif change == "changed_prompt":
        current = current.model_copy(
            update={
                "context": current.context.model_copy(
                    update={
                        "versions": current.context.versions.model_copy(update={"planning_prompt_sha256": "b" * 64})
                    }
                )
            }
        )
    elif change == "expired":
        record = record.model_copy(update={"expires_at": NOW})
    elif change == "wrong_source_hash":
        record = record.model_copy(update={"source_sha256": "b" * 64})
    else:
        evidence = record.evidence
        if change == "wrong_source":
            evidence = evidence.model_copy(
                update={"citation": evidence.citation.model_copy(update={"doc_id": "PUBLIC-other-doc"})}
            )
        elif change == "wrong_version":
            evidence = evidence.model_copy(
                update={"citation": evidence.citation.model_copy(update={"version": "PUBLIC other"})}
            )
        elif change == "future_effective":
            evidence = evidence.model_copy(
                update={
                    "citation": evidence.citation.model_copy(update={"effective_date": NOW.date() + timedelta(days=1)})
                }
            )
        else:
            evidence = evidence.model_copy(update={"status": DocStatus.archived, "historical": True})
        record = record.model_copy(update={"evidence": evidence})
    if change != "missing":
        registry = (record,)
    with pytest.raises(AgentContractError, match="^agent_handle_unavailable$"):
        admit(current, proposal("read_evidence"), registry=registry)


@pytest.mark.parametrize(
    "change",
    [
        "unknown_requirement",
        "wrong_kind",
        "wrong_quote",
        "outside_span",
        "unknown_missing",
        "empty_query",
        "unmarked_clarification",
        "source_type",
    ],
)
def test_action_fields_cannot_fabricate_task_refs_or_narrative_quotes(change):
    value = proposal("finish")
    if change == "unknown_requirement":
        value["proposal"]["draft"]["guideline_claims"][0]["requirement_id"] = "unknown"
    elif change == "wrong_kind":
        value["proposal"]["draft"]["narrative_facts"][0]["requirement_id"] = "guideline"
    elif change == "wrong_quote":
        value["proposal"]["draft"]["narrative_facts"][0]["quote"] = "SECRET"
    elif change == "outside_span":
        value["proposal"]["draft"]["narrative_facts"][0].update(char_start=100, char_end=106)
    elif change == "unknown_missing":
        value["proposal"]["draft"]["missing_requirement_ids"] = ["unknown"]
    elif change == "empty_query":
        value = proposal()
        value["proposal"]["query"] = "   "
    elif change == "unmarked_clarification":
        value = proposal("clarify")
        value["proposal"]["questions"][0]["field"] = "event"
    else:
        value = proposal("extract_ae")
        value["proposal"]["source_type"] = "email"
    with pytest.raises(AgentContractError, match="^invalid_agent_payload$"):
        admit(value=value)


@pytest.mark.parametrize(
    "change,code",
    [
        ("terminal", "agent_not_running"),
        ("expired", "agent_deadline"),
        ("before_start", "agent_deadline"),
        ("steps", "agent_step_limit"),
        ("tokens", "agent_budget_exhausted"),
        ("reserved_tokens", "agent_budget_exhausted"),
        ("cost", "agent_budget_exhausted"),
        ("reserved_cost", "agent_budget_exhausted"),
        ("token_reserve", "agent_final_reserve"),
        ("cost_reserve", "agent_final_reserve"),
    ],
)
def test_terminal_deadline_step_and_accounted_or_pending_budget_boundaries(change, code):
    current = run()
    options = {}
    if change == "terminal":
        current = stopped(current)
    elif change == "expired":
        options["now"] = current.expires_at
    elif change == "before_start":
        options["now"] = NOW - timedelta(seconds=1)
    elif change == "steps":
        current = current.model_copy(update={"decisions_consumed": 8})
    else:
        updates = {
            "tokens": {"accounted_tokens": 12001},
            "reserved_tokens": {"reserved_tokens": 12000},
            "cost": {"accounted_cost_microusd": 600001},
            "reserved_cost": {"reserved_cost_microusd": 600000},
            "token_reserve": {"accounted_tokens": 11000},
            "cost_reserve": {"accounted_cost_microusd": 550000},
        }[change]
        current = current.model_copy(update={"budget": current.budget.model_copy(update=updates)})
    with pytest.raises(AgentContractError, match="^" + code + "$"):
        admit(current, **options)


def test_final_reserve_is_available_for_finish_request_but_is_not_a_completion_gate():
    current = run()
    current = current.model_copy(update={"budget": current.budget.model_copy(update={"accounted_tokens": 11000})})
    assert admit(current, proposal("finish")).proposal.action == "finish"
    assert current.status == "running"


@pytest.mark.parametrize(
    "change", ["profile_bool", "usage_bool", "step_bool", "synthetic_int", "bad_context_text", "duplicate_handles"]
)
def test_copied_dtos_revalidate_native_types_and_metadata_without_echo(change):
    current = run()
    registry = None
    if change == "profile_bool":
        current = current.model_copy(
            update={
                "context": current.context.model_copy(
                    update={"profile": current.context.profile.model_copy(update={"token_cap": True})}
                )
            }
        )
    elif change == "usage_bool":
        current = current.model_copy(update={"budget": current.budget.model_copy(update={"accounted_tokens": True})})
    elif change == "step_bool":
        current = current.model_copy(update={"decisions_consumed": True})
    elif change == "synthetic_int":
        current = current.model_copy(update={"context": current.context.model_copy(update={"synthetic": 1})})
    elif change == "bad_context_text":
        current = current.model_copy(
            update={"context": current.context.model_copy(update={"narrative": "\ud800" * 20})}
        )
    else:
        registry = (handle(current), handle(current))
    with pytest.raises(AgentContractError, match="^invalid_agent_metadata$") as error:
        admit(current, registry=registry)
    assert CANARY not in str(error.value)


def test_stopped_snapshot_rejects_terminal_receipt_for_other_conditions():
    current = stopped(run())
    changed = current.model_copy(
        update={
            "terminal": current.terminal.model_copy(
                update={"binding": current.terminal.binding.model_copy(update={"conditions_sha256": "b" * 64})}
            )
        }
    )
    with pytest.raises(AgentContractError, match="^agent_binding_mismatch$"):
        validate_run_snapshot(changed)


@pytest.mark.parametrize("change", ["action_id", "binding", "action"])
def test_observation_cannot_be_attached_to_another_action_or_run(change):
    action = admit()
    observation = AgentObservation(
        action_id=action.action_id,
        binding=action.binding,
        action="search_documents",
        kind="ok",
        result_ref=uid(50),
        result_sha256=DIGEST,
        new_legal_information=True,
        retryable=False,
    )
    changes = {
        "action_id": {"action_id": uid(99)},
        "binding": {"binding": observation.binding.model_copy(update={"run_id": uid(99)})},
        "action": {"action": "extract_ae"},
    }[change]
    with pytest.raises(AgentContractError, match="^agent_binding_mismatch$"):
        validate_observation(action, observation.model_copy(update=changes))
    assert validate_observation(action, observation) == observation
