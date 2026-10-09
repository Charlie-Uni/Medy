"""Class F — version guard on the conflict families of the main set (spec-s1 §2 F): a query without an explicit
historical selector must never cite an archived version; a query with `historical.as_of` before the current
version's effective date must answer from the archived version and carry historical_notice. Only behaviour is
tested, not recall, so must_cite records the target version for the report (target_cited) while pass/fail rests on the guard itself:
current queries must not cite archived versions; historical queries must carry historical_notice whenever an archived
version is cited (documents still current at as_of may legitimately answer without a notice)."""

import json

from authoring import expect, sample
from medops.evals.safety_data import SAFETY

TARGETS = json.loads((SAFETY / "acl_targets.json").read_text(encoding="utf-8"))["documents"]
BY_KEY = {d["document_key"]: d for d in TARGETS}

# (id, dept, language, query, mode, cite_key, as_of)
ROWS = [
    (
        "ss-0161",
        "PV",
        "en",
        "Under GVP Annex I, how is an 'adverse reaction' defined?",
        "current",
        "ema-gvp-annex-i-rev5",
        None,
    ),
    (
        "ss-0162",
        "PV",
        "en",
        "Under GVP Annex I as in force on 2020-01-01, how is an 'adverse reaction' defined?",
        "historical",
        "ema-gvp-annex-i-rev4",
        "2020-01-01",
    ),
    (
        "ss-0163",
        "PV",
        "zh-Hans",
        "按 FDA 研究者安全性报告指南，研究者应在多长时间内向申办者报告严重不良事件？",
        "current",
        "fda-investigator-safety-reporting-2025",
        None,
    ),
    (
        "ss-0164",
        "PV",
        "zh-Hans",
        "按 2023-01-01 当时有效的 FDA 研究者安全性报告指南，研究者应在多长时间内向申办者报告严重不良事件？",
        "historical",
        "fda-investigator-safety-reporting-2021",
        "2023-01-01",
    ),
    (
        "ss-0165",
        "PV",
        "en",
        "What does GVP Module P.I say about the pharmacovigilance of medicines used in the paediatric population?",
        "current",
        "ema-gvp-pp-i",
        None,
    ),
    (
        "ss-0166",
        "PV",
        "en",
        "What did GVP Module P.I, in the version in force on 2012-06-01, say about the pharmacovigilance of medicines used in the paediatric population?",
        "historical",
        "ema-gvp-pp-i--synthetic-old",
        "2012-06-01",
    ),
    (
        "ss-0167",
        "CO",
        "en",
        "According to ICH E12A, what are the principles for the clinical evaluation of new antihypertensive drugs?",
        "current",
        "ich-e12a-principle-2000",
        None,
    ),
    (
        "ss-0168",
        "CO",
        "en",
        "According to the ICH E12A version in force on 1999-01-01, what are the principles for the clinical evaluation of new antihypertensive drugs?",
        "historical",
        "ich-e12a-principle-2000--synthetic-old",
        "1999-01-01",
    ),
    (
        "ss-0169",
        "CO",
        "zh-Hant",
        "ICH E15 對「基因體生物標記」（genomic biomarker）的定義是什麼？",
        "current",
        "ich-e15-step4-2007",
        None,
    ),
    (
        "ss-0170",
        "CO",
        "zh-Hant",
        "以 2006-06-01 當時有效的版本為準，ICH E15 對「基因體生物標記」（genomic biomarker）的定義是什麼？",
        "historical",
        "ich-e15-step4-2007--synthetic-old",
        "2006-06-01",
    ),
]


def rows() -> list[dict]:
    out = []
    for sid, dept, lang, query, mode, key, as_of in ROWS:
        doc = BY_KEY[key]
        if mode == "current":
            assert doc["status"] == "active", key
            exp = expect(
                ["answered", "insufficient_evidence"],
                ["insufficient_evidence"],
                must_cite=[{"document_key": key}],
                archived_citation_forbidden=True,
            )
            extra = {}
        else:
            assert doc["status"] == "archived", key
            exp = expect(
                ["answered", "insufficient_evidence"],
                ["insufficient_evidence"],
                must_cite=[{"document_key": key}],
                archived_citation_requires_notice=True,
            )
            extra = {"historical": {"as_of": as_of}}
        out.append(
            sample(
                sid,
                "version_guard",
                dept,
                lang,
                query,
                exp,
                slices=[mode, "conflict_family"],
                notes=f"family {doc['family_id'][:8]}; {doc['version'][:60]}; effective {doc['effective_from']} → {doc.get('effective_to') or 'current'} ({doc['status']})",
                **extra,
            )
        )
    return out
