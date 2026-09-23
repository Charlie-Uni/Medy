"""M2-08 deterministic rules: exact match, negation polarity, single-value contradiction, identifiers."""

from __future__ import annotations

from medops.domain.verification import ElementKind, Verdict
from medops.verification.rules import contained, judge_elements, negated, overlap_ratio, sentence_around
from tests.unit.harness._fixtures import evidence


def outcomes(claim, *texts):
    ev = [evidence(f"c{i}", t) for i, t in enumerate(texts, 1)]
    return {o.element.kind: o for o in judge_elements(claim, ev)}


def test_exact_dose_match_is_supported_and_names_the_chunk():
    o = outcomes("成人劑量為 100 mg，一天三次", "成人：口服 100 mg，一天三次。")
    assert o[ElementKind.dose].verdict is Verdict.supported and o[ElementKind.dose].evidence_chunk_id == "c1"
    assert o[ElementKind.frequency].verdict is Verdict.supported


def test_single_different_value_in_evidence_is_a_contradiction():
    o = outcomes("建議劑量 100 mg", "本品建議劑量為 200 mg。")
    assert o[ElementKind.dose].verdict is Verdict.contradicted and "dose:200:mass" in o[ElementKind.dose].reason


def test_two_candidate_values_leave_the_rule_undetermined():
    o = outcomes("建議劑量 100 mg", "成人 200 mg；兒童 50 mg。")
    assert o[ElementKind.dose].verdict is None


def test_negation_polarity_mismatch_contradicts_even_when_the_number_matches():
    same = outcomes("每日不得超過 300 mg", "每日不得超過 300 mg。")
    assert same[ElementKind.dose].verdict is Verdict.supported
    flipped = outcomes("每日不得超過 300 mg", "每日可用至 300 mg。")
    assert flipped[ElementKind.dose].verdict is Verdict.contradicted
    assert negated("should not be initiated without approval") and not negated("may be given with food")


def test_identifier_absent_is_not_supported_and_present_is_supported():
    absent = outcomes("依 21 CFR 312.32 應報告", "研究者應在 15 天內報告。")
    assert absent[ElementKind.identifier].verdict is Verdict.not_supported
    present = outcomes("依 21 CFR 312.32 應報告", "21 CFR 312.32 requires sponsors to report.")
    assert present[ElementKind.identifier].verdict is Verdict.supported


def test_population_and_indication_rules():
    pop = outcomes("兒童禁用", "兒童及青少年禁用本品。")
    assert pop[ElementKind.population].verdict is Verdict.supported
    unknown = outcomes("孕婦慎用", "成人每日一次。")
    assert unknown[ElementKind.population].verdict is None
    ind = outcomes("適應症：高血壓", "本品適應症：高血壓、心衰竭。")
    assert ind[ElementKind.indication].verdict is Verdict.supported


def test_sentence_window_and_containment_helpers():
    text = "第一句。不得併用 aliskiren；第三句。"
    start = text.index("aliskiren")
    assert sentence_around(text, start, start + 9) == "不得併用 aliskiren"
    ev = [evidence("c1", "Losartan potassium 禁用於對本項產品任何組成過敏者。")]
    assert contained("禁用於對本項產品任何組成過敏者", ev) == "c1"
    assert contained("完全無關的陳述", ev) is None
    assert overlap_ratio("Losartan 禁用 過敏者", ev[0].text) > 0.8
