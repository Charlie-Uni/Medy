"""Reflect (M4-02): the attribution rule table, the human override payload and which attribution is effective."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from medops.loop.reflect import CLASSES, CaseFacts, attribute, effective_attribution, override_payload


def facts(**kw) -> CaseFacts:
    base = {
        "case_id": "c",
        "trace_id": "t",
        "dept": "MA",
        "label": "bad",
        "reasons": (),
        "outcome": "answered",
        "reason_codes": (),
        "evidence_count": 5,
        "cited_count": 1,
        "flagged_count": 0,
    }
    base.update(kw)
    return CaseFacts(**base)


@pytest.mark.parametrize(
    ("f", "cls", "confidence"),
    [
        (
            facts(
                reasons=("safety_flagged",), flagged_count=1, outcome="escalated", reason_codes=("prompt_injection",)
            ),
            "safety",
            0.9,
        ),
        (facts(outcome="escalated", reason_codes=("acl_denied",)), "safety", 0.9),
        (facts(outcome="escalated", reason_codes=("intent_unclear",)), "intent", 0.8),
        (
            facts(outcome="refused", reason_codes=("high_risk_medical",), feedback_down=1, reasons=("feedback_down",)),
            "intent",
            0.6,
        ),
        (facts(outcome="refused", reason_codes=("high_risk_medical",)), None, None),  # a correct refusal is not a case
        (
            facts(outcome="escalated", reason_codes=("unsupported_conclusion",), escalation_resolution="false_alarm"),
            "generation",
            0.7,
        ),
        (
            facts(
                outcome="escalated",
                reason_codes=("unsupported_conclusion",),
                reasons=("verifier_failed",),
                escalation_detail="no claim survives verification (forged=0, dropped=1)",
            ),
            "generation",
            0.7,
        ),
        (
            facts(
                outcome="escalated", reason_codes=("insufficient_evidence",), escalation_resolution="confirmed_issue"
            ),
            "knowledge_gap",
            0.8,
        ),
        (facts(outcome="escalated", reason_codes=("insufficient_evidence",), evidence_count=0), "knowledge_gap", 0.7),
        (facts(outcome="escalated", reason_codes=("insufficient_evidence",), evidence_count=6), "retrieval", 0.5),
        (facts(replay_changed=True, reasons=("replay_drift",)), "generation", 0.5),
        (facts(feedback_down=1, reasons=("feedback_down",)), "generation", 0.4),
        (facts(feedback_corrections=1, reasons=("feedback_correction",)), "generation", 0.4),
        (facts(), None, None),
    ],
)
def test_rule_table(f, cls, confidence):
    result = attribute(f)
    if cls is None:
        assert result is None
    else:
        assert (result.attribution, result.confidence) == (cls, confidence) and result.note


def test_safety_wins_over_everything_and_notes_stay_short():
    f = facts(
        reasons=("feedback_down", "verifier_failed", "safety_flagged"),
        outcome="escalated",
        reason_codes=("unsupported_conclusion", "prompt_injection"),
        flagged_count=2,
        feedback_down=3,
        escalation_detail="x" * 2000,
    )
    result = attribute(f)
    assert result is not None and result.attribution == "safety" and len(result.note) < 500


def test_override_payload_and_effective_attribution():
    at = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    payload = override_payload(
        attribution="knowledge_gap", by="reviewer-1", note="corpus lacks the 2024 revision", at=at
    )
    assert payload == {
        "attribution": "knowledge_gap",
        "by": "reviewer-1",
        "note": "corpus lacks the 2024 revision",
        "at": at.isoformat(),
    }
    with pytest.raises(ValueError):
        override_payload(attribution="verifier", by="r", note=None)
    with pytest.raises(ValueError):
        override_payload(attribution="intent", by="", note=None)
    assert effective_attribution({"attribution": "retrieval", "human_override": payload}) == "knowledge_gap"
    assert effective_attribution({"attribution": "retrieval", "human_override": None}) == "retrieval"
    assert effective_attribution({"attribution": None, "human_override": {"attribution": "bogus"}}) is None
    assert set(CLASSES) == {"retrieval", "intent", "generation", "knowledge_gap", "safety"}
