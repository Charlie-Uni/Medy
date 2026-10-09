"""Validate the exact EVAL-12 calibration panel without calling a model.

python evals/harness/tools/answer_review_plan.py [--plan PLAN] [--dataset DATASET]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from medops.evals.answer_review import validate_calibration_plan
from medops.evals.datasets import sha256_file

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=REPO / "evals/answer_quality/calibration-v1-plan.json")
    parser.add_argument("--dataset", type=Path, default=REPO / "evals/main_set/main-v5-provisional")
    args = parser.parse_args()
    plan = validate_calibration_plan(args.plan, args.dataset, root=REPO)
    print(
        json.dumps(
            {
                "status": "valid_no_model_calls",
                "plan_sha256": sha256_file(args.plan),
                "dataset_version": plan["dataset"]["dataset_version"],
                "cases": plan["selection"]["cases"],
                "sample_ids": [item["sample_id"] for item in plan["selection"]["items"]],
                "requested_caps_usd": {
                    "generation": plan["generation"]["requested_run_cap_usd"],
                    "review": plan["review"]["requested_total_cap_usd"],
                    "combined": round(
                        plan["generation"]["requested_run_cap_usd"] + plan["review"]["requested_total_cap_usd"],
                        2,
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
