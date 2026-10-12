"""Breakdowns for a live harness run (rows.jsonl written by smoke_ask.py): by department, language, slice and
sample kind — answered rate, gold-cited rate, false abstention, reason codes, cost and latency. Read-only.

    python evals/harness/tools/summarize_run.py evals/harness/runs/<run> [--md out.md]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
from collections import Counter, defaultdict


def load(run_dir: pathlib.Path) -> list[dict]:
    """rows.jsonl is append-only across resumes (a redone sample appears twice); the last row per sample wins."""
    rows_path = run_dir / "rows.jsonl"
    if rows_path.exists():
        latest: dict[str, dict] = {}
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                latest[row["sample_id"]] = row
        return list(latest.values())
    return json.loads((run_dir / "results.json").read_text(encoding="utf-8"))["rows"]


def pct(num: int, den: int) -> str:
    return f"{num}/{den} = {100 * num / den:.1f}%" if den else "—"


def group_table(rows: list[dict], key, title: str) -> list[str]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        for g in key(r) if isinstance(key(r), (list, tuple)) else [key(r)]:
            groups[str(g)].append(r)
    lines = [
        f"### {title}",
        "",
        "| 组 | n | 有答案样本回答 | 回答且引用 gold | 有答案样本误弃答 | 无答案样本弃答 | 费用 | 均值延迟 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for g in sorted(groups):
        rs = groups[g]
        ans = [r for r in rs if r["kind"] != "no_answer"]
        na = [r for r in rs if r["kind"] == "no_answer"]
        answered = [r for r in ans if r["outcome"] == "answered"]
        false_abs = [r for r in ans if r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"]]
        abstained = [r for r in na if r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"]]
        lines.append(
            f"| {g} | {len(rs)} | {pct(len(answered), len(ans))} | {pct(sum(r['gold_cited'] for r in ans), len(ans))} | {pct(len(false_abs), len(ans))} | {pct(len(abstained), len(na))} | ${sum(r['cost_usd'] for r in rs):.2f} | {statistics.mean(r['latency_s'] for r in rs):.1f}s |"
        )
    lines.append("")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=pathlib.Path)
    ap.add_argument("--md", type=pathlib.Path)
    args = ap.parse_args()
    rows = load(args.run_dir)
    ans = [r for r in rows if r["kind"] != "no_answer"]
    na = [r for r in rows if r["kind"] == "no_answer"]
    lat = sorted(r["latency_s"] for r in rows)
    out = [f"# Run `{args.run_dir.name}` — {len(rows)} samples", ""]
    out += [
        f"- 有答案/冲突样本 {len(ans)}：回答 {pct(sum(r['outcome'] == 'answered' for r in ans), len(ans))}；回答且引用 gold {pct(sum(r['gold_cited'] for r in ans), len(ans))}；误弃答 {pct(sum(r['outcome'] == 'escalated' and 'insufficient_evidence' in r['reason_codes'] for r in ans), len(ans))}",
        f"- 无答案样本 {len(na)}：弃答 {pct(sum(r['outcome'] == 'escalated' and 'insufficient_evidence' in r['reason_codes'] for r in na), len(na))}；被回答 {sum(r['outcome'] == 'answered' for r in na)}",
        f"- 冲突样本引用现行版（gold）：{pct(sum(r['gold_cited'] for r in rows if r['kind'] == 'conflict'), sum(1 for r in rows if r['kind'] == 'conflict'))}",
        f"- reason codes：{dict(Counter(c for r in rows for c in r['reason_codes']))}",
        f"- 费用 ${sum(r['cost_usd'] for r in rows):.2f}，模型调用 {sum(r['model_calls'] for r in rows)}，延迟均值 {statistics.mean(lat):.1f}s，P50 {lat[len(lat) // 2]:.1f}s，P95 {lat[int(0.95 * (len(lat) - 1))]:.1f}s",
        f"- 节点重试/超时 attempt：{dict(Counter(a for r in rows for a in r['attempts'] if not a.endswith(':ok')))}",
        "",
    ]
    out += group_table(rows, lambda r: r["dept"], "按部门")
    out += group_table(rows, lambda r: r.get("language") or "?", "按语言")
    out += group_table(rows, lambda r: r["kind"], "按样本类型")
    out += group_table(
        rows, lambda r: "imported(pc-)" if r["imported"] else ("derived" if r["derived"] else "ms-"), "按来源"
    )
    out += group_table(rows, lambda r: r["slices"], "按切片（一个样本可属多个切片）")
    text = "\n".join(out)
    if args.md:
        args.md.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
