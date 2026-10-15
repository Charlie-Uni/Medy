"""Replay PUBLIC scripted records through the scorer, never a fake Agent benchmark.

No gateway, provider key, database or network import. For real trajectories use
an authorized collector and separate frozen plan; these scripts prove only rubric
mechanics. Do not put this evaluator input, assessment or private gold in planning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from medops.core.canonical import canonical_hash
from medops.core.strict_json import strict_json
from medops.evals.agent.contracts import Assessment, EvaluationPlan, ExecutionRecord
from medops.evals.agent.reporting import aggregate


def evaluate_fixture(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        payload = stream.read(8_000_001)
    if len(payload) > 8_000_000:
        raise ValueError("fixture_limit")
    data = strict_json(payload)
    if not isinstance(data, dict) or set(data) != {"format", "plan", "records", "assessments", "expected"}:
        raise ValueError("invalid_fixture")
    if data["format"] != "pv-agent-scripted-fixture-v1":
        raise ValueError("invalid_fixture")
    plan = EvaluationPlan.model_validate(data["plan"])
    for relative, digest in (
        ("S0-pv-case-spec-v1.json", plan.historical_spec_sha256),
        ("PLAN-02-contract-v2.json", plan.approved_contract_sha256),
    ):
        if hashlib.sha256((path.parent / relative).read_bytes()).hexdigest() != digest:
            raise ValueError("historical_spec_changed")
    if not isinstance(data["records"], list) or not isinstance(data["assessments"], list):
        raise ValueError("invalid_fixture")
    records = tuple(ExecutionRecord.model_validate(row) for row in data["records"])
    assessments = tuple(Assessment.model_validate(row) for row in data["assessments"])
    if any(a.assessor != "scripted_fixture" for a in assessments):
        raise ValueError("not_scripted_fixture")
    report = aggregate(plan, records, assessments)
    rows = report["rows"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid_report")
    projection = [{key: row[key] for key in ("execution_id", "business_completed", "handling_correct")} for row in rows]
    if projection != data["expected"]:
        raise ValueError("development_expectation_mismatch")
    return {
        **report,
        "fixture_sha256": hashlib.sha256(payload).hexdigest(),
        "scripted_records": len(records),
        "hosted_model_calls": 0,
        "api_cost_usd": 0,
        "scripted_expectations_matched": True,
        "report_content_sha256": canonical_hash(report),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate_fixture(args.fixture), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
