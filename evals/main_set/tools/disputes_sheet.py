"""Collect the LLM reviewer's disputes over the main-set batches into one adjudication sheet for annotator-01.

    python evals/main_set/tools/disputes_sheet.py [--out drafts/main-v1/review/disputes_sheet.md]

One row per disputed sample: batch, family relation, document / PDF (friendly symlink) / page, the disputed items,
the current query / slices / key_text (or the no-answer topic), the reviewer's reason and suggestion, and an empty
决定 column. The annotator writes `接受`（apply the suggestion, or `接受：key_text=… | slices=a,b | query=… | topic=…`）
or `保留：<理由>`（becomes resolution_note; status disputed_resolved）. Family rule: gold/slices decisions apply to
parent and twin together; query decisions only to the disputed sample.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def esc(t: object) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=REVIEW / "disputes_sheet.md")
    args = ap.parse_args()
    corpus = dc.load_corpus()
    by_hash = {d["source_hash"]: d for d in corpus.values()}
    drafts: dict[str, tuple[str, dict]] = {}
    for b in BATCHES:
        p = dc.DRAFTS / f"samples_draft_{b}.json"
        if p.exists():
            for s in json.loads(p.read_text(encoding="utf-8")):
                drafts[s["sample_id"]] = (b, s)
    twin_of = {sid: s["derived_from"] for sid, (_, s) in drafts.items() if s.get("derived_from")}
    parent_of_twin = {v: k for k, v in twin_of.items()}
    verdicts: dict[str, dict] = {}
    for b in BATCHES:
        rp = REVIEW / f"run_{b}.json"
        if rp.exists():
            verdicts.update(codex.current_verdicts(json.loads(rp.read_text(encoding="utf-8"))))
    disputed = {sid for sid, v in verdicts.items() if v["verdict"] == "dispute"}
    rows = []
    for sid in sorted(disputed):
        v = verdicts[sid]
        b, s = drafts[sid]
        issues = ", ".join(k for k, val in v["items"].items() if val == "issue")
        if sid in twin_of:
            related = f"孪生于 {twin_of[sid]}" + (
                "（父样本也被争议）" if twin_of[sid] in disputed else "（父样本未被争议）"
            )
        elif sid in parent_of_twin:
            related = f"有孪生 {parent_of_twin[sid]}" + (
                "（孪生也被争议）" if parent_of_twin[sid] in disputed else "（孪生未被争议）"
            )
        else:
            related = "无孪生"
        if s["required_gold_evidence"]:
            g = s["required_gold_evidence"][0]
            doc = by_hash[g["source_hash"]]
            page, anchor = g["page"], g["key_text"][:140]
        else:
            doc = corpus[s["abstention"]["scope_document_key"]]
            page, anchor = "全文", f"[无答案] topic: {s['abstention']['topic']}"
        pdf = f"`evals/main_set/pdf_by_key/{doc['document_key']}.pdf`"
        rows.append(
            f"| {sid} | {b} | {related} | {doc['document_key']} | {pdf} | {page} | {issues} | {esc(s['query'])} | {', '.join(s['slices'])} | "
            f"{esc(anchor)} | {esc(v['reason'][:600])} | {esc(v['suggestion'][:400])} | |"
        )
    lines = [
        "# 主评测集 main-v1 复核争议裁决表（复核人 reviewer-llm-02 = claude-opus-5）",
        "",
        f"> 共 {len(rows)} 条争议。每条请在「决定」列填写：`接受`（我按建议修改样本并只对该样本重跑复核；建议不够机械时写 `接受：key_text=… | slices=a,b | query=… | topic=…`）或 `保留：<理由>`（写入 resolution_note，状态记为 disputed_resolved）。",
        "> 同族规则（spec-v1.1 §5.1 / PR-15）：孪生的 gold、slices 与父样本完全相同；涉及 key_text、evidence_span 或 slices 的决定对父样本和孪生同时生效，query 的决定只影响被争议的那一条。无答案样本只有 query / topic / slices 可改。",
        "> PDF 用友好名打开（`evals/main_set/pdf_by_key/<document_key>.pdf`，本机符号链接），页码为 PDF 物理页序号。",
        "",
        "| 样本 | 批次 | 同族 | 文档 | PDF | 页 | 争议项 | query | slices | key_text / topic | 复核人理由 | 复核人建议 | 决定 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
    ]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} disputes -> {args.out.relative_to(dc.REPO)}")


if __name__ == "__main__":
    main()
