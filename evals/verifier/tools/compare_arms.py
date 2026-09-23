"""Compare DEC-003 arms on the same pairs (the intersection of every arm's judged pair ids).

    python evals/verifier/tools/compare_arms.py [--out evals/verifier/dec003/comparison.md] results_rules.json results_claude-haiku-4-5.json ...
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
LABELS = ("supported", "not_supported", "contradicted")


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    acc = sum(r["pred"] == r["label"] for r in rows) / n if n else None
    neg = [r for r in rows if r["label"] != "supported"]
    unsafe = sum(1 for r in neg if r["pred"] == "supported") / len(neg) if neg else None
    by_kind = {}
    for kind in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == kind]
        by_kind[kind] = sum(r["pred"] == r["label"] for r in sub) / len(sub)
    by_slice = {}
    for sl in sorted({s for r in rows for s in r["slices"]}):
        sub = [r for r in rows if sl in r["slices"]]
        by_slice[sl] = (len(sub), sum(r["pred"] == r["label"] for r in sub) / len(sub))
    return {"n": n, "accuracy": acc, "unsafe_accept_rate": unsafe, "by_kind": by_kind, "by_slice": by_slice}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/comparison.md")
    args = ap.parse_args()
    arms = {}
    for path in args.results:
        data = json.loads(path.read_text(encoding="utf-8"))
        arms[f"{data['arm']}:{data['model']}"] = (data, {r["pair_id"]: r for r in data["per_pair"]})
    common = set.intersection(*(set(rows) for _, rows in arms.values()))
    lines = [f"# DEC-003 arm comparison on {len(common)} shared pairs", ""]
    lines += ["| arm | accuracy | unsafe accept | " + " | ".join(sorted({r['kind'] for _, rows in arms.values() for r in rows.values()})) + " | cost (USD, API-equivalent) |"]
    kinds = sorted({r["kind"] for _, rows in arms.values() for r in rows.values()})
    lines.append("| --- | ---: | ---: | " + " | ".join("---:" for _ in kinds) + " | ---: |")
    per_arm = {}
    for name, (data, rows) in arms.items():
        m = metrics([rows[pid] for pid in sorted(common)])
        per_arm[name] = m
        kind_cells = " | ".join(f"{m['by_kind'].get(k, float('nan')):.3f}" if k in m["by_kind"] else "—" for k in kinds)
        lines.append(f"| {name} | {m['accuracy']:.3f} | {m['unsafe_accept_rate']:.3f} | {kind_cells} | {data.get('cost_usd', 0):.2f} |")
    lines += ["", "## By slice (accuracy; n in the first arm)", ""]
    slices = sorted({s for m in per_arm.values() for s in m["by_slice"]})
    lines.append("| slice | n | " + " | ".join(per_arm) + " |")
    lines.append("| --- | ---: | " + " | ".join("---:" for _ in per_arm) + " |")
    first = next(iter(per_arm.values()))
    for sl in slices:
        n = first["by_slice"].get(sl, (0, 0))[0]
        cells = " | ".join(f"{m['by_slice'][sl][1]:.3f}" if sl in m["by_slice"] else "—" for m in per_arm.values())
        lines.append(f"| {sl} | {n} | {cells} |")
    lines.append("")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:4 + len(arms)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
