"""Regressions for Codex findings D-01..D-05 (2026-09-10)."""

import pytest
from pydantic import ValidationError

from medops.domain import (
    Answer,
    CandidateRef,
    Citation,
    Claim,
    ElementKind,
    ElementSupport,
    Intent,
    IntentType,
    RiskLevel,
    SourceRank,
    Verdict,
    VerifyResult,
)
from tests.unit.domain.conftest import make_evidence


def _answer_for(citation: Citation) -> Answer:
    return Answer(claims=(Claim(text="x", citation_chunk_ids=(citation.chunk_id,)),), citations=(citation,))


# D-01 ------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "field,value", [("doc_id", "forged-doc"), ("version", "9999-99"), ("page", 42), ("section", "伪造章节")]
)
def test_answer_citation_must_match_evidence_field_by_field(answered_state, field, value):
    forged = answered_state.evidence[0].citation.model_copy(update={field: value})
    with pytest.raises(ValidationError, match="field by field"):
        answered_state.advance(answer=_answer_for(forged).model_dump())


# D-02 ------------------------------------------------------------------------------------------
def test_not_supported_elements_block_the_answer(answered_state):
    vr = answered_state.verify_result.model_copy(
        update={
            "elements": answered_state.verify_result.elements
            + (ElementSupport(kind=ElementKind.dose, text="1 g", verdict=Verdict.not_supported, confidence=0.7),)
        }
    )
    with pytest.raises(ValidationError, match="not_supported"):
        answered_state.advance(
            verify_result=vr.model_dump(),
            safety_result=answered_state.safety_result.model_dump(),
            answer=answered_state.answer.model_dump(),
        )


def test_supported_element_must_point_at_evidence_in_this_run(base_state):
    ev = make_evidence(chunk_id="c1")
    vr = VerifyResult(
        structural_ok=True,
        verifier_version="v",
        elements=(
            ElementSupport(
                kind=ElementKind.dose,
                text="0.5 g",
                verdict=Verdict.supported,
                evidence_chunk_id="ghost",
                confidence=0.9,
            ),
        ),
    )
    with pytest.raises(ValidationError, match="outside evidence"):
        base_state.advance(evidence=(ev.model_dump(),), verify_result=vr.model_dump())


# D-03 ------------------------------------------------------------------------------------------
def test_answer_requires_intent_and_high_risk_intent_cannot_be_answered(answered_state):
    with pytest.raises(ValidationError, match="classified intent"):
        answered_state.advance(
            intent=None,
            rewritten_queries=answered_state.rewritten_queries,
            candidates=tuple(c.model_dump() for c in answered_state.candidates),
            evidence=tuple(e.model_dump() for e in answered_state.evidence),
            verify_result=answered_state.verify_result.model_dump(),
            safety_result=answered_state.safety_result.model_dump(),
            answer=answered_state.answer.model_dump(),
        )
    high = Intent(type=IntentType.high_risk, risk=RiskLevel.high, confidence=0.9)
    with pytest.raises(ValidationError, match="never answered"):
        answered_state.advance(
            intent=high.model_dump(),
            rewritten_queries=answered_state.rewritten_queries,
            candidates=tuple(c.model_dump() for c in answered_state.candidates),
            evidence=tuple(e.model_dump() for e in answered_state.evidence),
            verify_result=answered_state.verify_result.model_dump(),
            safety_result=answered_state.safety_result.model_dump(),
            answer=answered_state.answer.model_dump(),
        )


def test_high_risk_level_on_a_legitimate_skill_still_answers(answered_state):
    off_label = Intent(
        type=IntentType.off_label_check, target_skill="off_label_check", risk=RiskLevel.high, confidence=0.9
    )
    state = answered_state.advance(
        intent=off_label.model_dump(),
        rewritten_queries=answered_state.rewritten_queries,
        candidates=tuple(c.model_dump() for c in answered_state.candidates),
        evidence=tuple(e.model_dump() for e in answered_state.evidence),
        verify_result=answered_state.verify_result.model_dump(),
        safety_result=answered_state.safety_result.model_dump(),
        answer=answered_state.answer.model_dump(),
    )
    assert state.answer is not None and state.intent.risk is RiskLevel.high


