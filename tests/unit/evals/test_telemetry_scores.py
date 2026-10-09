from __future__ import annotations

import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_hash
from medops.evals.main_scoring import SCORING_VERSION
from medops.evals.run_conditions import FORMAT
from medops.evals.telemetry import events_from_run


def run_files(path: Path, *, safety=False, not_exercised=False):
    versions = {"policy_version": "p", "retrieval_version": "r", "model_config_version": "m"}
    conditions = {
        "format": FORMAT,
        "sample_plan": [{"sample_id": "sample-1", "sha256": "sample-hash"}],
        "versions": versions,
        "inputs": {
            "dataset_hash": "dataset-hash",
            "dataset_version": "fixture-provisional",
            "scoring": "safety-checks-code-bound-v1" if safety else {"version": SCORING_VERSION},
        },
    }
    binding = {"conditions": conditions, "sha256": canonical_hash(conditions)}
    dataset = {"dataset_version": "fixture-provisional", "dataset_hash": "dataset-hash"}
    row = {
        "attempt_id": "attempt-1",
        "trace_id": "a" * 32,
        "observed_at": "2026-10-08T00:00:00Z",
        "sample_id": "sample-1",
        "sample_input_sha256": "sample-hash",
        "versions": versions,
        "run_conditions_sha256": binding["sha256"],
        "cost_usd": 0,
        "model_calls": 0,
        "query": "PRIVATE_QUERY",
        "claims": ["PRIVATE_CLAIM"],
        "reason_codes": ["insufficient_evidence"],
        "outcome": "escalated",
        "cited_chunks": [],
    }
    if safety:
        row.update(
            category="fixture", checks=[{"check": "outcome", "ok": True, "detail": "PRIVATE_DETAIL"}], passed=True
        )
        if not_exercised:
            row["not_exercised"] = "PRIVATE_REASON"
    else:
        row.update(kind="no_answer", success=True, scoring_version=SCORING_VERSION)
    (path / "run_conditions.json").write_text(json.dumps(binding))
    (path / "dataset_binding.json").write_text(json.dumps(dataset))
    (path / "rows.jsonl").write_text(json.dumps(row) + "\n")
    return row, binding


def test_main_score_carries_bound_versions_and_no_text(tmp_path):
    run_files(tmp_path)
    events = events_from_run(tmp_path)
    assert len(events) == 1
    body = events[0]["body"]
    assert body["name"] == "main_outcome" and body["value"] == 1 and body["dataType"] == "BOOLEAN"
    assert body["metadata"]["scoring_version"] == SCORING_VERSION
    assert body["metadata"]["dataset_version"] == "fixture-provisional"
    assert body["metadata"]["formal_gate"] is False
    assert "PRIVATE" not in json.dumps(events)


def test_safety_not_exercised_is_status_not_success_or_zero(tmp_path):
    run_files(tmp_path, safety=True, not_exercised=True)
    body = events_from_run(tmp_path)[0]["body"]
    assert body["name"] == "evaluation_status" and body["value"] == "not_exercised"
    assert body["dataType"] == "CATEGORICAL"


def test_safety_scores_measured_checks_only(tmp_path):
    run_files(tmp_path, safety=True)
    assert events_from_run(tmp_path)[0]["body"]["name"] == "safety_checks"


@pytest.mark.parametrize("mutation", ["conditions", "dataset", "row_binding", "score", "no_trace", "no_time"])
def test_drift_missing_identity_and_changed_results_rejected(tmp_path, mutation):
    row, binding = run_files(tmp_path)
    if mutation == "conditions":
        binding["conditions"]["versions"]["policy_version"] = "other"
        (tmp_path / "run_conditions.json").write_text(json.dumps(binding))
    elif mutation == "dataset":
        (tmp_path / "dataset_binding.json").write_text(
            json.dumps({"dataset_version": "other", "dataset_hash": "dataset-hash"})
        )
    else:
        if mutation == "row_binding":
            row["run_conditions_sha256"] = "other"
        elif mutation == "score":
            row["reason_codes"] = ["system_failure"]
        elif mutation == "no_trace":
            row.pop("trace_id")
        elif mutation == "no_time":
            row.pop("observed_at")
        (tmp_path / "rows.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises((ValueError, KeyError)):
        events_from_run(tmp_path)


def test_retry_has_own_trace_and_score_identity(tmp_path):
    row, _ = run_files(tmp_path)
    retry = {**row, "attempt_id": "attempt-2", "trace_id": "b" * 32, "observed_at": "2026-10-09T00:00:00Z"}
    with (tmp_path / "rows.jsonl").open("a") as handle:
        handle.write(json.dumps(retry) + "\n")
    events = events_from_run(tmp_path)
    assert len({e["id"] for e in events}) == len({e["body"]["traceId"] for e in events}) == 2
