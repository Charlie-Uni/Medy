"""Estimate the production path (rules first, model only where rules are undetermined) from existing arm
results, without new calls: for each shared pair take the rules verdict when `rules_decisive` (every element
verdict came from a rule), otherwise the model arm's verdict.

    python evals/verifier/tools/simulate_hybrid.py results_rules.json results_claude-haiku-4-5.json [...] [--out comparison_hybrid.md]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/verifier/tools"))
from compare_arms import metrics  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rules", type=pathlib.Path)
    ap.add_argument("models", nargs="+", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/comparison_hybrid.md")
    args = ap.parse_args()
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    rrows = {r["pair_id"]: r for r in rules["per_pair"]}
    lines = ["# DEC-003 simulated hybrid (rules first, model where rules are undetermined)", ""]
    lines += ["| arm | shared pairs | model calls needed | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for path in args.models:
        data = json.loads(path.read_text(encoding="utf-8"))
        mrows = {r["pair_id"]: r for r in data["per_pair"]}
        shared = sorted(set(rrows) & set(mrows))
        rows, calls = [], 0
        for pid in shared:
            r = rrows[pid]
            if r.get("rules_decisive"):
                rows.append(r)
            else:
                calls += 1
                rows.append({**r, "pred": mrows[pid]["pred"]})
        m = metrics(rows)
        k = m["by_kind"]
        lines.append(
            f"| rules→{data['model']} | {len(shared)} | {calls} ({calls / len(shared):.0%}) | {m['accuracy']:.3f} | {m['unsafe_accept_rate']:.3f} | "
            f"{k.get('contradicted/negation', 0):.3f} | {k.get('contradicted/numeric', 0):.3f} | {k.get('not_supported/same_doc', 0):.3f} | "
            f"{k.get('not_supported/other_doc', 0):.3f} | {k.get('supported', 0):.3f} |"
        )
    lines.append("")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