# D-04 ------------------------------------------------------------------------------------------
def test_changing_upstream_inputs_clears_downstream_results(answered_state):
    for field, value in (
        ("query", "另一个问题"),
        ("versions", {**answered_state.versions.model_dump(), "policy_version": "pol-2"}),
    ):
        nxt = answered_state.advance(**{field: value})
        assert (
            nxt.intent is None
            and nxt.evidence == ()
            and nxt.verify_result is None
            and nxt.safety_result is None
            and nxt.answer is None
        ), field
    changed_evidence = answered_state.advance(evidence=(make_evidence(text="孕妇禁用").model_dump(),))
    assert (
        changed_evidence.verify_result is None
        and changed_evidence.answer is None
        and changed_evidence.intent is not None
    )


def test_downstream_supplied_in_the_same_call_is_kept_and_revalidated(answered_state):
    new_ev = make_evidence(chunk_id="c2", text="孕妇禁用")
    vr = VerifyResult(
        structural_ok=True,
        verifier_version="v",
        elements=(
            ElementSupport(
                kind=ElementKind.population,
                text="孕妇",
                verdict=Verdict.supported,
                evidence_chunk_id="c2",
                confidence=0.9,
            ),
        ),
    )
    nxt = answered_state.advance(evidence=(new_ev.model_dump(),), verify_result=vr.model_dump())
    assert nxt.verify_result == vr and nxt.safety_result is None and nxt.answer is None
    with pytest.raises(ValidationError):  # stale answer explicitly re-supplied against new evidence is rejected
        answered_state.advance(
            evidence=(new_ev.model_dump(),),
            verify_result=vr.model_dump(),
            safety_result=answered_state.safety_result.model_dump(),
            answer=answered_state.answer.model_dump(),
        )


def test_unchanged_value_in_updates_does_not_clear_downstream(answered_state):
    same = answered_state.advance(query=answered_state.query, budget={"limit": 8000, "used": 1300})
    assert same.answer == answered_state.answer and same.budget.used == 1300


# D-05 ------------------------------------------------------------------------------------------
def test_candidate_ranks_are_immutable_and_positive():
    ref = CandidateRef(
        chunk_id="c1", source_ranks=(SourceRank(source="lexical", rank=1), SourceRank(source="vector", rank=3))
    )
    with pytest.raises(ValidationError):
        ref.source_ranks[0].rank = 9  # type: ignore[misc]
    with pytest.raises((TypeError, AttributeError)):
        ref.source_ranks.append(SourceRank(source="x", rank=1))  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        SourceRank(source="lexical", rank=0)
    with pytest.raises(ValidationError, match="one rank per candidate"):
        CandidateRef(
            chunk_id="c1", source_ranks=(SourceRank(source="lexical", rank=1), SourceRank(source="lexical", rank=2))
        )
    restored = CandidateRef.model_validate_json(ref.model_dump_json())
    assert restored == ref and all(r.rank >= 1 for r in restored.source_ranks)


# D-04 follow-ups (Codex re-review) -------------------------------------------------------------
def test_equivalent_inputs_in_any_representation_are_not_a_change(answered_state):
    s = answered_state
    same_model = s.advance(intent=s.intent)
    same_versions = s.advance(versions=s.versions)
    same_evidence_models = s.advance(evidence=s.evidence)
    same_evidence_dicts = s.advance(evidence=[e.model_dump() for e in s.evidence])
    for nxt in (same_model, same_versions, same_evidence_models, same_evidence_dicts):
        assert nxt == s


def test_changing_session_entities_clears_dependent_results(answered_state):
    nxt = answered_state.advance(session_entities=({"kind": "drug", "value": "示例药品Y"},))
    assert nxt.intent is None and nxt.rewritten_queries == () and nxt.verify_result is None and nxt.answer is None


def test_stale_escalation_is_cleared_and_inconsistent_escalation_is_rejected(answered_state):
    esc = {
        "reason_codes": ["insufficient_evidence"],
        "query": answered_state.query,
        "evidence_chunk_ids": ["c1"],
        "policy_version": "pol-1",
    }
    escalated = answered_state.advance(answer=None, escalation=esc)
    assert escalated.escalation is not None and escalated.escalation.evidence_chunk_ids == ("c1",)
    replaced = escalated.advance(evidence=(make_evidence(chunk_id="c2", text="孕妇禁用").model_dump(),))
    assert replaced.escalation is None and replaced.evidence[0].citation.chunk_id == "c2"
    with pytest.raises(ValidationError, match="not in this state"):
        escalated.advance(evidence=(make_evidence(chunk_id="c2", text="孕妇禁用").model_dump(),), escalation=esc)
