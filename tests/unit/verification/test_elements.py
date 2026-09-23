"""M2-07: deterministic key-element extraction on zh-Hant / zh-Hans / en clauses."""

from __future__ import annotations

from medops.domain.verification import ElementKind
from medops.verification.elements import extract


def canon(text, kind=None):
    return [e.canonical for e in extract(text) if kind is None or e.kind is kind]


def test_doses_with_unit_conversion_and_ranges():
    assert canon("口服，100 mg，一天三次；或 300 mg 當作一個單一劑量", ElementKind.dose) == [
        "dose:100:mass",
        "dose:300:mass",
    ]
    assert canon("0.5 g twice daily", ElementKind.dose) == ["dose:500:mass"]
    assert canon("10 mcg/kg once daily", ElementKind.dose) == ["dose:0.01:mass_per_kg"]
    assert canon("1,500-1,749 克", ElementKind.dose) == ["dose:1.5e+06-1.749e+06:mass"]
    assert canon("GFR<60 mL/min/1.73 m²", ElementKind.dose) == []  # a measurement rate, not a dose
    assert canon("5 % 葡萄糖 250 mL", ElementKind.dose) == ["dose:5:percent", "dose:250:volume"]


def test_frequencies_zh_and_en_and_priority_over_time_windows():
    els = extract("一天三次，每 8 小時一次；bid 亦可")
    assert [e.canonical for e in els if e.kind is ElementKind.frequency] == ["freq:3/day", "freq:3/day", "freq:2/day"]
    assert not [e for e in els if e.kind is ElementKind.time_window]  # 一天 inside 一天三次 is not a window
    assert canon("three times a day for 7 days", ElementKind.frequency) == ["freq:3/day"]
    assert canon("three times a day for 7 days", ElementKind.time_window) == ["time:7:d"]
    assert canon("every 12 hours; once weekly", ElementKind.frequency) == ["freq:2/day", "freq:1/week"]


def test_time_windows_zh_en_with_working_days():
    assert canon("首次獲知後 15 calendar days 內；no later than 10 working days", ElementKind.time_window) == [
        "time:15:d",
        "time:10:wd",
    ]
    assert canon("大約在治療 48 小時之後", ElementKind.time_window) == ["time:48:h"]
    assert canon("14 天內完成", ElementKind.time_window) == ["time:14:d"]
    assert canon("within two weeks", ElementKind.time_window) == []  # words are out of scope for v1 (recorded)


def test_identifiers_are_normalized():
    ids = canon(
        "見 21 CFR 312.32(c)(1)(i) 及 ICH E6(R3)、E11(R1) 第 2.5.1 節、Article 23(1)、衛署藥製字第 012345 號",
        ElementKind.identifier,
    )
    assert "id:21 cfr 312.32(c)(1)(i)" in ids
    assert "id:ich e6(r3)" in ids and "id:e11(r1)" in ids
    assert "id:第 2.5.1 節" in ids and "id:article 23(1)" in ids
    assert "id:衛署藥製字第 012345 號" in ids


def test_population_and_indication_tags():
    assert canon("6至12歲兒童治療贅瘤疾病引起的高尿酸血症", ElementKind.population) == ["pop:pediatric"]
    assert canon("elderly patients with renal impairment", ElementKind.population) == [
        "pop:elderly",
        "pop:renal_impairment",
    ]
    assert canon("適應症：原發性高血壓。", ElementKind.indication) == ["ind:原發性高血壓"]
    assert canon("indicated for the treatment of hypertension in adults", ElementKind.indication)[0].startswith("ind:")


def test_elements_do_not_overlap_and_keep_positions():
    els = extract("成人每日 100 mg，一天三次")
    spans = [(e.start, e.end) for e in els]
    assert spans == sorted(spans)
    for (_s1, e1), (s2, _e2) in zip(spans, spans[1:], strict=False):
        assert e1 <= s2
