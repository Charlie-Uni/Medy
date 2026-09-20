"""No-answer sample drafting (spec-m1 §2): a pinned LLM drafter proposes in-scope questions that the document does
not answer; the tool then checks mechanically that every `absence_term` is absent from ALL pages of the scope
document and reports corpus-wide hits for the annotator and the reviewer.

    python evals/main_set/tools/draft_noanswer.py draft [--only KEY ...] [--model claude-sonnet-5]
    python evals/main_set/tools/draft_noanswer.py verify

Documents: every active corpus document except tiny ones (< 1,500 chars); 1 question per label, 1 per guideline,
so ~70 candidates for a >= 40 target after curation. Page selection reuses draft_llm.select_pages; the pages
actually packed for the reviewer later are recorded in abstention.document_pages.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import pathlib
import re
import sys
import tempfile
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
import draft_llm  # noqa: E402

PROMPT = dc.DRAFTS / "drafting_prompt_noanswer.md"
RAW = dc.DRAFTS / "raw_noanswer"
INPUTS = dc.DRAFTS / "inputs"
SYSTEM_PROMPT = draft_llm.SYSTEM_PROMPT
MIN_CHARS = 1500
ASK = 2  # per document; curation keeps at most one per document unless the count falls short


def build_prompt(prompt_text: str, doc: dict, pages: list[int]) -> str:
    lines = [
        prompt_text.rstrip(),
        "",
        "---",
        "",
        "## 本次任务",
        "",
        f"文档标题：{doc['title']}",
        f"- document_key: {doc['document_key']}",
        f"- 部门: {doc['owner_dept']}",
        f"- 文档语言: {doc['language']}",
        f"- 类型: {doc['doc_type']}",
        f"- 要求样本数: {ASK}（topic 互不相同）",
        f"- 本次提供 {len(pages)} 页（文档共 {doc['pages']} 页）",
        "",
        "## 页文本",
        "",
    ]
    for p in pages:
        lines += [f"=== 第 {p} 页 ===", dc.page_text(doc["source_hash"], p) or "", ""]
    return "\n".join(lines)


def targets() -> list[tuple[dict, list[int]]]:
    out = []
    for key, d in dc.load_corpus().items():
        if key in dc.INACTIVE_KEYS:
            continue
        pages, total = draft_llm.select_pages(d)
        if total < MIN_CHARS:
            continue
        out.append((d, pages))
    return out


def draft(args: argparse.Namespace) -> int:
    prompt_text = PROMPT.read_bytes().decode("utf-8")
    version = dc.cli_version(args.binary)
    RAW.mkdir(exist_ok=True)
    INPUTS.mkdir(exist_ok=True)
    todo = [
        (d, p)
        for d, p in targets()
        if (not args.only or d["document_key"] in args.only)
        and (args.force or not (RAW / f"{d['document_key']}.json").exists())
    ]
    print(f"no-answer drafting for {len(todo)} documents with {args.model}", flush=True)

    def one(doc: dict, pages: list[int], workdir: pathlib.Path) -> str:
        prompt = build_prompt(prompt_text, doc, pages)
        (INPUTS / f"{doc['document_key']}.noanswer.txt").write_text(prompt, encoding="utf-8")
        started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        reply, meta = dc.run_claude(args.binary, args.model, args.effort, SYSTEM_PROMPT, prompt, workdir)
        rec = {
            "document_key": doc["document_key"],
            "source_hash": doc["source_hash"],
            "pages_sent": pages,
            "drafting_prompt_sha256": dc.sha256_bytes(prompt_text.encode("utf-8")),
            "cli_version": version,
            "started_at": started,
            "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "prompt_chars": len(prompt),
            **meta,
            "reply": reply,
        }
        (RAW / f"{doc['document_key']}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return f"{doc['document_key']}: ${meta['cost_usd']:.3f}"

    failures = 0
    with tempfile.TemporaryDirectory(prefix="main-na-") as tmp, cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(one, d, p, pathlib.Path(tmp)): d for d, p in todo}
        for fut in cf.as_completed(futs):
            try:
                print(fut.result(), flush=True)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"{futs[fut]['document_key']}: FAILED {exc}", flush=True)
    cost = sum(json.loads(p.read_text(encoding="utf-8")).get("cost_usd") or 0 for p in RAW.glob("*.json"))
    print(f"done: {len(todo) - failures} ok, {failures} failed; cumulative no-answer drafting cost ${cost:.2f}")
    return 1 if failures else 0


def term_hits(term: str, corpus: dict[str, dict]) -> dict[str, int]:
    """Documents (by key) whose pages contain the term (case-insensitive, norm-v1 text)."""
    t = dc.normalize_text(term).lower()
    hits: dict[str, int] = {}
    if len(t) < 2:
        return hits
    for key, d in corpus.items():
        n = 0
        for p in range(1, d["pages"] + 1):
            text = dc.page_text(d["source_hash"], p)
            if text and t in text.lower():
                n += 1
        if n:
            hits[key] = n
    return hits


def verify(args: argparse.Namespace) -> int:
    corpus = dc.load_corpus()
    cands: list[dict] = []
    seen: set[str] = set()
    per_doc_ok = Counter()
    for path in sorted(RAW.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        doc = corpus[rec["document_key"]]
        try:
            items = dc.parse_json_array(rec["reply"])
        except ValueError as exc:
            print(f"{doc['document_key']}: unparsable: {exc}")
            continue
        for rank, it in enumerate(items, 1):
            problems, warnings = [], []
            query = str(it.get("query") or "").strip()
            terms = [str(t).strip() for t in (it.get("absence_terms") or []) if str(t).strip()]
            if not 4 <= len(query) <= 300:
                problems.append(f"query length {len(query)}")
            nq = dc.normalize_text(query)
            if nq in seen:
                problems.append("duplicate query")
            seen.add(nq)
            if len(terms) < 2:
                problems.append("fewer than 2 absence_terms")
            hits_all = {t: term_hits(t, corpus) for t in terms}
            in_scope = {t: h.get(doc["document_key"], 0) for t, h in hits_all.items()}
            present = [t for t, n in in_scope.items() if n]
            if present:
                problems.append(f"absence_terms present in scope document: {present}")
            elsewhere = {t: len([k for k in h if k != doc["document_key"]]) for t, h in hits_all.items()}
            if any(n >= 10 for n in elsewhere.values()):
                warnings.append("some absence_terms are common elsewhere in the corpus (generic term?)")
            nc = it.get("nearest_clause")
            nearest = None
            if isinstance(nc, dict) and isinstance(nc.get("page"), int):
                text = dc.page_text(doc["source_hash"], nc["page"]) or ""
                status, pos, exact = dc.locate(text, str(nc.get("text") or ""))
                nearest = {
                    "page": nc["page"],
                    "text": exact if status.startswith(("exact", "tolerant")) else str(nc.get("text") or "")[:300],
                    "located": status,
                }
                if not status.startswith(("exact", "tolerant")):
                    warnings.append(f"nearest_clause not located ({status})")
            slices = ["no_answer"]
            if dc.mixed_zh_en(query, ""):
                slices.append("mixed_zh_en")
            if doc["doc_type"] == "label" and doc["language"] != "en" and re.search(r"[一-鿿]", query):
                slices.append("drug_name_zh")
            if doc["language"] == "en" and dc._ID.search(query):
                slices.append("protocol_id")
            language = "mixed" if "mixed_zh_en" in slices else "zh"
            query_en = it.get("query_en") if doc["language"] == "en" else None
            status = "ok" if not problems else "rejected"
            if status == "ok":
                per_doc_ok[doc["document_key"]] += 1
            cands.append(
                {
                    "query": query,
                    "dept": doc["owner_dept"],
                    "language": language,
                    "slices": slices,
                    "required_gold_evidence": [],
                    "answerable": False,
                    "expected_behaviour": "insufficient_evidence",
                    "abstention": {
                        "scope_document_key": doc["document_key"],
                        "topic": str(it.get("topic") or "")[:200],
                        "absence_check": f"absence_terms {terms} 在 {doc['document_key']} 全部 {doc['pages']} 页 norm-v1 页文本中出现 0 次（工具核查 {dt.date.today().isoformat()}）；语料内其他文档命中数 {elsewhere}"[
                            :800
                        ],
                        "document_pages": rec["pages_sent"],
                    },
                    "notes": "",
                    "_draft": {
                        "document_key": doc["document_key"],
                        "title": doc["title"],
                        "rank": rank,
                        "status": status,
                        "problems": problems,
                        "warnings": warnings,
                        "rationale": str(it.get("rationale") or "")[:500],
                        "absence_hits": {t: len(h) for t, h in hits_all.items()},
                        "nearest_clause": nearest,
                        "query_en": query_en if isinstance(query_en, str) else None,
                        "selected": status == "ok" and per_doc_ok[doc["document_key"]] == 1,
                    },
                }
            )
    out = dc.DRAFTS / "candidates_NA.json"
    out.write_text(json.dumps(cands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sel = [c for c in cands if c["_draft"]["selected"]]
    print(
        f"NA: {len(cands)} candidates, {sum(c['_draft']['status'] == 'ok' for c in cands)} passed absence checks, {len(sel)} selected; depts {dict(Counter(c['dept'] for c in sel))} -> {out.relative_to(dc.REPO)}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("--model", default="claude-sonnet-5")
    d.add_argument("--effort", default="high")
    d.add_argument("--binary", default=dc.DEFAULT_BINARY)
    d.add_argument("--workers", type=int, default=3)
    d.add_argument("--only", nargs="*")
    d.add_argument("--force", action="store_true")
    sub.add_parser("verify")
    args = ap.parse_args()
    return draft(args) if args.cmd == "draft" else verify(args)


if __name__ == "__main__":
    sys.exit(main())
