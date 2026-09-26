"""Build the versioned medical glossary of ADR-0008 from (1) the Taiwan FDA drug-licence open dataset and
(2) curated abbreviations verified against the corpus page texts. Output: `glossary-<date>-<sha12>.json`
(the `Glossary` structure of medops.retrieval.rewrite) plus a provenance file naming the snapshot, licence,
counts and every rejected entry. Page text never enters the output; only names, synonyms and page numbers.

Usage: python evals/glossary/tools/build_glossary.py --tfda <36_2.csv.zip> --pages <pages dir>
       --corpus evals/probe/precise_clause/v2/corpus.json --out evals/glossary [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from medops.core.canonical import canonical_json  # noqa: E402
from medops.retrieval.lexical.normalization import normalize_text  # noqa: E402
from medops.retrieval.rewrite import Glossary, GlossaryEntry  # noqa: E402

TFDA_URL = "https://data.fda.gov.tw/data/opendata/export/36/csv"
TFDA_DATASET = "全部藥品許可證資料集（衛生福利部食品藥物管理署）"
TFDA_LICENCE = "政府資料開放授權條款－第1版（相容 CC BY 4.0）；署名：衛生福利部食品藥物管理署"
MAX_SYNONYMS = 5


def load_pages(pages_dir: Path, corpus: dict) -> dict[str, dict[int, str]]:
    """document_key -> {page: normalised text}; only documents present locally."""
    out: dict[str, dict[int, str]] = {}
    for doc in corpus["documents"]:
        d = pages_dir / doc["source_hash"]
        if not d.is_dir():
            continue
        out[doc["document_key"]] = {
            int(f.stem): normalize_text(f.read_text(encoding="utf-8")) for f in d.glob("*.txt") if f.stem.isdigit()
        }
    return out


def read_tfda(zip_path: Path) -> tuple[list[dict[str, str]], str]:
    with zipfile.ZipFile(zip_path) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name)
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows, hashlib.sha256(raw).hexdigest()


def _clean(value: str) -> str:
    return normalize_text(value.replace("　", " ")).strip()


def _distinct(term: str, candidates: list[str]) -> list[str]:
    """Synonyms distinct from the term and from each other (case-insensitive), capped, order kept."""
    out: list[str] = []
    seen = {term.lower()}
    for c in candidates:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out[:MAX_SYNONYMS]


def _present(term: str, pages: dict[str, dict[int, str]]) -> list[tuple[str, int]]:
    if len(term) < 2:
        return []
    lower = term.lower()
    hits = []
    for key, by_page in pages.items():
        for page, text in sorted(by_page.items()):
            if lower in text.lower():
                hits.append((key, page))
                break
    return hits


_LICENCE_NO = re.compile(r"(?:內衛|衛署|衛部)[\u4e00-\u9fff]{1,6}字第\d{3,8}號")  # national licence numbers


def licence_numbers_in_pages(pages: dict[str, dict[int, str]]) -> dict[str, list[tuple[str, int]]]:
    """Every licence number (e.g. 衛署藥製字第048564號, spaces removed) found in the corpus pages -> evidence.
    Brand-name presence alone is not used: many licensed "brand names" are common nouns (葡萄糖, 注射劑, 胃液)
    that would match unrelated text."""
    found: dict[str, list[tuple[str, int]]] = {}
    for doc_key, by_page in pages.items():
        for page, text in sorted(by_page.items()):
            for m in _LICENCE_NO.finditer(re.sub(r"\s+", "", text)):
                found.setdefault(m.group(0), []).append((doc_key, page))
    return found


def tfda_entries(rows: list[dict[str, str]], pages: dict[str, dict[int, str]]) -> tuple[list[dict], dict]:
    """Brand (中文品名) -> English product name + ingredient names, for licences whose number occurs in the
    corpus, plus the reverse English -> brand entries. Withdrawn licences are kept (labels may predate withdrawal)."""
    entries: list[dict] = []
    seen: set[str] = set()
    anchors = licence_numbers_in_pages(pages)
    stats = {"rows": len(rows), "licence_numbers_in_pages": len(anchors), "licences_in_corpus": 0, "entries": 0}
    for row in rows:
        brand = _clean(row.get("中文品名", ""))
        english = _clean(row.get("英文品名", ""))
        ingredients = [_clean(x) for x in (row.get("主成分略述") or "").split(";;") if _clean(x)]
        if not brand or brand in seen:
            continue
        evidence = anchors.get(re.sub(r"\s+", "", row.get("許可證字號", "")), [])
        if not evidence:
            continue
        seen.add(brand)
        stats["licences_in_corpus"] += 1
        synonyms = _distinct(brand, [english, *ingredients])
        if not synonyms:
            continue
        entries.append(
            {
                "term": brand,
                "synonyms": synonyms,
                "kind": "brand",
                "source": "tfda",
                "licence_no": _clean(row.get("許可證字號", "")),
                "status": _clean(row.get("註銷狀態", "")),
                "evidence": [{"document_key": k, "page": p} for k, p in evidence[:2]],
            }
        )
        if english and english.lower() != brand.lower():
            entries.append(
                {
                    "term": english,
                    "synonyms": _distinct(english, [brand, *ingredients]),
                    "kind": "brand",
                    "source": "tfda",
                    "licence_no": _clean(row.get("許可證字號", "")),
                    "status": _clean(row.get("註銷狀態", "")),
                    "evidence": [{"document_key": k, "page": p} for k, p in evidence[:2]],
                }
            )
    stats["entries"] = len(entries)
    return entries, stats


def abbreviation_entries(curated: dict, pages: dict[str, dict[int, str]]) -> tuple[list[dict], list[dict]]:
    """Keep an abbreviation only when it and its expansion occur on the same page of some document."""
    kept: list[dict] = []
    rejected: list[dict] = []
    for item in curated["entries"]:
        abbr, expansion = item["term"], _clean(item["expansion"])
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(abbr)}(?![A-Za-z0-9])")
        evidence = []
        for key, by_page in pages.items():
            for page, text in sorted(by_page.items()):
                if expansion.lower() in text.lower() and pattern.search(text):
                    evidence.append({"document_key": key, "page": page})
                    break
        if evidence:
            kept.append(
                {
                    "term": abbr,
                    "synonyms": [expansion],
                    "kind": "abbreviation",
                    "source": "corpus",
                    "evidence": evidence[:3],
                }
            )
        else:
            rejected.append(
                {
                    "term": abbr,
                    "expansion": expansion,
                    "reason": "abbreviation and expansion never co-occur on a corpus page",
                }
            )
    return kept, rejected


MIN_CJK_TERM = 3  # a CJK glossary term is matched as a substring: two characters would fire on unrelated text


def concept_entries(concepts: dict, pages: dict[str, dict[int, str]]) -> tuple[list[dict], list[dict]]:
    """Chinese concept terms -> English terms (record 93): each English term must occur verbatim on a cited corpus
    page (mechanical); the Chinese renderings come from the concepts file (model translation, spot-checked by the
    decision-maker per ADR-0008). zh-Hans and zh-Hant become separate entries when they differ, and several English
    forms of one Chinese term (singular / plural, British / American spelling) share one entry as synonyms."""
    by_zh: dict[str, dict] = {}
    rejected: list[dict] = []
    for item in concepts["terms"]:
        if not item.get("keep", True):
            rejected.append({"term": item["en"], "reason": "translator marked it as not a term"})
            continue
        english = _clean(item["en"])
        evidence = []
        for ev in item.get("evidence", []):
            text = pages.get(ev["document_key"], {}).get(int(ev["page"]), "")
            if english.lower() in text.lower():
                evidence.append({"document_key": ev["document_key"], "page": int(ev["page"])})
        if not evidence:
            rejected.append({"term": english, "reason": "English term not found on any cited corpus page"})
            continue
        for zh in dict.fromkeys(_clean(item.get(k, "")) for k in ("zh_hans", "zh_hant")):
            if not zh or zh.lower() == english.lower():
                continue
            if len(zh) < MIN_CJK_TERM:
                rejected.append({"term": zh, "reason": f"shorter than {MIN_CJK_TERM} characters (substring matching)"})
                continue
            entry = by_zh.setdefault(
                zh,
                {
                    "term": zh,
                    "synonyms": [],
                    "kind": "concept",
                    "source": "corpus-terms+model-translation",
                    "evidence": [],
                },
            )
            if english not in entry["synonyms"] and len(entry["synonyms"]) < MAX_SYNONYMS:
                entry["synonyms"].append(english)
            for ev in evidence:
                if ev not in entry["evidence"] and len(entry["evidence"]) < 3:
                    entry["evidence"].append(ev)
    return list(by_zh.values()), rejected


def build(
    *,
    tfda_zip: Path,
    pages_dir: Path,
    corpus_path: Path,
    out_dir: Path,
    built_on: date,
    concepts_path: Path | None = None,
) -> dict:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    pages = load_pages(pages_dir, corpus)
    if not pages:
        raise SystemExit("no local page texts found; the builder needs the extracted pages")
    rows, tfda_sha = read_tfda(tfda_zip)
    curated = json.loads((REPO / "evals/glossary/sources/abbreviations_curated.json").read_text(encoding="utf-8"))
    tfda, tfda_stats = tfda_entries(rows, pages)
    abbr, rejected = abbreviation_entries(curated, pages)
    concepts, concept_rejected = ([], [])
    concepts_meta: dict = {}
    if concepts_path is not None:
        concepts_doc = json.loads(concepts_path.read_text(encoding="utf-8"))
        concepts, concept_rejected = concept_entries(concepts_doc, pages)
        concepts_meta = {k: concepts_doc.get(k) for k in ("built_at", "model", "prompt_sha256", "cost_usd", "corpus")}
    raw_entries = tfda + abbr + concepts
    # de-duplicate by term (first wins), then validate through the runtime model
    by_term: dict[str, dict] = {}
    for e in raw_entries:
        by_term.setdefault(e["term"], e)
    entries = [GlossaryEntry(term=e["term"], synonyms=tuple(e["synonyms"]), kind=e["kind"]) for e in by_term.values()]
    digest = hashlib.sha256(canonical_json([x.model_dump(mode="json") for x in entries]).encode("utf-8")).hexdigest()
    version = f"glossary-{built_on.strftime('%Y%m%d')}-{digest[:12]}"
    glossary = Glossary(version=version, entries=tuple(entries))
    out_dir.mkdir(parents=True, exist_ok=True)
    glossary_path = out_dir / f"{version}.json"
    provenance_path = out_dir / f"{version}.provenance.json"
    if glossary_path.exists():
        raise SystemExit(f"{glossary_path} already exists")
    glossary_path.write_text(
        json.dumps(glossary.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    provenance = {
        "version": version,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "adr": "docs/adr/ADR-0008-medical-glossary-sources.md",
        "sources": {
            "tfda": {
                "dataset": TFDA_DATASET,
                "url": TFDA_URL,
                "licence": TFDA_LICENCE,
                "snapshot_sha256": tfda_sha,
                **tfda_stats,
            },
            "corpus_abbreviations": {
                "curated_file": "evals/glossary/sources/abbreviations_curated.json",
                "corpus": str(corpus_path),
                "documents_with_pages": len(pages),
                "kept": len(abbr),
                "rejected": rejected,
            },
        },
        "entries": {
            "total": len(entries),
            "brand": sum(1 for e in entries if e.kind == "brand"),
            "abbreviation": sum(1 for e in entries if e.kind == "abbreviation"),
            "concept": sum(1 for e in entries if e.kind == "concept"),
        },
        "concepts": (
            {
                "file": str(concepts_path),
                **concepts_meta,
                "kept": len(concepts),
                "rejected": concept_rejected,
                "note": "Chinese renderings are model translations of English terms that occur verbatim in the corpus; the decision-maker spot-checks a sample before a release (ADR-0008)",
            }
            if concepts_path is not None
            else None
        ),
        "entry_evidence": [
            {
                "term": e["term"],
                "kind": e["kind"],
                "source": e["source"],
                "evidence": e["evidence"],
                **({"licence_no": e["licence_no"], "status": e["status"]} if "licence_no" in e else {}),
            }
            for e in by_term.values()
        ],
        "matching_note": "the rewriter matches ASCII terms as whole words (case-insensitive) and CJK terms as substrings, outside protected spans",
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "version": version,
        "glossary": str(glossary_path),
        "provenance": str(provenance_path),
        "entries": provenance["entries"],
        "rejected": [r["term"] for r in rejected],
        "tfda": tfda_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tfda", type=Path, required=True)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=REPO / "evals/probe/precise_clause/v2/corpus.json")
    parser.add_argument("--out", type=Path, default=REPO / "evals/glossary")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--concepts", type=Path, default=None, help="concepts file from build_concepts.py (record 93)")
    args = parser.parse_args()
    summary = build(
        tfda_zip=args.tfda,
        pages_dir=args.pages,
        corpus_path=args.corpus,
        out_dir=args.out,
        built_on=args.date,
        concepts_path=args.concepts,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
