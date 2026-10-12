"""Aggregate supplied semantic reviews of exact main-run snapshots. No model/DB calls.

python evals/harness/tools/answer_review.py --run RUN_DIR [--reviews VERDICTS.jsonl] --out NEW_REPORT.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from medops.evals.answer_review import load_run_cases, summarize
from medops.evals.datasets import read_rows, sha256_file


def report(run: Path, reviews_path: Path | None = None) -> dict:
    cases, latest = load_run_cases(run)
    result = summarize(cases, read_rows(reviews_path) if reviews_path else [])
    result["provenance"] = {
        "run": str(run),
        "rows_sha256": sha256_file(run / "rows.jsonl"),
        "review_file_sha256": sha256_file(reviews_path) if reviews_path else None,
        "snapshot_file_hashes": sorted(r["answer_review_input"]["sha256"] for r in latest.values()),
    }
    return result


def report_runs(runs: Sequence[Path], reviews_path: Path | None = None) -> dict:
    """Aggregate exact snapshots from distinct run directories without copying them."""
    if not runs:
        raise ValueError("at least one answer run is required")
    cases = []
    seen_ids: set[str] = set()
    provenance = []
    for run in runs:
        current, latest = load_run_cases(run)
        current_ids = {case["sample_id"] for case in current}
        overlap = seen_ids & current_ids
        if overlap:
            raise ValueError(f"answer review runs contain duplicate samples: {sorted(overlap)}")
        seen_ids.update(current_ids)
        cases.extend(current)
        provenance.append(
            {
                "run": str(run),
                "rows_sha256": sha256_file(run / "rows.jsonl"),
                "snapshot_file_hashes": sorted(row["answer_review_input"]["sha256"] for row in latest.values()),
            }
        )
    result = summarize(cases, read_rows(reviews_path) if reviews_path else [])
    result["provenance"] = {
        "runs": provenance,
        "review_file_sha256": sha256_file(reviews_path) if reviews_path else None,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, nargs="+", required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = report_runs(args.run, args.reviews)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
