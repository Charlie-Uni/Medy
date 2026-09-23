"""DEC-003 arm 0: the deterministic verifier (rules + containment + overlap, no model) on the pair set.

    python evals/verifier/tools/run_rules_arm.py [--pairs evals/verifier/dec003/pairs.jsonl] [--out evals/verifier/dec003/results_rules.json]

Prediction per pair: contradicted if any element is contradicted; else supported if no element is not_supported;
else not_supported. Reports accuracy overall, per kind, per slice, plus the confusion matrix and how often the
rules alone were decisive (no containment/overlap fallback needed).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/verifier/tools"))
from common import evidence_from_pair, predict_from_result, report_markdown  # noqa: E402

from medops.domain.answer import Claim  # noqa: E402
from medops.verification.verifier import VERIFIER_VERSION, verify_claims  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=pathlib.Path, default=REPO / "evals/verifier/dec003/pairs.jsonl")
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/results_rules.json")
    args = ap.parse_args()
    pairs = [json.loads(l) for l in args.pairs.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for p in pairs:
        ev = evidence_from_pair(p)
        vr = verify_claims([Claim(text=p["statement"], citation_chunk_ids=(p["evidence_chunk_id"],))], [ev])
        pred, decisive = predict_from_result(vr)
        rows.append({"pair_id": p["pair_id"], "label": p["label"], "pred": pred, "kind": p["kind"], "slices": p["slices"], "dept": p["dept"], "rules_decisive": decisive})
    result = summarize(rows, arm="rules", model=VERIFIER_VERSION)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(report_markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("arm", "n", "accuracy", "by_kind")}, ensure_ascii=False))
    return 0


def summarize(rows: list[dict], *, arm: str, model: str, cost_usd: float = 0.0) -> dict:
    n = len(rows)
    correct = sum(r["pred"] == r["label"] for r in rows)
    by_kind: dict[str, dict] = {}
    for kind in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == kind]
        by_kind[kind] = {"n": len(sub), "accuracy": round(sum(r["pred"] == r["label"] for r in sub) / len(sub), 4)}
    by_slice: dict[str, dict] = {}
    for sl in sorted({s for r in rows for s in r["slices"]}):
        sub = [r for r in rows if sl in r["slices"]]
        by_slice[sl] = {"n": len(sub), "accuracy": round(sum(r["pred"] == r["label"] for r in sub) / len(sub), 4)}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        confusion[r["label"]][r["pred"]] += 1
    labels = ("supported", "not_supported", "contradicted")
    # safety-relevant error: a contradiction or an unsupported statement judged supported
    unsafe = sum(1 for r in rows if r["label"] != "supported" and r["pred"] == "supported")
    return {
        "arm": arm,
        "model": model,
        "n": n,
        "accuracy": round(correct / n, 4) if n else None,
        "unsafe_accept_rate": round(unsafe / max(1, sum(1 for r in rows if r["label"] != "supported")), 4),
        "rules_decisive_share": round(sum(1 for r in rows if r.get("rules_decisive")) / n, 4) if n else None,
        "by_kind": by_kind,
        "by_slice": by_slice,
        "confusion": {a: {b: confusion[a][b] for b in labels} for a in labels},
        "cost_usd": round(cost_usd, 4),
        "per_pair": rows,
        "dept_counts": dict(Counter(r["dept"] for r in rows)),
    }


if __name__ == "__main__":
    sys.exit(main())
