# -*- coding: utf-8 -*-
"""Collect the current reviewer disputes of the v2 review into one adjudication sheet for annotator-01.

    python evals/probe/precise_clause/drafts/v2/tooling/disputes_sheet.py [--out drafts/v2/review/disputes_sheet.md]

For every disputed verdict: sample, current query/slices/key_text/span, the reviewer's issue items, reason and
suggestion, plus an empty 决定 column. The annotator writes either `接受`（I apply the suggested change and re-run
the reviewer for that sample with --only）or `保留：<理由>`（becomes resolution_note; status disputed_resolved）.
"""

import argparse
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("v2_codex_tooling", HERE / "run_codex_review.py")
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
REPO, REVIEW, DRAFTS = codex.REPO, codex.REVIEW, HERE.parent
CORPUS = REPO / "evals/probe/precise_clause/v1/corpus.json"
SOURCES = REPO / "evals/probe/precise_clause/v1/sources"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=REVIEW / "disputes_sheet.md")
    args = ap.parse_args()
    drafts = {}
    for batch in ("MA", "PV", "CO", "EN"):
        path = DRAFTS / f"samples_draft_{batch}.json"
        if path.exists():
            for s in json.loads(path.read_text(encoding="utf-8")):
                drafts[s["sample_id"]] = (batch, s)
    twin_of = {sid: s.get("derived_from") for sid, (_, s) in drafts.items() if s.get("derived_from")}
    parent_of_twin = {v: k for k, v in twin_of.items()}
    disputed_ids = set()
    for batch in ("MA", "PV", "CO", "EN"):
        vpath = REVIEW / f"verdicts_{batch}.jsonl"
        if vpath.exists():
            disputed_ids |= {v["sample_id"] for v in codex.load_records(vpath) if v["verdict"] == "dispute"}
    corpus = {d["source_hash"]: d for d in json.loads(CORPUS.read_text(encoding="utf-8"))["documents"]}
    used_docs = {}
    rows = []
    for batch in ("MA", "PV", "CO", "EN"):
        vpath = REVIEW / f"verdicts_{batch}.jsonl"
        if not vpath.exists():
            continue
        for v in codex.load_records(vpath):
            if v["verdict"] != "dispute":
                continue
            _, s = drafts[v["sample_id"]]
            g = s["required_gold_evidence"][0]
            issues = ", ".join(k for k, val in v["items"].items() if val == "issue")
            esc = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
            sid = s["sample_id"]
            if sid in twin_of:
                related = f"孪生于 {twin_of[sid]}" + ("（父样本也被争议）" if twin_of[sid] in disputed_ids else "（父样本未被争议）")
            elif sid in parent_of_twin:
                related = f"有孪生 {parent_of_twin[sid]}" + ("（孪生也被争议）" if parent_of_twin[sid] in disputed_ids else "（孪生未被争议）")
            else:
                related = "无孪生"
            doc = corpus[g["source_hash"]]
            used_docs[doc["document_key"]] = (doc, g["source_hash"])
            rows.append(
                f"| {sid} | {batch} | {related} | {doc['document_key']} | `{g['source_hash']}.pdf` | {g['page']} | {issues} | {esc(s['query'])} | {', '.join(s['slices'])} | {esc(g['key_text'][:140])} | "
                f"{esc(v['reason'][:600])} | {esc(v['suggestion'][:400])} | |"
            )
    lines = [
        "# 探针 v2 复核争议裁决表（复核人 reviewer-llm-02 = claude-opus-5）",
        "",
        f"> 共 {len(rows)} 条争议。每条请在「决定」列填写：`接受`（我按建议修改样本并只对该样本重跑复核）或 `保留：<理由>`（写入 resolution_note，状态记为 disputed_resolved）。批次 MA/PV/CO 为 v1 原样本（你此前已确认过），EN 为英文孪生。",
        "> 同族规则（SPEC 5.1 / PR-15）：孪生的 gold、slices 必须与父样本完全相同。凡涉及 key_text、evidence_span 或 slices 的决定，对父样本和孪生同时生效，即使复核人只争议了其中一个；query 的决定只影响被争议的那一条。",
        "",
        f"> PDF 文件位于本机目录 `{SOURCES}`（不进入 Git），页码为 PDF 物理页序号（从 1 起）。",
        "",
        "| 样本 | 批次 | 同族 | 文档 | PDF 文件 | 页 | 争议项 | query | slices | key_text | 复核人理由 | 复核人建议 | 决定 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "## 文档与 PDF 对照",
        "",
        "| 文档 | 标题 | PDF 文件 | 页数 |",
        "| --- | --- | --- | --- |",
        *[f"| {k} | {d['title']} | `{h}.pdf` | {d['pages']} |" for k, (d, h) in sorted(used_docs.items())],
    ]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} disputes -> {args.out}")


if __name__ == "__main__":
    main()
