"""Build `evals/main_set/corpus.json` (main evaluation set, spec-m1) from the probe corpus plus the signed
candidates of DEC-011 whose PDFs are staged and extracted. Every new entry is derived from the candidate
record (licence evidence, provenance) and the extraction record (sha256, byte size, pages); the PII scan runs
`pii-rules-v1` over the norm-v1 page texts. Page text never enters the output.

Candidates are selected by `reviewer_decision == "eligible"` and either a notes marker (default `记录 47`, the
v0.8 batch) or an explicit id list (`--select-ids-file`, one candidate id per line, for later batches).

Usage: python evals/main_set/tools/build_corpus.py --candidates <vX.json> --pages evals/main_set/pages
       --sources evals/main_set/sources_staging [--select-ids-file ids.txt] [--only-keys k1,k2] [--exclude-labels]
       [--verified-at YYYY-MM-DD --batch-note "DEC-011 v1.3/v1.5，决策人 2026-09-28 确认"] [--pii-review file.json]
       --out evals/main_set/corpus.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

import jsonschema  # noqa: E402

from medops.evals.probe.pii import PII_RULESET_VERSION, find_pii_matches  # noqa: E402
from medops.retrieval.lexical.normalization import normalize_text  # noqa: E402

LICENCE_TEMPLATES = {
    "ich": {
        "name_or_summary": "ICH 公共许可（ich.org Legal Mentions / 文内 ICH 公告）：可使用、复制、并入其他作品、改作与分发，须致谢 ICH，排除 ICH/MedDRA 徽标与第三方内容",
        "permitted_scope": "保存、索引、引用、展示；复制与并入其他作品",
        "attribution_required": True,
        "attribution_text": "© ICH（International Council for Harmonisation）；引用时注明 ICH 与文档标识",
        "terms_url": "https://www.ich.org/page/legal-mentions",
    },
    "ema": {
        "name_or_summary": "EMA 网站法律声明：EMA 网页提供的信息与文档为公开内容，可全部或部分复制与分发，须署名来源",
        "permitted_scope": "保存、索引、引用、展示；复制与分发",
        "attribution_required": True,
        "attribution_text": "Source: European Medicines Agency and Heads of Medicines Agencies (GVP)",
        "terms_url": "https://www.ema.europa.eu/en/about-us/about-website/legal-notice",
    },
    "fda": {
        "name_or_summary": "美国联邦政府作品，公共领域（fda.gov Website Policies: not copyrighted, may be reproduced without permission）",
        "permitted_scope": "保存、索引、引用、展示；任意复制与再分发",
        "attribution_required": False,
        "attribution_text": "U.S. Food and Drug Administration（public domain）",
        "terms_url": "https://www.fda.gov/about-fda/about-website/website-policies",
    },
    "meddra": {
        "name_or_summary": "ICH 公共许可（文内「免责声明及版权公告」）：可使用、复制、纳入其他作品、改写、修订、翻译或传播，须始终承认 ICH 版权，排除 MedDRA/ICH 徽标与第三方内容",
        "permitted_scope": "保存、索引、引用、展示；复制与并入其他作品",
        "attribution_required": True,
        "attribution_text": "© ICH（International Council for Harmonisation）；MedDRA® 商标由 ICH 注册；引用时注明 ICH 与文档标识",
        "terms_url": "https://www.ich.org/page/legal-mentions",
    },
    "tfda": {
        "name_or_summary": "政府資料開放授權條款-第1版（OGDL-1.0，與 CC BY 4.0 相容）；仿單經 data.gov.tw 資料集 9117 / TFDA 資料集 39 以開放資料發布",
        "permitted_scope": "保存、索引、引用、展示；重製、散布、公開傳輸、改作，不限目的與時間",
        "attribution_required": True,
        "attribution_text": "資料來源：衛生福利部食品藥物管理署 藥品仿單查詢平台（政府資料開放授權條款第1版）；不主張商標與機關標誌權利",
        "terms_url": "https://data.gov.tw/license",
    },
}


def family(c: dict) -> str:
    p = c["publisher"]
    if p.startswith("International"):
        return "ich"
    if p.startswith("European"):
        return "ema"
    if p.startswith("U.S."):
        return "fda"
    if p.startswith("MedDRA"):
        return "meddra"
    return "tfda"


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].rstrip("-")


FDA_KEYS = {
    "152530": "fda-investigator-safety-reporting-2021",
    "116754": "fda-risk-based-monitoring-2013",
    "88915": "fda-informed-consent-2023",
    "169090": "fda-e6r3-gcp-2025",
    "77765": "fda-investigator-responsibilities-2009",
    "121479": "fda-rbm-qa-2023",
}
MEDDRA_KEYS = (
    ("SMQ", "meddra-smq-intro-guide-25-zh-hans"),
    ("入门指南", "meddra-intro-guide-25-zh-hans"),
    ("更新内容", "meddra-whats-new-25-zh-hans"),
)


def _year(text: str) -> str | None:
    """Year of the document date: a parenthesised or spelled-out date wins over the year inside an EMA document
    number (EMA/198270/2026 must not yield 1982)."""
    m = re.search(r"\(\d{1,2} [A-Za-z]+ ((?:19|20)\d{2})\)|\b\d{1,2} [A-Z][a-z]+ ((?:19|20)\d{2})\b|(?:issued|updated|effective) \d{2}/\d{2}/((?:19|20)\d{2})", text)
    if m:
        return next(g for g in m.groups() if g)
    m = re.search(r"\b((?:19|20)\d{2})\b", text)
    return m.group(1) if m else None


# TFDA guidance / regulation documents of the v1.2 batch: readable keys fixed per candidate id (Chinese titles
# do not slug); the id is stable across candidate-list versions (test_candidate_lists).
TFDA_DOC_KEYS = {
    "cand-0252": "tfda-gpvp-guidance-2014",
    "cand-0253": "tfda-drug-safety-surveillance-regulation",
    "cand-0254": "tfda-psur-format-and-schedule-2005",
    "cand-0255": "tfda-rems-plan-required-items-2023",
    "cand-0256": "tfda-adr-report-acceptance-principles-2013",
    "cand-0257": "tfda-vaccine-ae-report-form-guide-4th-2025",
    "cand-0258": "tfda-gcp-regulation-2020",
    "cand-0259": "tfda-ind-application-guide-2025-12",
    "cand-0260": "tfda-bridging-study-guidance",
    "cand-0261": "tfda-cell-therapy-ct-application-review-2014",
    "cand-0262": "tfda-e-labeling-implementation-schedule-2025",
    "cand-0263": "tfda-otc-label-format-qa-2016",
}


def document_key(c: dict, used: set[str]) -> str:
    """Stable, human-readable keys: ICH code + step/Q&A + year; GVP module/addendum + revision, other EMA
    documents by title; FDA fixed map by media id for the v0.8 batch, otherwise title (+ draft marker) + year;
    MedDRA by document kind; TFDA labels by English product name, else by licence number; other TFDA documents
    by the English part of the title, else by source hash."""
    fam = family(c)
    t = c["title"]
    v = c["version_or_date"]
    if fam == "ich":
        m = re.match(r"ICH ((?:E|M|Q)\d+[A-Z]?(?:\(R\d\))?)", t)
        code = m.group(1).lower().replace("(", "-").replace(")", "") if m else slug(t)[:30]
        step4 = re.search(r"Step 4, (\d{4})", v)
        if step4:
            base = f"ich-{code}-step4-{step4.group(1)}"
        else:
            kind = "qa" if re.search(r"Q&As?|Questions", t + v) else "doc"
            base = f"ich-{code}-{kind}-{_year(v) or 'undated'}"
    elif fam == "ema":
        m = re.search(r"Module ([IVX]+)(?: Addendum ([IVX]+))?", t)
        pp = re.search(r"Considerations ([IVX]+)", t)
        annex = re.search(r"Annex ([IVX]+)", t)
        if m:
            base = f"ema-gvp-module-{m.group(1).lower()}" + (f"-addendum-{m.group(2).lower()}" if m.group(2) else "")
        elif pp:
            base = f"ema-gvp-pp-{pp.group(1).lower()}"
        elif annex and "pharmacovigilance practices" in t:
            base = f"ema-gvp-annex-{annex.group(1).lower()}"
            template = re.search(r"Templates?:\s*(.+)$", t)
            if template:  # Annex II has several template documents; keep them apart by subject
                base += "-" + slug(template.group(1))[:30].rstrip("-")
        else:
            base = "ema-" + slug(t)[:45].rstrip("-")
        rev = re.search(r"Rev\.? ?(\d+)", v)
        base += f"-rev{rev.group(1)}" if rev else ""
        if not (m or pp or annex):
            base += f"-{_year(v)}" if _year(v) else ""
    elif fam == "fda":
        media = re.search(r"/media/(\d+)/", c["pdf_url"]).group(1)
        if media in FDA_KEYS:
            base = FDA_KEYS[media]
        else:
            # drop generic framing ("Guidance for Industry:", FAQ information-sheet preambles, trailing "Guidance for …")
            core = re.sub(
                r"^(guidance for industry|draft guidance|information sheet guidance for [^:]*?\bfrequently asked questions)\s*[:—–-]?\s*",
                "",
                t,
                flags=re.IGNORECASE,
            )
            core = re.split(r"\s*[:—–]\s*|\s+-\s+|\s+Guidance for\b", core, flags=re.IGNORECASE)[0] or t
            suffix = ("-draft" if re.match(r"Draft", v, re.IGNORECASE) else "") + (f"-{_year(v)}" if _year(v) else "")
            base = "fda-" + slug(core)[: 56 - len(suffix)].rstrip("-") + suffix
    elif fam == "meddra":
        base = next(k for marker, k in MEDDRA_KEYS if marker in t)
    elif c["doc_type"] != "label":
        if c["candidate_id"] in TFDA_DOC_KEYS:
            base = TFDA_DOC_KEYS[c["candidate_id"]]
        else:
            en = next((p.split("，")[0] for p in re.findall(r"（([^（）]+)）", t) if re.search(r"[A-Za-z]{3,}", p)), None)
            base = "tfda-" + (slug(en)[:40] if en and slug(en) else "doc-" + re.search(r"sha256 ([0-9a-f]{12})", c["notes"]).group(1))
    else:
        en = None
        for part in re.findall(r"（([^（）]+)）", t):
            if re.search(r"[A-Za-z]{3,}", part):
                en = part.split("，")[0]
                break
        lic = re.search(r"許可證 (\S+?)號", v)
        base = "tfda-label-" + (
            slug(en)[:40] if en and slug(en) else "lic-" + re.sub(r"\D", "", lic.group(1)) if lic else slug(t)[:40]
        )
    base = base.rstrip("-")
    if len(base) > 60:  # corpus schema: document_key <= 64 chars; leave room for a collision suffix
        base = base[:60].rstrip("-")
    key = base
    n = 2
    while key in used:
        key = f"{base}-{n}"
        n += 1
    used.add(key)
    return key


def short_version(c: dict) -> str:
    """<= 80 chars: labels keep the revision date or the PDF metadata date; guidelines keep their version string."""
    v = c["version_or_date"]
    if c["doc_type"] != "label":
        return v[:80]
    m = re.search(r"修訂日期 ([0-9.]+)", v)
    if m:
        return f"修訂日期 {m.group(1)}"[:80]
    m = re.search(r"CreationDate (\d{4})-?(\d{2})-?(\d{2})", v)
    return (f"pdf-meta {m.group(1)}-{m.group(2)}-{m.group(3)}（未见版本行）" if m else v)[:80]


def pii_scan(
    pages_dir: Path, sha: str, pages: int, today: str, candidate_id: str = "", review_file: Path | None = None
) -> dict:
    hits = 0
    for i in range(1, pages + 1):
        text = normalize_text((pages_dir / sha / f"{i}.txt").read_text(encoding="utf-8"))
        hits += len(find_pii_matches(text))
    if hits == 0:
        return {
            "status": "clean",
            "method": "pii-rules-v1 over norm-v1 page text of all pages",
            "ruleset_version": PII_RULESET_VERSION,
            "scanned_at": today,
        }
    review_file = review_file or REPO / "evals/main_set/pii_review_2026-09-21.json"
    review = json.loads(review_file.read_text(encoding="utf-8"))
    accepted = review["false_positives"].get(candidate_id)
    if accepted is None:
        raise SystemExit(f"{candidate_id}: {hits} PII hit(s) without a recorded review; refusing to mark clean")
    rel = review_file.relative_to(REPO) if review_file.is_relative_to(REPO) else review_file
    return {
        "status": "clean",
        "method": f"pii-rules-v1 over norm-v1 page text of all pages; {hits} hit(s) reviewed as institutional mailboxes ({rel})",
        "ruleset_version": PII_RULESET_VERSION,
        "scanned_at": today,
    }


def display_title(c: dict) -> str:
    """FDA drafts must be visibly labelled as drafts wherever the title is shown (decision 2026-09-28, cand-0347)."""
    t = c["title"]
    if family(c) == "fda" and re.match(r"Draft", c["version_or_date"], re.IGNORECASE) and "草案" not in t:
        when = re.search(r"issued (\d{2}/\d{2}/\d{4})|Draft, ([A-Za-z]+ \d{4})", c["version_or_date"])
        stamp = (when.group(1) or when.group(2)) if when else _year(c["version_or_date"]) or ""
        suffix = f"（FDA 草案 {stamp}，Draft / Not for Implementation，非现行指南）"
        room = 300 - len(suffix)  # corpus schema: title <= 300
        return (t if len(t) <= room else t[: room - 1].rstrip() + "…") + suffix
    return t


def build(
    candidates: Path,
    pages_dir: Path,
    sources: Path,
    out: Path,
    *,
    only_keys: set[str] | None,
    exclude_labels: bool,
    select_ids: set[str] | None = None,
    marker: str = "记录 47",
    verified_at: str = "2026-09-21",
    batch_note: str = "DEC-011 v0.8，决策人 2026-09-21 确认",
    pii_review: Path | None = None,
    dataset_version: str = "main-v1-provisional",
    base_corpus: Path | None = None,
) -> dict:
    """`base_corpus` (default: the probe corpus) is the document list new entries are appended to; pass the
    current main-set corpus.json to extend an existing corpus instead of rebuilding it from the probe set."""
    base_path = base_corpus or REPO / "evals/probe/precise_clause/v2/corpus.json"
    probe = json.loads(base_path.read_text(encoding="utf-8"))["documents"]
    cands = json.loads(candidates.read_text(encoding="utf-8"))["candidates"]
    used = {d["document_key"] for d in probe}
    known_hashes = {d["source_hash"] for d in probe}
    today = date.today().isoformat()
    docs = list(probe)
    skipped = []
    for c in cands:
        if c.get("reviewer_decision") != "eligible":
            continue
        if select_ids is not None:
            if c["candidate_id"] not in select_ids:
                continue
        elif marker not in (c.get("notes") or ""):
            continue
        if exclude_labels and c["doc_type"] == "label":
            skipped.append((c["candidate_id"], "label excluded (image-layer check pending)"))
            continue
        sha = re.search(r"sha256 ([0-9a-f]{64})", c["notes"]).group(1)
        if sha in known_hashes:
            skipped.append((c["candidate_id"], "already in the base corpus (same source_hash)"))
            continue
        extraction = pages_dir / sha / "extraction.json"
        if not extraction.is_file():
            skipped.append((c["candidate_id"], "not extracted"))
            continue
        e = json.loads(extraction.read_text(encoding="utf-8"))
        pdf = sources / f"{sha}.pdf"
        if not pdf.is_file() or e["source_hash"] != sha:
            skipped.append((c["candidate_id"], "source missing or hash mismatch"))
            continue
        fam = family(c)
        tpl = LICENCE_TEMPLATES[fam]
        key = document_key(c, used)
        if only_keys and key not in only_keys:
            continue
        docs.append(
            {
                "document_key": key,
                "title": display_title(c),
                "doc_type": c["doc_type"],
                "owner_dept": c["owner_dept"],
                "language": c["language"],
                "source_url": c["pdf_url"],
                "publisher": c["publisher"],
                "license_status": "eligible",
                "license_or_terms": {
                    "name_or_summary": tpl["name_or_summary"],
                    "permitted_scope": tpl["permitted_scope"],
                    "attribution_required": tpl["attribution_required"],
                    "attribution_text": tpl["attribution_text"],
                    "third_party_content_checked": True,
                    "third_party_note": c["third_party_note"],
                    "verified_at": verified_at,
                    "verified_by": "reviewer-01",
                },
                "terms_url": tpl["terms_url"],
                "retrieved_at": c["fetched_at"],
                "version_label": short_version(c),
                "source_hash": sha,
                "byte_size": e["byte_size"],
                "mime": "application/pdf",
                "pages": e["pages"],
                "pii_scan": pii_scan(pages_dir, sha, e["pages"], today, c["candidate_id"], pii_review),
                "notes": f"候选 {c['candidate_id']}（{batch_note}）；原件 main_set/sources/{sha[:12]}…pdf；pypdf {e['extractor_version']} 抽取 {e['pages']} 页，空白页 {[i for i, n in enumerate(e.get('chars_per_page', []), 1) if n == 0]}"
                + ("；" + (c.get("reviewer_note") or "")[:300] if "草案" in (c.get("reviewer_note") or "") else ""),
            }
        )
    fixtures = REPO / "evals/main_set/conflict_fixtures/corpus_fixture.json"
    # fixtures and version fixes are already applied inside an existing corpus.json; re-applying them when
    # extending one would re-append the superseded fixture record and duplicate the fix (record 96)
    if base_corpus is None and fixtures.is_file():
        # synthetic version-conflict fixtures (record 50): only the current records are gold-eligible corpus documents
        known = {d["document_key"] for d in docs}
        for rec in json.loads(fixtures.read_text(encoding="utf-8"))["documents"]:
            if not rec["document_key"].endswith("--synthetic-old") and rec["document_key"] not in known:
                if only_keys and rec["document_key"] not in only_keys:
                    continue
                docs.append(rec)
    # version-label corrections re-published through the M1-11 flow (record 50 §9): same source object, new key/version
    for fix_file in sorted((REPO / "evals/main_set/version_fixes").glob("*.json")) if base_corpus is None else []:
        for rec in json.loads(fix_file.read_text(encoding="utf-8"))["documents"]:
            # a fix either re-labels the same file (same source_hash) or replaces an older file by a newer revision
            target = rec.get("replaces_source_hash", rec["source_hash"])
            clean = {k: v for k, v in rec.items() if k != "replaces_source_hash"}
            docs = [clean if d["source_hash"] == target else d for d in docs]
    corpus = {"dataset_version": dataset_version, "documents": docs}
    schema = json.loads((REPO / "evals/probe/precise_clause/schema/corpus.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(corpus, schema)
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "documents": len(docs),
        "new": len(docs) - len(probe),
        "skipped": skipped,
        "pii_hits": [d["document_key"] for d in docs if d["pii_scan"]["status"] != "clean"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--pages", type=Path, required=True)
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--out", type=Path, default=REPO / "evals/main_set/corpus.json")
    p.add_argument("--only-keys", default=None)
    p.add_argument("--exclude-labels", action="store_true")
    p.add_argument("--select-ids-file", type=Path, default=None, help="one candidate id per line; replaces --marker")
    p.add_argument("--marker", default="记录 47", help="notes substring selecting the batch when no id file is given")
    p.add_argument("--verified-at", default="2026-09-21")
    p.add_argument("--batch-note", default="DEC-011 v0.8，决策人 2026-09-21 确认")
    p.add_argument("--pii-review", type=Path, default=None)
    p.add_argument("--dataset-version", default="main-v1-provisional")
    p.add_argument("--base-corpus", type=Path, default=None, help="extend this corpus.json instead of the probe corpus")
    a = p.parse_args()
    ids = None
    if a.select_ids_file:
        ids = {line.strip() for line in a.select_ids_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    summary = build(
        a.candidates,
        a.pages,
        a.sources,
        a.out,
        only_keys=set(a.only_keys.split(",")) if a.only_keys else None,
        exclude_labels=a.exclude_labels,
        select_ids=ids,
        marker=a.marker,
        verified_at=a.verified_at,
        batch_note=a.batch_note,
        pii_review=a.pii_review,
        dataset_version=a.dataset_version,
        base_corpus=a.base_corpus,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
