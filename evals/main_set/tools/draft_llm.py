"""Main-set drafting stage (spec-m1 v1.0 section 4 step 1): ask a pinned LLM drafter for clause samples per
document, then anchor every proposal mechanically against the norm-v1 page text.

    python evals/main_set/tools/draft_llm.py plan                       # writes drafts/main-v1/plan.json
    python evals/main_set/tools/draft_llm.py draft [--only KEY ...]     # one claude -p call per document -> raw/
    python evals/main_set/tools/draft_llm.py verify                     # raw/ -> candidates_{MA,PV,CO}.json

The drafter (default claude-sonnet-5) must differ from the LLM second reviewer (claude-opus-5, SPEC 4 step 3).
Full page texts go only to inputs/ (gitignored); raw/ keeps the reply, the prompt hash and the call metadata.
Verification never trusts the reply: key_text/span are re-located in the page text (exact or whitespace/quote
tolerant), offsets are recomputed, uniqueness is checked, and advisory slice checks are attached. Nothing here
decides a sample: the annotator sheet is produced by make_sheets.py from the curated candidates.
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

PROMPT = dc.DRAFTS / "drafting_prompt.md"
PLAN = dc.DRAFTS / "plan.json"
RAW = dc.DRAFTS / "raw"
RAW_LONG = dc.DRAFTS / "raw_long"  # targeted pass for long_context clauses (spec-m1 §2: span > 1,500 chars)
INPUTS = dc.DRAFTS / "inputs"
LONG_ADDENDUM = (
    "## 本次为“长条款”专项\n\n"
    "只需要 1 条样本（最多 2 条备选）：span 必须是一段**完整的列表或要件清单条款**，长度 **1500 到 2000 字符**（逐字连续复制，"
    "包含 key_text，不要跨越两个不同章节，不要把整节塞进来）；问题应是需要整段清单才能完整回答的问题（例如“…至少应包含哪些要素？”）。"
    "key_text 仍是该清单中最能标识它的最短片段（页内唯一）。若提供的页中没有这样长度的清单条款，输出空数组 []。"
)
SYSTEM_PROMPT = (
    "You are a careful drafting assistant for a regulatory-document retrieval benchmark. Follow the user's "
    "instructions exactly and output only what they ask for."
)
PAGE_BUDGET_CHARS = 36000
MAX_PAGES = 14
TOC = re.compile(r"\.{6,}")


def page_score(text: str) -> float:
    return (
        len(dc._NUM_UNIT.findall(text))
        + len(dc._TIME.findall(text))
        + 0.6 * len(dc._NEG.findall(text))
        + 0.3 * len(dc._ID.findall(text))
        + 0.0002 * len(text)
    )


def select_pages(doc: dict) -> tuple[list[int], int]:
    texts = {p: dc.page_text(doc["source_hash"], p) or "" for p in range(1, doc["pages"] + 1)}
    total = sum(len(t) for t in texts.values())
    if total <= PAGE_BUDGET_CHARS:
        return [p for p, t in texts.items() if len(t) >= 80], total
    scored = []
    for p, t in texts.items():
        if len(t) < 400 or len(TOC.findall(t)) >= 8:
            continue
        scored.append((page_score(t), p))
    scored.sort(reverse=True)
    chosen: list[int] = []
    used = 0
    for _, p in scored:
        if len(chosen) >= MAX_PAGES or used + len(texts[p]) > PAGE_BUDGET_CHARS:
            continue
        chosen.append(p)
        used += len(texts[p])
    return sorted(chosen), total


def make_plan() -> dict:
    corpus = dc.load_corpus()
    used = dc.probe_usage()
    fixtures_path = dc.MAIN / "conflict_fixtures/fixtures.json"
    fixture_keys = (
        {f["document_key"] for f in json.loads(fixtures_path.read_text(encoding="utf-8"))["fixtures"]}
        if fixtures_path.exists()
        else set()
    )
    entries = []
    for key, d in corpus.items():
        if key in dc.INACTIVE_KEYS:
            continue
        pages, total = select_pages(d)
        probe_used = used.get(d["source_hash"], 0)
        if probe_used:
            quota = min(2, dc.CAP_PER_DOCUMENT - probe_used)
        elif key in fixture_keys:
            quota = 5  # version_conflict samples: 5 documents x 5 >= 20 non-derived (twins inherit the slice)
        elif d["doc_type"] == "label":
            quota = 3 if total < 6000 else 4
        else:
            quota = 4
        entries.append(
            {
                "document_key": key,
                "dept": d["owner_dept"],
                "language": d["language"],
                "doc_type": d["doc_type"],
                "probe_samples": probe_used,
                "quota": quota,
                "ask": quota + 2,
                "pages_sent": pages,
                "pages_total": d["pages"],
                "chars_total": total,
            }
        )
    plan = {
        "created_at": dt.date.today().isoformat(),
        "cap_per_document": dc.CAP_PER_DOCUMENT,
        "excluded_inactive": sorted(dc.INACTIVE_KEYS),
        "page_budget_chars": PAGE_BUDGET_CHARS,
        "max_pages": MAX_PAGES,
        "documents": entries,
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_dept = Counter()
    for e in entries:
        by_dept[e["dept"]] += e["quota"]
    print(
        f"plan: {len(entries)} documents, quota total {sum(by_dept.values())} {dict(by_dept)} -> {PLAN.relative_to(dc.REPO)}"
    )
    return plan


def build_prompt(prompt_text: str, doc: dict, entry: dict, mode: str = "main") -> str:
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
        (
            f"- 要求样本数: {entry['quota']}（可另给 1 到 2 条备选，排在最后）"
            if mode == "main"
            else "- 要求样本数: 1（长条款专项，见下）"
        ),
        f"- 本次提供 {len(entry['pages_sent'])} 页（文档共 {entry['pages_total']} 页；只能从提供的页中选条款）",
        "",
    ]
    if mode == "long":
        lines += [LONG_ADDENDUM, ""]
    lines += ["## 页文本", ""]
    for p in entry["pages_sent"]:
        lines.append(f"=== 第 {p} 页 ===")
        lines.append(dc.page_text(doc["source_hash"], p) or "")
        lines.append("")
    return "\n".join(lines)


def draft_one(
    binary: str,
    model: str,
    effort: str,
    version: str,
    prompt_text: str,
    doc: dict,
    entry: dict,
    workdir: pathlib.Path,
    mode: str = "main",
) -> str:
    key = doc["document_key"]
    prompt = build_prompt(prompt_text, doc, entry, mode)
    raw_dir = RAW if mode == "main" else RAW_LONG
    (INPUTS / (f"{key}.txt" if mode == "main" else f"{key}.long.txt")).write_text(prompt, encoding="utf-8")
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    reply, meta = dc.run_claude(binary, model, effort, SYSTEM_PROMPT, prompt, workdir)
    record = {
        "document_key": key,
        "source_hash": doc["source_hash"],
        "quota": entry["quota"] if mode == "main" else 1,
        "mode": mode,
        "pages_sent": entry["pages_sent"],
        "drafting_prompt_sha256": dc.sha256_bytes(prompt_text.encode("utf-8")),
        "cli_version": version,
        "started_at": started,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "prompt_chars": len(prompt),
        **meta,
        "reply": reply,
    }
    (raw_dir / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{key}: {meta['input_tokens']}+{meta['output_tokens']} tokens, ${meta['cost_usd']:.3f}"


def draft(args: argparse.Namespace) -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    corpus = dc.load_corpus()
    prompt_text = PROMPT.read_bytes().decode("utf-8")
    version = dc.cli_version(args.binary)
    raw_dir = RAW if args.mode == "main" else RAW_LONG
    raw_dir.mkdir(exist_ok=True)
    INPUTS.mkdir(exist_ok=True)
    todo = []
    for e in plan["documents"]:
        if args.only and e["document_key"] not in args.only:
            continue
        if args.mode == "long" and (
            e["doc_type"] != "guideline" or e["probe_samples"] + e["quota"] >= dc.CAP_PER_DOCUMENT
        ):
            continue  # long clauses live in guidelines; keep one slot under the per-document cap
        if not args.force and (raw_dir / f"{e['document_key']}.json").exists():
            continue
        todo.append(e)
    print(
        f"drafting {len(todo)} documents with {args.model} (effort {args.effort}, {args.workers} workers)", flush=True
    )
    failures = 0
    with (
        tempfile.TemporaryDirectory(prefix="main-draft-") as tmp,
        cf.ThreadPoolExecutor(max_workers=args.workers) as pool,
    ):
        futs = {
            pool.submit(
                draft_one,
                args.binary,
                args.model,
                args.effort,
                version,
                prompt_text,
                corpus[e["document_key"]],
                e,
                pathlib.Path(tmp),
                args.mode,
            ): e
            for e in todo
        }
        for fut in cf.as_completed(futs):
            e = futs[fut]
            try:
                print(fut.result(), flush=True)
            except Exception as exc:  # noqa: BLE001 - reported per document, run continues
                failures += 1
                print(f"{e['document_key']}: FAILED {exc}", flush=True)
    cost = sum(
        json.loads(p.read_text(encoding="utf-8")).get("cost_usd") or 0
        for p in list(RAW.glob("*.json")) + list(RAW_LONG.glob("*.json"))
    )
    print(f"done: {len(todo) - failures} ok, {failures} failed; cumulative drafting cost ${cost:.2f}")
    return 1 if failures else 0


def verify(args: argparse.Namespace) -> int:
    plan = {e["document_key"]: e for e in json.loads(PLAN.read_text(encoding="utf-8"))["documents"]}
    corpus = dc.load_corpus()
    by_dept: dict[str, list[dict]] = {"MA": [], "PV": [], "CO": []}
    seen_queries: dict[str, str] = {}
    totals = Counter()
    for path in sorted(RAW.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        key = rec["document_key"]
        doc = corpus[key]
        entry = plan[key]
        try:
            items = dc.parse_json_array(rec["reply"])
        except ValueError as exc:
            print(f"{key}: reply unparsable: {exc}")
            totals["unparsable_docs"] += 1
            continue
        ok_count = 0
        for rank, it in enumerate(items, 1):
            cand = anchor(it, rank, doc, entry, seen_queries)
            if cand["_draft"]["status"] == "ok":
                ok_count += 1
                cand["_draft"]["selected"] = ok_count <= entry["quota"]
            by_dept[doc["owner_dept"]].append(cand)
            totals[cand["_draft"]["status"]] += 1
        totals["docs"] += 1
        if ok_count < entry["quota"]:
            print(f"{key}: only {ok_count}/{entry['quota']} anchored candidates")
        long_path = RAW_LONG / path.name
        if long_path.exists():
            # targeted long_context pass: at most one extra selected sample per document, inside the cap
            selected = min(ok_count, entry["quota"])
            try:
                long_items = dc.parse_json_array(json.loads(long_path.read_text(encoding="utf-8"))["reply"])
            except ValueError as exc:
                print(f"{key}: long reply unparsable: {exc}")
                long_items = []
            picked = False
            for i, it in enumerate(long_items, 1):
                cand = anchor(it, 100 + i, doc, entry, seen_queries)
                d = cand["_draft"]
                d["mode"] = "long"
                if d["status"] == "ok" and "long_context" not in cand["slices"]:
                    d["status"] = "rejected"
                    d["problems"].append("long pass: span not longer than 1500 characters")
                if d["status"] == "ok" and not picked and selected + entry["probe_samples"] < dc.CAP_PER_DOCUMENT:
                    d["selected"] = True
                    picked = True
                    totals["long_selected"] += 1
                by_dept[doc["owner_dept"]].append(cand)
                totals[f"long_{d['status']}"] += 1
    for dept, cands in by_dept.items():
        out = dc.DRAFTS / f"candidates_{dept}.json"
        out.write_text(json.dumps(cands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sel = [c for c in cands if c["_draft"].get("selected")]
        print(
            f"{dept}: {len(cands)} candidates, {sum(c['_draft']['status'] == 'ok' for c in cands)} anchored, "
            f"{len(sel)} selected; slices {dict(Counter(s for c in sel for s in c['slices']))} -> {out.relative_to(dc.REPO)}"
        )
    print(f"totals: {dict(totals)}")
    return 0


def anchor(it: dict, rank: int, doc: dict, entry: dict, seen_queries: dict[str, str]) -> dict:
    problems: list[str] = []
    warnings: list[str] = []
    query = str(it.get("query") or "").strip()
    page = it.get("page")
    key_in = str(it.get("key_text") or "")
    span_in = str(it.get("span") or "")
    slices_in = [s for s in (it.get("slices") or []) if s in dc.SLICES]
    if not isinstance(page, int) or page < 1 or page > doc["pages"]:
        problems.append(f"page {page!r} out of range")
        page = None
    if page is not None and page not in entry["pages_sent"]:
        warnings.append("page was not among the pages sent")
    text = dc.page_text(doc["source_hash"], page) if page else None
    key = span = ""
    cs = ce = -1
    key_status = span_status = "n/a"
    if text is None:
        problems.append("no page text")
    else:
        key_status, kpos, key = dc.locate(text, key_in)
        if not key_status.startswith(("exact", "tolerant")):
            problems.append(f"key_text {key_status}")
        span_status, spos, span = dc.locate(text, span_in)
        if not span_status.startswith(("exact", "tolerant")):
            problems.append(f"span {span_status}")
        elif key and key not in span:
            problems.append("span does not contain key_text")
        else:
            cs, ce = spos, spos + len(span)
    if not 4 <= len(query) <= 300:
        problems.append(f"query length {len(query)}")
    if not 2 <= len(key) <= 200 and key:
        problems.append(f"key_text length {len(key)}")
    if span and not 2 <= len(span) <= 2000:
        problems.append(f"span length {len(span)}")
    nq = dc.normalize_text(query)
    if key and nq == key:
        problems.append("query equals key_text")
    if nq in seen_queries and seen_queries[nq] != f"{doc['document_key']}#{rank}":
        problems.append(f"duplicate query of {seen_queries[nq]}")
    else:
        seen_queries.setdefault(nq, f"{doc['document_key']}#{rank}")
    slices = list(dict.fromkeys(slices_in))
    if doc["language"] == "en" and "drug_name_zh" in slices:
        slices.remove("drug_name_zh")
        warnings.append("dropped drug_name_zh on an English document")
    mixed = dc.mixed_zh_en(query, key)
    if mixed and "mixed_zh_en" not in slices:
        slices.append("mixed_zh_en")
    if not mixed and "mixed_zh_en" in slices:
        slices.remove("mixed_zh_en")
    if span and len(span) > dc.LONG_CONTEXT_CHARS:
        slices.append("long_context")
    if not slices:
        problems.append("no slices")
    warnings.extend(dc.slice_warnings(query, span, slices, doc))
    query_en = it.get("query_en")
    if doc["language"] == "en" and not (isinstance(query_en, str) and 4 <= len(query_en.strip()) <= 300):
        warnings.append("missing query_en for an English document")
        query_en = None
    if doc["language"] != "en":
        query_en = None
    language = "mixed" if "mixed_zh_en" in slices else "zh"
    return {
        "query": query,
        "dept": doc["owner_dept"],
        "language": language,
        "slices": slices,
        "required_gold_evidence": [
            {
                "gold_id": None,
                "source_hash": doc["source_hash"],
                "version_label": doc["version_label"],
                "page": page,
                "printed_page_label": None,
                "section": str(it.get("section") or "").strip()[:200] or "（未填）",
                "key_text": key,
                "evidence_span": {"text": span, "char_start": cs, "char_end": ce},
            }
        ],
        "notes": "",
        "_draft": {
            "document_key": doc["document_key"],
            "title": doc["title"],
            "rank": rank,
            "status": "ok" if not problems else "rejected",
            "problems": problems,
            "warnings": warnings,
            "key_status": key_status,
            "span_status": span_status,
            "query_en": query_en.strip() if isinstance(query_en, str) else None,
            "rationale": str(it.get("rationale") or "")[:500],
            "selected": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    d = sub.add_parser("draft")
    d.add_argument("--model", default="claude-sonnet-5")
    d.add_argument("--effort", default="high")
    d.add_argument("--binary", default=dc.DEFAULT_BINARY)
    d.add_argument("--workers", type=int, default=4)
    d.add_argument("--only", nargs="*")
    d.add_argument("--force", action="store_true")
    d.add_argument("--mode", choices=("main", "long"), default="main")
    sub.add_parser("verify")
    args = ap.parse_args()
    if args.cmd == "plan":
        make_plan()
        return 0
    if args.cmd == "draft":
        return draft(args)
    return verify(args)


if __name__ == "__main__":
    sys.exit(main())
