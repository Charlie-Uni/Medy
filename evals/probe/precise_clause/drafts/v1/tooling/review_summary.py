"""Render review progress and disputes without inventing human resolutions."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from review_pack import pack_samples
from run_codex_review import verify_review

REPO = Path(__file__).resolve().parents[6]
ROOT = REPO / "evals/probe/precise_clause"
DRAFTS = ROOT / "drafts/v1"
REVIEW = DRAFTS / "review"


def main() -> None:
    prompt_text = (ROOT / "v1/review_prompt.md").read_bytes().decode("utf-8")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    corpus = {x["source_hash"]: x for x in json.loads((ROOT / "v1/corpus.json").read_text())["documents"]}
    totals = Counter()
    batches = {}
    lines = [
        "# 新口径正式复核进度与争议",
        "",
        f"提示 SHA-256：`{prompt_hash}`。模型 gpt-6-astra，逐条 high；本表由 review_summary.py 生成。",
        "",
        "本表列当前样本的独立 LLM 复核意见；人工裁决见 [确认记录](owner_confirmations_2026-09-19.md) 及 resolutions.json。",
        "统计仅按 LLM 的 agree/dispute 结论，不表示争议是否已由人工裁决；草稿、页文本或提示变更后须重新复核。",
        "",
    ]
    details = []
    for batch in ("MA", "PV", "CO"):
        samples = json.loads((DRAFTS / f"samples_draft_{batch}.json").read_text())
        by_id = {s["sample_id"]: s for s in samples}
        run = json.loads((REVIEW / f"run_{batch}.json").read_text())
        records = pack_samples(samples, corpus, ROOT / "v1/pages")
        raw = (REVIEW / f"verdicts_{batch}.jsonl").read_text()
        rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
        if len({v["sample_id"] for v in rows}) != len(rows) or not {v["sample_id"] for v in rows}.issubset(by_id):
            raise ValueError(f"{batch}: duplicate or unexpected verdict sample ids")
        verify_review(
            run,
            records,
            {v["sample_id"]: v for v in rows},
            prompt_text,
            "gpt-6-astra",
            "high",
            input_dir=REVIEW,
            require_complete=False,
        )
        counts = Counter(x["verdict"] for x in rows)
        batches[batch] = {"expected": len(samples), "completed": len(rows), **dict(counts)}
        totals.update(counts)
        lines.append(f"- {batch}：{len(rows)}/{len(samples)}；agree {counts['agree']}，dispute {counts['dispute']}。")
        for verdict in rows:
            if verdict["verdict"] != "dispute":
                continue
            sample = by_id[verdict["sample_id"]]
            gold = sample["required_gold_evidence"][0]
            issues = ", ".join(k for k, v in verdict["items"].items() if v == "issue")
            details.extend(
                [
                    "",
                    f"## {sample['sample_id']} / {batch} / {issues}",
                    "",
                    f"问题：{sample['query']}",
                    "",
                    f"当前锚点：{gold['key_text']}",
                    "",
                    f"原文位置：{sample['_draft']['document_key']}，物理页 {gold['page']}，{gold['section']}。",
                    "",
                    f"复核理由：{verdict['reason']}",
                    "",
                    f"复核人建议：{verdict['suggestion']}",
                    "",
                    "人工裁决：请核对确认记录及 resolutions.json 中绑定本次输入与结论的记录。",
                ]
            )
    complete = all(v["expected"] == v["completed"] for v in batches.values())
    lines += [
        "",
        f"合计 {sum(totals.values())}/75；agree {totals['agree']}，dispute {totals['dispute']}。",
        "复核已跑完，人工裁决状态另见确认记录及 resolutions.json；未冻结。"
        if complete
        else "复核进行中，当前统计不是最终结果；未冻结。",
        *details,
        "",
    ]
    (REVIEW / "formal_review_status.md").write_text("\n".join(lines), encoding="utf-8")
    status = {"complete": complete, "prompt_hash": prompt_hash, "batches": batches, "totals": dict(totals)}
    (REVIEW / "formal_review_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
