import pytest
from pydantic import ValidationError

from medops.domain import AgentState, Answer, Claim, DocStatus, ReasonCode, SafetyDecision, SafetyResult, VerifyResult
from tests.unit.domain.conftest import make_evidence


def test_full_run_round_trips_through_json(answered_state):
    restored = AgentState.model_validate_json(answered_state.model_dump_json())
    assert restored == answered_state
    assert restored.answer is not None and restored.answer.citations[0].chunk_id == "c1"


def test_advance_returns_new_state_and_revalidates(base_state):
    nxt = base_state.advance(rewritten_queries=("q1", "q2"))
    assert nxt is not base_state and base_state.rewritten_queries == () and nxt.rewritten_queries == ("q1", "q2")
    with pytest.raises(ValidationError):
        base_state.advance(rewritten_queries=("q1", "q2", "q3", "q4"))  # bounded 1-3


def test_answer_is_unrepresentable_without_evidence_verify_and_safety(base_state, answered_state):
    ev = make_evidence()
    answer = Answer(claims=(Claim(text="x", citation_chunk_ids=("c1",)),), citations=(ev.citation,))
    intent = answered_state.intent.model_dump()
    with pytest.raises(ValidationError, match="classified intent"):
        base_state.advance(answer=answer.model_dump())
    with pytest.raises(ValidationError, match="requires verified evidence"):
        base_state.advance(intent=intent, answer=answer.model_dump())
    with pytest.raises(ValidationError, match="verify_result"):
        base_state.advance(intent=intent, evidence=(ev.model_dump(),), answer=answer.model_dump())
    refused = SafetyResult(
        decision=SafetyDecision.refuse, reason_codes=(ReasonCode.high_risk_medical,), checker_version="s"
    )
    with pytest.raises(ValidationError, match="safety decision allow"):
        answered_state.advance(safety_result=refused.model_dump(), answer=answered_state.answer.model_dump())
    # without an explicitly re-supplied answer the stale answer is simply dropped (D-04)
    assert answered_state.advance(safety_result=refused.model_dump()).answer is None


def test_answer_cannot_cite_outside_verified_evidence(answered_state):
    ghost = Answer(
        claims=(Claim(text="x", citation_chunk_ids=("c9",)),), citations=(make_evidence(chunk_id="c9").citation,)
    )
    with pytest.raises(ValidationError, match="field by field"):
        answered_state.advance(answer=ghost.model_dump())


def test_contradiction_blocks_answer(answered_state):
    contradicted = VerifyResult(
        structural_ok=True,
        verifier_version="v",
        elements=({"kind": "dose", "text": "0.5 g", "verdict": "contradicted", "confidence": 0.9},),
    )
    with pytest.raises(ValidationError, match="non-contradicted"):
        answered_state.advance(
            verify_result=contradicted.model_dump(),
            safety_result=answered_state.safety_result.model_dump(),
            answer=answered_state.answer.model_dump(),
        )


def test_historical_evidence_requires_explicit_request_and_notice(base_state):
    hist = make_evidence(status=DocStatus.archived, historical=True)
    with pytest.raises(ValidationError, match="historical request"):
        base_state.advance(evidence=(hist.model_dump(),))
    state = base_state.advance(historical_requested=True, evidence=(hist.model_dump(),))
    assert state.evidence[0].historical


def test_answer_and_escalation_are_mutually_exclusive(answered_state):
    esc = {"reason_codes": ["insufficient_evidence"], "query": answered_state.query, "policy_version": "pol-1"}
    with pytest.raises(ValidationError, match="never both"):
        answered_state.advance(escalation=esc)
    ended = answered_state.advance(answer=None, escalation=esc)
    assert ended.escalation is not None and ended.answer is None
    with pytest.raises(ValidationError, match="policy_version"):
        answered_state.advance(answer=None, escalation={**esc, "policy_version": "other"})


def test_evidence_limits_and_uniqueness(base_state):
    ev = make_evidence()
    with pytest.raises(ValidationError, match="unique"):
        base_state.advance(evidence=(ev.model_dump(), ev.model_dump()))
    many = tuple(make_evidence(chunk_id=f"c{i}").model_dump() for i in range(9))
    with pytest.raises(ValidationError):
        base_state.advance(evidence=many)  # at most 8 in context (baseline 4.4)


def test_budget_overrun_is_rejected(answered_state):
    with pytest.raises(ValidationError, match="exceeded"):
        answered_state.advance(budget={"limit": 8000, "used": 8001})
