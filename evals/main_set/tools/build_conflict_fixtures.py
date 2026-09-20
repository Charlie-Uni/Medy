"""Synthetic version-conflict fixtures for the main evaluation set (spec-m1 v1.0 sections 2 and 5).

Five newly added guideline documents (ICH E7, E12A, E15; GVP Annex I, GVP P.I) are each ingested twice through the
M1-11 publish flow: a synthetic old version (`<key>--synthetic-old`, earlier effective_from, archived on publish) and
the real current version (`<key>`, the only active copy, gold-eligible). The two copies share one source object
(same PDF, administrator-confirmed share), so the text is identical: the fixtures test version status and effective
windows (INV-DATA-03), not content differences, and every sample built on them says so in `notes` and carries
`conflict.synthetic=true`.

    python evals/main_set/tools/build_conflict_fixtures.py

Writes: corpus_candidates/DEC-011-candidates-v1.0.json (v0.9 + 5 candidates), conflict_fixtures/corpus_fixture.json
(loader corpus with the 10 records and the activation dates), and appends the 5 current records to
evals/main_set/corpus.json (validated against the corpus schema). Ingestion commands are in record 50.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_corpus as bc  # noqa: E402
import jsonschema  # noqa: E402

from medops.retrieval.lexical.normalization import normalize_text  # noqa: E402

REPO = bc.REPO
MAIN = REPO / "evals/main_set"
PAGES = MAIN / "pages"
CANDS = REPO / "evals/probe/precise_clause/corpus_candidates"
FIX = MAIN / "conflict_fixtures"
TODAY = "2026-09-21"
OWNER_NOTE = "决策人 2026-09-21 授权实现方决定（“我需要的是结果 你来决定”）：与已签字同族文档同一许可依据；用于 spec-m1 §5 合成冲突 fixture；决策人可在记录 50 否决"

FIXTURES = [
    {
        "key": "ich-e7-step4-1993",
        "cid": "cand-0097",
        "title": "ICH E7: Studies in Support of Special Populations: Geriatrics",
        "dept": "CO",
        "sha": "cbe681cf342eeefb477c1a30770d12798fadcf2d00079faa0aa66047ce4ca330",
        "family": "ich",
        "pdf_url": "https://database.ich.org/sites/default/files/E7_Guideline.pdf",
        "landing_url": "https://www.ich.org/page/efficacy-guidelines",
        "version": "Step 4, 1993-06-24",
        "effective_from": "1993-06-24",
    },
    {
        "key": "ich-e12a-principle-2000",
        "cid": "cand-0098",
        "title": "ICH E12A: Principles for Clinical Evaluation of New Antihypertensive Drugs (ICH consensus principle document)",
        "dept": "CO",
        "sha": "d09627c2d02dc3c6675be445232a7312e0aa295f6b1748da68fc9d771405a9ac",
        "family": "ich",
        "pdf_url": "https://database.ich.org/sites/default/files/E12_Guideline.pdf",
        "landing_url": "https://www.ich.org/page/efficacy-guidelines",
        "version": "Principle document, 2000-03-02",
        "effective_from": "2000-03-02",
    },
    {
        "key": "ich-e15-step4-2007",
        "cid": "cand-0099",
        "title": "ICH E15: Definitions for Genomic Biomarkers, Pharmacogenomics, Pharmacogenetics, Genomic Data and Sample Coding Categories",
        "dept": "CO",
        "sha": "40516566c939436147ade1b076a2e46d716755d3062c1102732ae394cf8e02fc",
        "family": "ich",
        "pdf_url": "https://database.ich.org/sites/default/files/E15_Guideline.pdf",
        "landing_url": "https://www.ich.org/page/efficacy-guidelines",
        "version": "Step 4, 2007-11-01",
        "effective_from": "2007-11-01",
    },
    {
        "key": "ema-gvp-annex-i-rev4",
        "cid": "cand-0100",
        "title": "Guideline on good pharmacovigilance practices (GVP) – Annex I – Definitions (Rev 4)",
        "dept": "PV",
        "sha": "93435355242b002f23e966d1f08454614c405ce4e286e6979b5de44692bab4fe",
        "family": "ema",
        "pdf_url": "https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-good-pharmacovigilance-practices-annex-i-definitions-rev-4_en.pdf",
        "landing_url": "https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp",
        "version": "EMA/876333/2011 Rev 4 (2017-10-09)",
        "effective_from": "2017-10-09",
    },
    {
        "key": "ema-gvp-pp-i",
        "cid": "cand-0101",
        "title": "Guideline on good pharmacovigilance practices (GVP) – Product- or Population-Specific Considerations I: Vaccines for prophylaxis against infectious diseases",
        "dept": "PV",
        "sha": "0d68ef884e7293e1ef0fb09fbdbc23f646948c4c9627401336ff98d47886c412",
        "family": "ema",
        "pdf_url": "https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-good-pharmacovigilance-practices-gvp-product-or-population-specific-considerations-i-vaccines-prophylaxis-against-infectious-diseases_en.pdf",
        "landing_url": "https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp",
        "version": "EMA/488220/2012 Corr (2013-12-09)",
        "effective_from": "2013-12-09",
    },
]
TEMPLATE_CANDIDATE = {"ich": "cand-0050", "ema": "cand-0065"}
SYNTHETIC_SUFFIX = "--synthetic-old"


def old_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return d.replace(year=d.year - 2).isoformat()


def first_pages_notice(sha: str) -> str | None:
    text = " ".join(normalize_text((PAGES / sha / f"{p}.txt").read_text(encoding="utf-8")) for p in (1, 2))
    m = re.search(r"(©[^.]{0,160}\.\s*Reproduction is authorised provided the source is acknowledged\.)", text)
    if m:
        return m.group(1)
    m = re.search(r"(This document is protected by copyright[^.]*\.)", text)
    return m.group(1) if m else None


def main() -> int:
    v09 = json.loads((CANDS / "DEC-011-candidates-v0.9.json").read_text(encoding="utf-8"))
    templates = {c["candidate_id"]: c for c in v09["candidates"]}
    corpus = (
        json.loads(bc.CORPUS_OUT.read_text(encoding="utf-8"))
        if hasattr(bc, "CORPUS_OUT")
        else json.loads((MAIN / "corpus.json").read_text(encoding="utf-8"))
    )
    existing_keys = {d["document_key"] for d in corpus["documents"]}
    existing_hashes = {d["source_hash"] for d in corpus["documents"]}
    new_candidates, fixture_records, corpus_additions = [], [], []
    for f in FIXTURES:
        e = json.loads((PAGES / f["sha"] / "extraction.json").read_text(encoding="utf-8"))
        assert e["source_hash"] == f["sha"]
        tpl_c = templates[TEMPLATE_CANDIDATE[f["family"]]]
        tpl = bc.LICENCE_TEMPLATES[f["family"]]
        notice = first_pages_notice(f["sha"])
        evidence = [tpl_c["license_evidence"][0]]
        if notice:
            evidence.append(
                {"url": f["pdf_url"], "locator": f"PDF 第 1 页版权声明（{TODAY} pypdf 抽取）", "quote": notice}
            )
        blanks = [i for i, n in enumerate(e.get("chars_per_page", []), 1) if n == 0]
        new_candidates.append(
            {
                "candidate_id": f["cid"],
                "title": f["title"],
                "publisher": tpl_c["publisher"],
                "language": "en",
                "doc_type": "guideline",
                "owner_dept": f["dept"],
                "landing_url": f["landing_url"],
                "pdf_url": f["pdf_url"],
                "version_or_date": f["version"],
                "registry_id": None,
                "license_status": "eligible",
                "license_evidence": evidence,
                "third_party_note": tpl_c["third_party_note"],
                "reasoning": f"{'ICH 公共许可' if f['family'] == 'ich' else 'EMA 法律声明允许署名复制分发'}（与已签字的同族文档同一依据）；{f['dept']} 部门检索需求；spec-m1 §5 合成冲突 fixture（同一 PDF 以旧版/现行两个 document_key 入库，旧版归档）；{e['pages']} 页文本层完整。",
                "fetch_verified": True,
                "fetched_at": TODAY,
                "reviewer_decision": "eligible",
                "reviewer_note": OWNER_NOTE,
                "notes": f"{TODAY} 下载 sha256 {f['sha']}，{e['byte_size']} 字节，{e['pages']} 页；文内版权/Legal notice: {'有' if notice else '无（依据站点法律声明）'}。M1-20 主评测集合成冲突 fixture（记录 50）。",
            }
        )
        base = {
            "title": f["title"],
            "doc_type": "guideline",
            "owner_dept": f["dept"],
            "language": "en",
            "source_url": f["pdf_url"],
            "publisher": tpl_c["publisher"],
            "license_status": "eligible",
            "license_or_terms": {
                "name_or_summary": tpl["name_or_summary"],
                "permitted_scope": tpl["permitted_scope"],
                "attribution_required": tpl["attribution_required"],
                "attribution_text": tpl["attribution_text"],
                "third_party_content_checked": True,
                "third_party_note": tpl_c["third_party_note"],
                "verified_at": TODAY,
                "verified_by": "reviewer-01",
            },
            "terms_url": tpl["terms_url"],
            "retrieved_at": TODAY,
            "source_hash": f["sha"],
            "byte_size": e["byte_size"],
            "mime": "application/pdf",
            "pages": e["pages"],
            "pii_scan": bc.pii_scan(PAGES, f["sha"], e["pages"], TODAY, f["cid"]),
        }
        current = {
            "document_key": f["key"],
            **base,
            "version_label": f["version"],
            "notes": (
                f"候选 {f['cid']}（DEC-011 v1.0，决策人授权实现方决定，记录 50）；合成冲突 fixture：同一 PDF 以两个 document_key 入库，"
                f"旧版 {f['key']}{SYNTHETIC_SUFFIX}（effective_from {old_date(f['effective_from'])}）在发布本版时归档，正文与本版相同；"
                f"原件 main_set/sources/{f['sha'][:12]}…pdf；pypdf {e['extractor_version']} 抽取 {e['pages']} 页，空白页 {blanks}"
            ),
        }
        synthetic_old = {
            "document_key": f["key"] + SYNTHETIC_SUFFIX,
            **base,
            "version_label": f"synthetic-old（合成旧版，正文与 {f['version']} 相同）"[:80],
            "notes": f"合成旧版（spec-m1 §5）：与 {f['key']} 共用同一源对象，仅用于版本冲突评测；不可作为 gold；发布现行版时归档（记录 50）",
        }
        fixture_records.append(
            {
                "document_key": f["key"],
                "synthetic_old_key": synthetic_old["document_key"],
                "source_hash": f["sha"],
                "effective_from_old": old_date(f["effective_from"]),
                "effective_from_current": f["effective_from"],
                "current": current,
                "synthetic_old": synthetic_old,
            }
        )
        if f["key"] not in existing_keys:
            assert f["sha"] not in existing_hashes, f["key"]
            corpus_additions.append(current)
    v10 = {
        **v09,
        "candidate_list_version": "v1.0",
        "compiled_at": TODAY,
        "compiled_by": "ADR-0003 Claude Fable 5.1（承接 v0.9；新增 5 份合成冲突 fixture 文档，决策人授权实现方决定）",
        "candidates": v09["candidates"] + new_candidates,
    }
    (CANDS / "DEC-011-candidates-v1.0.json").write_text(
        json.dumps(v10, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    loader_corpus = {
        "dataset_version": "main-v1-provisional",
        "purpose": "loader input for the synthetic version-conflict fixtures (spec-m1 §5); the eval corpus lists only the current records",
        "documents": [r["synthetic_old"] for r in fixture_records] + [r["current"] for r in fixture_records],
    }
    (FIX / "corpus_fixture.json").write_text(
        json.dumps(loader_corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (FIX / "fixtures.json").write_text(
        json.dumps(
            {
                "created_at": TODAY,
                "rule": "spec-m1 v1.0 §5：合成冲突——同一文档以两个 document_key、不同 version_label 与 effective_from 入库并归档旧版；样本 conflict.synthetic=true",
                "fixtures": [
                    {k: v for k, v in r.items() if k not in ("current", "synthetic_old")} for r in fixture_records
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if corpus_additions:
        corpus["documents"].extend(corpus_additions)
        schema = json.loads((REPO / "evals/probe/precise_clause/schema/corpus.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(corpus, schema)
        (MAIN / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"candidates v1.0: {len(v10['candidates'])}; fixtures: {len(fixture_records)}; corpus additions: {len(corpus_additions)} -> corpus {len(corpus['documents'])} documents"
    )
    for r in fixture_records:
        print(
            f"  {r['document_key']}: old {r['effective_from_old']} -> current {r['effective_from_current']}; pii {r['current']['pii_scan']['status']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
