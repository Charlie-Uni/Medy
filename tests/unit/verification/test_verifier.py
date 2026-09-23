"""Verifier: structural citation check, element verdicts, statement fallback and the optional LLM judge."""

from __future__ import annotations

import pytest

from medops.domain.answer import Claim
from medops.domain.verification import ElementKind, Verdict
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelOutputInvalid
from medops.verification.verifier import structural_check, verify_claims, verify_evidence
from tests.unit.harness._fixtures import evidence

EV = [
    evidence("c1", "年齡 6 至 12 歲的孩童：口服，100 mg，一天三次；或 300 mg 當作一個單一劑量，一天一次。"),
    evidence("c2", "Losartan potassium 禁用於對本項產品任何組成過敏者。"),
]


def test_structural_check_reports_forged_citations_only():
    assert structural_check(["c1", "c9", "c2", "c9"], EV) == ("c9",)
    vr = verify_claims([Claim(text="任意陳述", citation_chunk_ids=("c9",))], EV)
    assert vr.structural_ok is False and vr.hallucinated_citations == ("c9",)


def test_numeric_elements_are_verified_by_rules_first():
    vr = verify_claims([Claim(text="6 至 12 歲孩童口服 100 mg，一天三次", citation_chunk_ids=("c1",))], EV)
    kinds = {e.kind: e.verdict for e in vr.elements}
    assert kinds[ElementKind.dose] is Verdict.supported and kinds[ElementKind.frequency] is Verdict.supported
    assert kinds[ElementKind.population] is Verdict.supported  # 孩童 contained in the evidence
    assert vr.structural_ok and not vr.unsupported and not vr.contradicted
    bad = verify_claims([Claim(text="孩童口服 500 mg", citation_chunk_ids=("c1",))], EV)
    assert bad.contradicted is False  # two doses in the evidence: the rule stays undetermined -> not_supported
    assert [e.verdict for e in bad.elements if e.kind is ElementKind.dose] == [Verdict.not_supported]


def test_statement_without_elements_uses_containment_then_overlap_then_judge():
    contained = verify_claims([Claim(text="禁用於對本項產品任何組成過敏者", citation_chunk_ids=("c2",))], EV)
    assert contained.elements[0].kind is ElementKind.statement and contained.elements[0].verdict is Verdict.supported
    unrelated = verify_claims([Claim(text="本品可與葡萄柚汁同服", citation_chunk_ids=("c2",))], EV)
    assert unrelated.elements[0].verdict is Verdict.not_supported and "no judge" in unrelated.elements[0].reason
    judge = FakeModelGateway({"verify": [{"verdict": "contradicted", "reason": "evidence forbids it"}]})
    judged = verify_claims(
        [Claim(text="本品可與葡萄柚汁同服", citation_chunk_ids=("c2",))], EV, gateway=judge, judge_model_id="gpt-6-luna"
    )
    assert judged.contradicted and judged.elements[0].reason.startswith("llm:gpt-6-luna")
    sent = judge.calls[0]
    assert sent.purpose == "verify" and sent.json_schema is not None and "chunk=c2" in sent.messages[1].content


def test_judge_output_must_be_a_known_verdict():
    judge = FakeModelGateway({"verify": [{"verdict": "maybe", "reason": ""}]})
    with pytest.raises(ModelOutputInvalid):
        verify_claims(
            [Claim(text="本品可與葡萄柚汁同服", citation_chunk_ids=("c2",))],
            EV,
            gateway=judge,
            judge_model_id="gpt-6-luna",
        )


def test_evidence_stage_never_reports_contradiction_and_fails_structurally_without_evidence():
    vr = verify_evidence("孩童口服 500 mg 如何給予？", EV)
    assert vr.structural_ok and not vr.contradicted
    assert verify_evidence("任何問題", []).structural_ok is False


def test_negation_flip_of_a_contained_statement_is_a_contradiction_not_support():
    ev = [evidence("c3", "研究者不得在未取得知情同意的情況下使用試驗器械。")]
    flipped = verify_claims(
        [Claim(text="研究者在未取得知情同意的情況下使用試驗器械。", citation_chunk_ids=("c3",))], ev
    )
    assert flipped.contradicted and flipped.elements[0].kind is ElementKind.statement
    same = verify_claims(
        [Claim(text="研究者不得在未取得知情同意的情況下使用試驗器械。", citation_chunk_ids=("c3",))], ev
    )
    assert not same.contradicted and not same.unsupported


def test_default_policy_leaves_everything_but_polarity_and_containment_to_the_judge():
    ev = [evidence("c1", LABEL_TEXT := "年齡 6 至 12 歲的孩童：口服，100 mg，一天三次。每日劑量不得超過 300 mg。")]
    judge = FakeModelGateway({"verify": [{"verdict": "supported", "reason": "same dose, same population"}]})
    # an exact numeric match is no longer decided by the rules alone: the judge is consulted once
    numeric = verify_claims(
        [Claim(text="6 至 12 歲孩童口服 100 mg，一天三次", citation_chunk_ids=("c1",))],
        ev,
        gateway=judge,
        judge_model_id="gpt-6-luna",
    )
    assert len(judge.calls) == 1 and numeric.elements[0].kind is ElementKind.statement and not numeric.unsupported
    # a negation-polarity contradiction is decided by the rules without a call
    flipped = verify_claims(
        [Claim(text="每日可超過 300 mg", citation_chunk_ids=("c1",))], ev, gateway=judge, judge_model_id="gpt-6-luna"
    )
    assert flipped.contradicted and len(judge.calls) == 1
    # same-polarity whole-statement containment is decided by the rules without a call
    contained_claim = verify_claims(
        [Claim(text="每日劑量不得超過 300 mg", citation_chunk_ids=("c1",))],
        ev,
        gateway=judge,
        judge_model_id="gpt-6-luna",
    )
    assert not contained_claim.unsupported and not contained_claim.contradicted and len(judge.calls) == 1
    # rules_first keeps the per-element path (numeric match supported by rule, no call)
    legacy = verify_claims(
        [Claim(text="6 至 12 歲孩童口服 100 mg，一天三次", citation_chunk_ids=("c1",))],
        ev,
        gateway=judge,
        judge_model_id="gpt-6-luna",
        policy="rules_first",
    )
    assert len(judge.calls) == 1 and {e.kind for e in legacy.elements} >= {ElementKind.dose, ElementKind.frequency}
    assert LABEL_TEXT
