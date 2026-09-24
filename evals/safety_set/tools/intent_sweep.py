"""Regression sweep for the high-risk intent rule (record 70): recall over the safety set's class A, false positives over
the other safety classes (only E samples carrying a high-risk component may hit) and over the main set's 614 queries.

    python evals/safety_set/tools/intent_sweep.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import REPO, load_drafts  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from medops.harness.intent import INTENT_VERSION, classify  # noqa: E402

MAIN = REPO / "evals/main_set/main-v1-provisional/samples.jsonl"


def main() -> int:
    rows = load_drafts()
    high = lambda q: classify(q).type.value == "high_risk"  # noqa: E731
    a = [r for r in rows if r["category"] == "high_risk"]
    a_miss = [r["sample_id"] for r in a if not high(r["query"])]
    others = [r for r in rows if r["category"] != "high_risk"]
    hits = [(r["sample_id"], r["category"]) for r in others if high(r["query"])]
    unexpected = [
        h
        for h in hits
        if not (h[1] == "combined" and "high_risk" in next(r for r in others if r["sample_id"] == h[0])["slices"])
    ]
    main_rows = [json.loads(line) for line in MAIN.read_text(encoding="utf-8").splitlines() if line.strip()]
    main_hits = [(r["sample_id"], r["query"][:80]) for r in main_rows if high(r["query"])]
    out = {
        "intent_version": INTENT_VERSION,
        "class_a_recall": {"n": len(a), "matched": len(a) - len(a_miss), "missed": a_miss},
        "other_classes": {"n": len(others), "hits": hits, "unexpected": unexpected},
        "main_set": {"n": len(main_rows), "hits": main_hits},
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 1 if a_miss or unexpected or main_hits else 0


if __name__ == "__main__":
    sys.exit(main())
