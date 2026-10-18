"""PUBLIC stop-judge request/schema/cross-task cases; deterministic, no hosted calls."""

import json

import pytest
from pydantic import ValidationError

from medops.application.agent_stop_gate import parse_stop_verdict, stop_request
from medops.application.agent_tool_ports import AgentToolFault
from medops.infrastructure.llm.gateway import BudgetExceeded
from tests.support.agent_terminal import stop_verdict
from tests.support.pv_loop import setup_loop, terminal
from tests.support.pv_review import final_config
from tests.support.pv_tools import parent


def stopped():
    current, loop, driver, _, _ = setup_loop({"agent_plan": [terminal("clarify")]}, resolution="ambiguous")
    with parent():
        result = loop.run(current)
    assert result.reason == "clarification_required"
    return current.context, driver.events[-1].state


@pytest.mark.parametrize("case", ["missing", "duplicate", "foreign", "string", "extra", "missing_flag"])
def test_missing_wrong_or_untyped_question_judgements_are_rejected(case):
    ctx, state = stopped()
    raw = stop_verdict()
    if case == "missing":
        raw["questions"] = []
    elif case == "duplicate":
        raw["questions"] *= 2
    elif case == "foreign":
        raw["questions"][0]["field"] = "requirements"
    elif case == "string":
        raw["questions"][0]["necessary"] = "true"
    elif case == "extra":
        raw["gold"] = "PUBLIC evaluator input must not be accepted"
    else:
        del raw["scope_safe"]
    with pytest.raises((AgentToolFault, ValidationError)):
        parse_stop_verdict(raw, ctx, state.terminal_request)


def test_stop_request_uses_actual_committed_context_and_cannot_cross_tasks():
    ctx, state = stopped()
    request = stop_request(ctx, state, final_config())
    data = json.loads(request.messages[1].content)
    assert data["narrative"] == ctx.narrative and data["action"]["action"] == "clarify"
    assert data["observations"] == []
    assert set(data) == {
        "narrative",
        "requirements",
        "source_scope",
        "clarifiable_fields",
        "action",
        "observations",
        "steps_consumed",
        "evidence",
    }
    with pytest.raises(AgentToolFault):
        stop_request(ctx.model_copy(update={"narrative": "PUBLIC different original narrative"}), state, final_config())
    with pytest.raises(BudgetExceeded):
        stop_request(ctx, state, final_config(max_review_user_bytes=1))


@pytest.mark.parametrize("key", ["decision_supported", "scope_safe", "narrative_supported"])
def test_false_is_preserved_instead_of_defaulting_to_a_success(key):
    ctx, state = stopped()
    result = parse_stop_verdict(stop_verdict(**{key: False}), ctx, state.terminal_request)
    assert getattr(result, key) is False
