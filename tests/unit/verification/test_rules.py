"""M2-08 deterministic rules: exact match, negation polarity, single-value contradiction, identifiers."""

from __future__ import annotations

from medops.domain.verification import ElementKind, Verdict
from medops.verification.rules import (
    best_overlap,
    clause_around,
    compare_polarity,
    contained,
    judge_elements,
    negated,
    overlap_ratio,
    polarity,
    polarity_relation,
    sentence_around,
)
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
    paraphrased = outcomes("每日不得超過 300 mg", "每日可用至 300 mg。")
    assert paraphrased[ElementKind.dose].verdict is Verdict.supported  # a limit phrased two ways (v2)
    flipped = outcomes("每日不得超過 300 mg", "每日應超過 300 mg。")
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
    assert contained("禁用於對本項產品任何組成過敏者", ev) == ("c1", "same")
    assert contained("完全無關的陳述", ev) is None
    assert overlap_ratio("Losartan 禁用 過敏者", ev[0].text) > 0.8


def test_containment_and_overlap_carry_negation_polarity():
    ev = [evidence("c1", "第一句。每日劑量不得超過 300 mg。第三句。")]
    assert contained("超過 300 mg", ev) == ("c1", "opposite")  # crossing the limit the evidence sets
    assert contained("不得超過 300 mg", ev) == ("c1", "same")
    ratio, chunk, relation = best_overlap("每日劑量可超過 300 mg", ev)
    assert chunk == "c1" and ratio > 0.6 and relation == "opposite"


def test_bound_phrases_are_limits_not_negations():
    # the live run's dominant false contradiction: 上限 X paraphrases 不得超過 X (record 54 §3)
    same = outcomes("每日劑量上限為 10 mg", "腎功能不全病人每日劑量不得超過 10 mg。")
    assert same[ElementKind.dose].verdict is Verdict.supported
    lower = outcomes("應至少 24 小時前相互通知", "發布前應不少於 24 小時相互通知。")
    assert lower[ElementKind.time_window].verdict is Verdict.supported
    lead = outcomes("至少提前 24 小時通知", "不得晚於 24 小時前通知。")
    assert lead[ElementKind.time_window].verdict is None  # lead-time phrasing: bound direction is ambiguous
    plain = outcomes("每日劑量為 10 mg", "每日劑量不得超過 10 mg。")
    assert plain[ElementKind.dose].verdict is None  # a plain value against a limit: the judge decides
    assert "unclear" in plain[ElementKind.dose].reason
    crossing = outcomes("每日劑量可超過 10 mg", "每日劑量不得超過 10 mg。")
    assert crossing[ElementKind.dose].verdict is Verdict.contradicted
    assert compare_polarity("最遲 30 天內提交", "not later than 30 days") == "same"
    assert compare_polarity("上限 10 mg", "至少 10 mg") == "opposite"
    assert polarity("不得超過 300 mg").negations == 0 and polarity("不得使用").negations == 1


def test_legal_bound_phrasings_are_limits_too():
    # support-rules-v3: the v2 full run's last four rule contradictions (record 54 §3.5) were "in no event later than"
    # (counted as a negation plus an exceed) and 儘早於 (matched as 早於, an exceed) against no later than / 最早
    assert compare_polarity("no later than 10 working days", "in no event later than 10 working days after") == "same"
    assert compare_polarity("最迟不得超过10个工作日", "in no case later than 10 working days") == "same"
    assert compare_polarity("最早可於心肌梗塞後12小時開始", "可儘早於心肌梗塞12小時後即開始進行治療") == "same"
    assert compare_polarity("as early as 12 hours after", "no earlier than 12 hours after") == "same"
    assert polarity("in no event later than 15 calendar days").negations == 0
    # crossing a limit is still opposite to the limit
    assert compare_polarity("later than 10 working days", "in no event later than 10 working days") == "opposite"
    assert compare_polarity("早於 12 小時", "儘早於 12 小時後開始") == "opposite"
    reported = outcomes(
        "The report is due no later than 10 working days after the effect.",
        "A report of a UADE is due as soon as possible, but in no event later than 10 working days after the effect.",
    )
    assert reported[ElementKind.time_window].verdict is Verdict.supported


def test_indication_containment_respects_negation_polarity():
    ev = [evidence("c1", "Losartan potassium 禁用於對本項產品任何組成過敏者。")]
    flipped = judge_elements("Losartan potassium 用於對本項產品任何組成過敏者。", ev)
    assert [o.verdict for o in flipped if o.element.kind is ElementKind.indication] == [Verdict.contradicted]
    ev2 = [evidence("c2", "Losartan potassium 用於治療高血壓及心衰竭。")]
    same = judge_elements("Losartan potassium 用於治療高血壓。", ev2)
    assert [o.verdict for o in same if o.element.kind is ElementKind.indication] == [Verdict.supported]


def test_polarity_is_compared_on_the_clause_not_the_whole_sentence():
    # record 54 §3.2: unrelated negation cues in the same evidence sentence flipped the polarity of a matching value
    ppi = outcomes(
        "低血鎂通報顯示病人至少使用 PPI 3 個月後出現反應。",
        "低血鎂症曾有通報案件顯示,當長期使用PPI類成分藥品(至少使用3個月,大部分在使用1年以上),可能出現罕見低血鎂之不良反應,可能無症狀或嚴重之不良反應症狀。",
    )
    assert ppi[ElementKind.time_window].verdict is not Verdict.contradicted  # clause agrees, sentence has 無: unclear
    herbal = outcomes(
        "传统药用年限至少 30 年，其中至少 15 年在欧盟。",
        "the product proves not to be harmful in the specified conditions of use and the efficacy is plausible on the basis of long-standing use for a period of at least 30 years, including at least 15 years within the Union.",
    )
    assert herbal[ElementKind.time_window].verdict is not Verdict.contradicted
    notice = outcomes(
        "发布安全公告前应至少提前 24 小时相互通知。",
        "they shall inform each other not later than 24 hours in advance, except where urgent public announcements are required.",
    )
    assert notice[ElementKind.time_window].verdict is not Verdict.contradicted
    text = "第一句，不得併用 aliskiren，第三句。"
    start = text.index("aliskiren")
    assert clause_around(text, start, start + 9) == "不得併用 aliskiren"
    # a negation inside the element's own clause, with the sentence agreeing, still contradicts
    real = outcomes("每日 300 mg", "兒童不得使用 300 mg。")
    assert real[ElementKind.dose].verdict is Verdict.contradicted
    # clause and sentence disagree -> unclear, never a rule verdict
    assert polarity_relation("每日 300 mg", (2, 8), "可能無症狀，每日 300 mg。", (6, 12)) == "unclear"


def test_term_elements_never_contradict_on_polarity_alone():
    # record 54 §3.2 (ms-0018): the population term appears inside a negated predicate about another group
    out = outcomes(
        "嚴重腎功能不全病人每日劑量上限為 10 mg",
        "輕度至中度肝或腎功能不全的病人通常不需要調整劑量。嚴重腎功能不全病人每日劑量不可超過 10 mg。",
    )
    assert out[ElementKind.dose].verdict is Verdict.supported
    assert out[ElementKind.population].verdict is not Verdict.contradicted
    only_negated = outcomes("腎功能不全病人使用本品", "腎功能不全病人不得使用本品。")
    assert only_negated[ElementKind.population].verdict is None  # the judge decides, not the rule
