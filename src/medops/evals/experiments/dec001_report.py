"""Gate evaluation and Markdown report for a DEC-001 run (ADR-0002 hard gates and selection rules).

Reads `run_manifest.json` + `results.json` produced by `dec001_run`, applies the pre-registered
thresholds and renders the numbers. It states explicitly which selection criteria could NOT be
evaluated in a lexical-only run (end-to-end Recall@5, end-to-end P95, licence review) so the report can
never be read as a production decision on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

MACRO_MIN = 0.90
SLICE_MIN = 0.85
SLICES = ("drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en")
REPLACE_MIN_GAIN_PP = 5.0
P95_MAX_RATIO = 1.25
RELEASE_BLOCKED = {"C"}


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _blk(block: Mapping[str, Any]) -> str:
    return f"{_pct(block['strict_macro_recall'])} (n={block['queries']})"


def gate_view(r: Mapping[str, Any]) -> Mapping[str, Any]:
    """The block the hard gates are computed on: the language_matched scope when the run recorded scopes
    (ADR-0002 amendment 1), else the whole candidate result (run 1 format)."""
    scopes = r.get("scopes")
    if scopes and scopes.get("language_matched"):
        return scopes["language_matched"]
    return r


def evaluate(results: Mapping[str, Any]) -> dict[str, Any]:
    scoped = any("scopes" in r for r in results["candidates"].values())
    out: dict[str, Any] = {
        "candidates": {},
        "selection": {},
        "gate_scope": "language_matched" if scoped else "all_samples",
    }
    for cand, r in sorted(results["candidates"].items()):
        view = gate_view(r)
        slices = {g["label"]: g for g in view["by_slice"]}
        slice_verdicts = {}
        for name in SLICES:
            g = slices.get(name)
            if g is None or g["recall"] is None:
                slice_verdicts[name] = {"recall": None, "support": 0, "passed": False, "note": "no samples"}
                continue
            insufficient = g["support"] < 8
            slice_verdicts[name] = {
                "recall": g["recall"],
                "support": g["support"],
                "passed": (g["recall"] >= SLICE_MIN) and not insufficient,
                "note": "support below 8: gate cannot be evaluated" if insufficient else "",
            }
        macro = view["strict_macro_recall"]
        gates = {
            "macro_recall_at_20_ge_90": macro is not None and macro >= MACRO_MIN,
            "all_six_slices_ge_85": all(v["passed"] for v in slice_verdicts.values()),
            "zero_leakage": len(r["leak_violations"]) == 0,
            "no_silent_shortfall": True,  # enforced by the adapter contract (page == min(eligible, k)); a violation raises
            "reproducible_rankings": len(r["not_reproducible_queries"]) == 0,
        }
        out["candidates"][cand] = {
            "macro": macro,
            "gate_queries": view.get("queries", r.get("queries")),
            "slices": slice_verdicts,
            "gates": gates,
            "passes_hard_gates": all(gates.values()),
            "p95_ms": r["latency_ms"]["p95"],
            "release_blocked": cand in RELEASE_BLOCKED,
        }
    a = out["candidates"].get("A")
    for cand, diff in sorted(results.get("paired_against_A", {}).items()):
        c = out["candidates"][cand]
        gain_ok = diff["point"] >= REPLACE_MIN_GAIN_PP and diff["ci_low"] > 0
        p95_ok = (
            a is not None and a["p95_ms"] and c["p95_ms"] is not None and c["p95_ms"] <= P95_MAX_RATIO * a["p95_ms"]
        )
        out["selection"][cand] = {
            "paired_gain_pp": diff["point"],
            "ci95": [diff["ci_low"], diff["ci_high"]],
            "gain_criterion_met": gain_ok,
            "lexical_p95_within_125pct_of_A": p95_ok,
            "hard_gates": c["passes_hard_gates"],
            "licence_blocks_selection": c["release_blocked"],
            "not_evaluated_here": [
                "end_to_end_recall_at_5_drop_le_1pp",
                "key_slice_drop_le_5pp_end_to_end",
                "end_to_end_p95_le_8s",
            ],
            "could_replace_A_on_lexical_evidence": gain_ok
            and bool(p95_ok)
            and c["passes_hard_gates"]
            and not c["release_blocked"],
        }
    passing = [c for c, v in out["candidates"].items() if v["passes_hard_gates"]]
    if not passing:
        out["lexical_conclusion"] = (
            "no candidate passes the hard gates: DEC-001 and M1 stay blocked; gates are not lowered"
        )
    elif "A" in passing:
        out["lexical_conclusion"] = (
            "A passes the hard gates and is the complexity baseline; a replacement needs the full selection rule (lexical gain + end-to-end + licence)"
        )
    else:
        out["lexical_conclusion"] = (
            f"A fails; among passing candidates {passing} the ADR tie rules apply (5 pp / CI, then lexical P95)"
        )
    return out


def render_markdown(manifest: Mapping[str, Any], results: Mapping[str, Any], evaluation: Mapping[str, Any]) -> str:
    lines = [
        f"# DEC-001 词法对比运行报告：{manifest['run_id']}",
        "",
        f"- 用途：{manifest['purpose']}",
        f"- 运行清单 SHA-256：`{results['run_manifest_sha256']}`（查询前写出）",
        f"- 数据集：{manifest['dataset']['version']}，dataset_hash `{manifest['dataset']['dataset_hash']}`",
        f"- Git HEAD：`{manifest.get('git_head')}`；as_of {manifest['measurement']['as_of']}；K={manifest['measurement']['k']}；"
        f"预热 {manifest['measurement']['warmup_full_passes']} 遍、测量 {manifest['measurement']['measured_full_passes']} 遍、种子 {manifest['measurement']['random_seed']}；并发 1",
        f"- 环境：{manifest['environment']['platform']}，{manifest['environment']['cpu_count']} CPU",
        "",
        "## 候选与索引",
        "",
        "| 候选 | 服务器 | 镜像 | 扩展 | 索引版本 | 分词器版本 | 词典版本 | 映射 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cand, c in sorted(manifest["candidates"].items()):
        idx = c["index"]
        ext = ", ".join(f"{k} {v}" for k, v in c["extensions"].items())
        lines.append(
            f"| {cand} | {c['server']} | `{(c.get('image_local_id') or 'dev cluster')[:19]}` | {ext} | `{idx['retriever_version']}` | `{idx['tokenizer_version']}` | `{idx['dictionary_version']}` | {c['mapping_counts']['mapped']} mapped / {c['mapping_counts']['unmappable']} unmappable |"
        )
    lines += [
        "",
        "## 硬门禁（ADR-0002）",
        "",
        "| 候选 | 严格宏平均 Recall@20 | " + " | ".join(SLICES) + " | 泄漏 | 可复现 | 通过 |",
        "| --- | --- | " + " | ".join("---" for _ in SLICES) + " | --- | --- | --- |",
    ]
    for cand, ev in sorted(evaluation["candidates"].items()):
        cells = []
        for name in SLICES:
            v = ev["slices"][name]
            cells.append(f"{_pct(v['recall'])} (n={v['support']}){'' if v['passed'] else ' ✗'}")
        r = results["candidates"][cand]
        lines.append(
            f"| {cand} | {_pct(ev['macro'])}{'' if ev['gates']['macro_recall_at_20_ge_90'] else ' ✗'} | "
            + " | ".join(cells)
            + f" | {len(r['leak_violations'])} | {'是' if ev['gates']['reproducible_rankings'] else '否'} | {'通过' if ev['passes_hard_gates'] else '未通过'} |"
        )
    if evaluation.get("gate_scope") == "language_matched":
        n_gate = next(iter(evaluation["candidates"].values()))["gate_queries"]
        lines += ["", f"硬门禁按 ADR-0002 修订 1 在语言一致子集内计算（每候选 {n_gate} 条冻结样本）。", ""]
        lines += [
            "## 作用域分报（冻结样本）",
            "",
            "| 候选 | 语言一致 宏平均 (n) | 跨语言 宏平均 (n) | 全部冻结样本 (n) |",
            "| --- | --- | --- | --- |",
        ]
        for cand, r in sorted(results["candidates"].items()):
            sc = r["scopes"]
            frozen_n = sum(1 for q in r["per_query"] if not q.get("provisional"))
            lines.append(
                f"| {cand} | {_blk(sc['language_matched'])} | {_blk(sc['cross_lingual'])} | "
                f"{_pct(r['strict_macro_recall'])} (n={frozen_n}) |"
            )
        if any(r["scopes"]["provisional_twins"]["queries"] for r in results["candidates"].values()):
            lines += [
                "",
                "### 临时叠加：未复核、未经人工确认的英文孪生查询（不进入门禁）",
                "",
                "| 候选 | 孪生 宏平均 (n) | 语言一致 + 孪生 宏平均 (n) | 孪生按部门 |",
                "| --- | --- | --- | --- |",
            ]
            for cand, r in sorted(results["candidates"].items()):
                sc = r["scopes"]
                dept_cells = ", ".join(
                    f"{g['label']} {_pct(g['recall'])} (n={g['support']})"
                    for g in sc["provisional_twins"]["by_department"]
                    if g["support"]
                )
                lines.append(
                    f"| {cand} | {_blk(sc['provisional_twins'])} | "
                    f"{_blk(sc['language_matched_plus_provisional_twins'])} | {dept_cells} |"
                )
    lines += [
        "",
        "## 部门与脚本变体（全部冻结样本）",
        "",
        "| 候选 | MA | PV | CO | zh-Hans | zh-Hant | en | drug_name_zh/zh-Hans | drug_name_zh/zh-Hant |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cand, r in sorted(results["candidates"].items()):
        dept = {g["label"]: g for g in r["by_department"]}
        script = {g["label"]: g for g in r["by_gold_script"]}
        drug = {g["label"]: g for g in r["drug_name_zh_by_script"]}

        def cell(g):
            return "n/a" if g is None or g["recall"] is None else f"{_pct(g['recall'])} (n={g['support']})"

        lines.append(
            f"| {cand} | {cell(dept.get('MA'))} | {cell(dept.get('PV'))} | {cell(dept.get('CO'))} | {cell(script.get('zh-Hans'))} | {cell(script.get('zh-Hant'))} | {cell(script.get('en'))} | {cell(drug.get('drug_name_zh/zh-Hans'))} | {cell(drug.get('drug_name_zh/zh-Hant'))} |"
        )
    lines += [
        "",
        "## 延迟与候选数",
        "",
        "| 候选 | 词法 P95 (ms) | 均值 (ms) | 最大 (ms) | 测量次数 | 耗尽(<K) 查询数 | 零结果查询数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cand, r in sorted(results["candidates"].items()):
        lat = r["latency_ms"]
        lines.append(
            f"| {cand} | {lat['p95']:.2f} | {lat['mean']:.2f} | {lat['max']:.2f} | {lat['measured_executions']} | {r['candidate_exhausted_queries']} | {r['zero_result_queries']} |"
        )
    lines += ["", "## 相对 A 的选择规则（仅词法部分）", ""]
    if evaluation["selection"]:
        lines += [
            "| 候选 | 配对提升 (pp) | 95% CI | 提升 ≥5pp 且 CI 下界 >0 | 词法 P95 ≤ 1.25×A | 硬门禁 | 许可证阻断 | 仅凭词法证据可替代 A |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for cand, s in sorted(evaluation["selection"].items()):
            lines.append(
                f"| {cand} | {s['paired_gain_pp']:+.1f} | [{s['ci95'][0]:+.1f}, {s['ci95'][1]:+.1f}] | {'是' if s['gain_criterion_met'] else '否'} | {'是' if s['lexical_p95_within_125pct_of_A'] else '否'} | {'通过' if s['hard_gates'] else '未通过'} | {'是' if s['licence_blocks_selection'] else '否'} | {'是' if s['could_replace_A_on_lexical_evidence'] else '否'} |"
            )
        lines.append("")
        lines.append(
            "未在本运行评估：端到端 Recall@5 下降 ≤1pp、关键切片端到端下降 ≤5pp、端到端 P95 ≤8s；这些需要向量/重排配置固定后另测。"
        )
    lines += ["", f"**词法结论：** {evaluation['lexical_conclusion']}", ""]
    lines += ["## 未命中明细（各候选 recall < 1 的样本）", ""]
    for cand, r in sorted(results["candidates"].items()):
        misses = [q for q in r["per_query"] if q["recall"] < 1.0]
        lines.append(
            f"- {cand}：{len(misses)} 条 — "
            + ", ".join(
                f"{q['sample_id']}{'(unmappable)' if q['unmappable_golds'] else ''}{'(cross)' if q.get('scope') == 'cross_lingual' else ''}{'(twin)' if q.get('provisional') else ''}"
                for q in misses
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate ADR-0002 gates for a DEC-001 run and write report.md")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads((args.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    results = json.loads((args.run_dir / "results.json").read_text(encoding="utf-8"))
    evaluation = evaluate(results)
    (args.run_dir / "evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_dir / "report.md").write_text(render_markdown(manifest, results, evaluation), encoding="utf-8")
    print(
        json.dumps({c: v["passes_hard_gates"] for c, v in evaluation["candidates"].items()}),
        evaluation["lexical_conclusion"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
