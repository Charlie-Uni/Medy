"""Bounded final shape: real request factories, explicit engineering inputs, no billing."""

import pytest
from pydantic import ValidationError

from medops.application.agent_final_gate import (
    FinalGateConfig,
    check_structure,
    derived_profile,
    material_request,
    startup_reserve,
)
from medops.application.agent_tool_ports import AgentToolFault
from medops.domain.agent_actions import ReviewDraft
from medops.infrastructure.llm.execution_budget import PRICES, estimate_request
from medops.infrastructure.llm.gateway import BudgetExceeded
from tests.support.pv_agent import draft, run
from tests.support.pv_final import setup_final
from tests.support.pv_tools import parent


def config(**changes):
    values = dict(
        model_id="gpt-6-sol",
        max_output_tokens=128,
        timeout_s=20,
        max_review_user_bytes=2000,
        max_citation_user_bytes=500,
        max_citation_judges=1,
    )
    return FinalGateConfig(**(values | changes))


def test_real_final_shape_derives_the_startup_floor_without_issuing_requests():
    current = run()
    cfg = config()
    estimate = startup_reserve(cfg, PRICES)
    profile = derived_profile(current.context, cfg, PRICES)
    request = material_request(current.context, ReviewDraft(**draft()), cfg)
    assert estimate.tokens == profile.final_reserve_tokens > estimate_request(request).tokens
    assert profile.cost_cap_microusd == 600000 and profile.token_cap == 12000
    assert startup_reserve(config(max_review_user_bytes=2001), PRICES).tokens == estimate.tokens + 1
    with pytest.raises(ValidationError):
        derived_profile(current.context, config(max_review_user_bytes=12000), PRICES)


@pytest.mark.parametrize("case", ["missing", "wrong_kind", "false_quote", "extra"])
def test_structural_final_gate_rejects_miscoverage_and_fabricated_quotes(case):
    current, value = run(), draft()
    if case == "missing":
        value["narrative_facts"] = []
    elif case == "wrong_kind":
        value["narrative_facts"][0]["requirement_id"] = "guideline"
    elif case == "false_quote":
        value["narrative_facts"][0]["quote"] = "WRONG!"
    else:
        value["guideline_claims"][0]["requirement_id"] = "unknown"
    with pytest.raises(AgentToolFault):
        check_structure(current.context, ReviewDraft(**value))


@pytest.mark.parametrize("semantic", [True, False, "true"])
def test_real_final_gate_uses_original_protected_root_and_seals_it(semantic):
    current, tool, facts, fake, action, record = setup_final(
        reserve=10000,
        script={
            "verify": [{"verdict": "supported", "reason": "PUBLIC"}],
            "agent_final_material": [{"narrative_supported": semantic, "complete": True, "scope_safe": True}],
        },
    )
    with parent(token_limit=12000) as root:
        if isinstance(semantic, str):
            with pytest.raises(AgentToolFault):
                tool.verify_final_citations(action, run=current, evidence_registry=(record,), final_config=config())
        else:
            proof = tool.verify_final_citations(action, run=current, evidence_registry=(record,), final_config=config())
            assert proof.material_check.semantic_supported is semantic
            assert proof.material_check.citations_supported and current.status == "running"
            assert facts.final_calls
        assert root.finalization_snapshot().state == "closed" and root.snapshot().calls == 2
    assert [r.purpose for r in fake.calls] == ["verify", "agent_final_material"]


def test_final_shape_overflow_stops_before_any_provider_and_preserves_root_cap():
    current, tool, _, fake, action, record = setup_final(reserve=10000)
    with parent(token_limit=12000) as root, pytest.raises(BudgetExceeded):
        tool.verify_final_citations(
            action, run=current, evidence_registry=(record,), final_config=config(max_review_user_bytes=1)
        )
    assert not fake.calls and root.snapshot().calls == 0 and root.snapshot().limits.token_limit == 12000


def test_duplicate_final_verdict_keys_are_rejected_even_if_gateway_parsed_them():
    current, tool, _, fake, action, record = setup_final(
        reserve=10000,
        script={
            "verify": [{"verdict": "supported", "reason": "PUBLIC"}],
            "agent_final_material": [
                '{"narrative_supported":false,"narrative_supported":true,"complete":true,"scope_safe":true}'
            ],
        },
    )
    with parent(token_limit=12000) as root, pytest.raises(AgentToolFault):
        tool.verify_final_citations(action, run=current, evidence_registry=(record,), final_config=config())
    assert root.finalization_snapshot().state == "closed" and root.snapshot().calls == 2
    assert len(fake.calls) == 2
