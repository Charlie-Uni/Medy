"""Replay baseline reuse accepts only fully bound, execution-identical baseline measurements."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from medops.core.canonical import canonical_hash
from medops.evals.datasets import read_rows
from medops.evals.main_scoring import SCORING_BINDING, SCORING_VERSION
from medops.evals.run_conditions import FORMAT, attempt_accounting, validate_replay_attempts

_PATH = Path(__file__).resolve().parents[3] / "evals/replay/tools/replay_run.py"
_SPEC = importlib.util.spec_from_file_location("replay_run", _PATH)
rr = importlib.util.module_from_spec(_SPEC)
sys.modules["replay_run"] = rr
_SPEC.loader.exec_module(rr)

BASELINE_VERSIONS = {
    "policy_version": "policy-m3-api-1;arm=baseline",
    "retrieval_version": "a" * 64,
    "skill_version_set": ["label_query@1.0.0"],
    "model_config_version": "answer=x;judge=x",
}
CANDIDATE_VERSIONS = {**BASELINE_VERSIONS, "policy_version": "policy-m3-api-1;arm=candidate"}


def _conditions(*, candidate_marker: str = "old", dataset_hash: str = "h" * 64) -> dict:
    samples = {"rp-0001": "1" * 64, "rs-0001": "2" * 64}
    return {
        "format": FORMAT,
        "source": {"sha256": "s" * 64},
        "environment": {"python": "3.12"},
        "sample_plan": [{"sample_id": key, "sha256": value} for key, value in samples.items()],
        "versions": {
            "baseline": dict(BASELINE_VERSIONS),
            "candidate": {**CANDIDATE_VERSIONS, "candidate_marker": candidate_marker},
        },
        "facts": {"medops_v2": {"database_identity": "db", "sha256": "f" * 64}},
        "configuration": {
            "as_of": "2026-09-24",
            "device": "mps",
            "runs": 3,
            "gate_seed": 1,
            "subset": True,
            "arms": {"baseline": {"retrieval": "released"}, "candidate": {"marker": candidate_marker}},
            "policy_snapshots": {
                "baseline": [{"policy_id": "released"}],
                "candidate": [{"policy_id": candidate_marker}],
            },
        },
        "inputs": {
            "dataset_hash": dataset_hash,
            "dataset_version": "replay-v1",
            "candidate_file_sha256": candidate_marker,
            "scoring": SCORING_BINDING,
        },
    }


def _row(conditions: dict, *, arm: str, run: int, replay_id: str, suffix: str = "") -> dict:
    sample_hashes = {item["sample_id"]: item["sha256"] for item in conditions["sample_plan"]}
    return {
        "attempt_id": f"{arm}-{run}-{replay_id}{suffix}",
        "run_conditions_sha256": canonical_hash(conditions),
        "sample_input_sha256": sample_hashes[replay_id],
        "versions": conditions["versions"][arm],
        "scoring_version": SCORING_VERSION,
        "replay_id": replay_id,
        "arm": arm,
        "run": run,
        "success": True,
        "reason_codes": [],
        "cost_usd": 0.01,
        "model_calls": 1,
    }


def _prev(tmp_path: Path, *, conditions: dict | None = None) -> Path:
    conditions = conditions or _conditions()
    prev = tmp_path / "2026-09-25-replay-eval-v1-rrf40"
    prev.mkdir()
    binding_hash = canonical_hash(conditions)
    (prev / "run_conditions.json").write_text(
        json.dumps({"sha256": binding_hash, "conditions": conditions}), encoding="utf-8"
    )
    (prev / "results.json").write_text(
        json.dumps(
            {
                "scoring": SCORING_BINDING,
                "run_conditions_sha256": binding_hash,
                "baseline_reuse_identity_sha256": rr.baseline_reuse_identity(conditions),
            }
        ),
        encoding="utf-8",
    )
    rows = [
        _row(conditions, arm=arm, run=run, replay_id=replay_id)
        for run in (1, 2, 3)
        for arm in ("baseline", "candidate")
        for replay_id in ("rp-0001", "rs-0001")
    ]
    (prev / "rows.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return prev


def test_copies_only_baseline_attempts_and_rebinds_them_to_current_run(tmp_path):
    previous = _conditions(candidate_marker="old")
    current = _conditions(candidate_marker="new")
    prev = _prev(tmp_path, conditions=previous)
    out = tmp_path / "new" / "rows.jsonl"
    out.parent.mkdir()

    assert rr.seed_baseline_rows(prev, out, conditions=current, runs=2) == 4
    rows = read_rows(out)
    assert {row["arm"] for row in rows} == {"baseline"}
    assert {row["run"] for row in rows} == {1, 2}
    assert all(row["reused_from"] == prev.name for row in rows)
    assert all(row["source_attempt_id"] and row["source_run_conditions_sha256"] for row in rows)
    validate_replay_attempts(rows, current)
    accounting = attempt_accounting(rows)
    assert accounting["reused_attempts"] == 4 and accounting["reused_cost_usd"] == 0.04

    # Resume is idempotent and a candidate-only change does not invalidate a measured baseline.
    assert rr.seed_baseline_rows(prev, out, conditions=current, runs=2) == 0
    assert len(read_rows(out)) == 4


@pytest.mark.parametrize("section", ["source", "environment", "sample_plan", "facts", "baseline_version", "dataset"])
def test_refuses_a_different_baseline_execution_identity(tmp_path, section):
    previous = _conditions()
    current = copy.deepcopy(previous)
    if section == "baseline_version":
        current["versions"]["baseline"]["retrieval_version"] = "b" * 64
    elif section == "dataset":
        current["inputs"]["dataset_hash"] = "x" * 64
    else:
        current[section] = {"changed": True}
    prev = _prev(tmp_path, conditions=previous)
    out = tmp_path / "rows.jsonl"

    with pytest.raises(SystemExit, match="baseline execution identity differs"):
        rr.seed_baseline_rows(prev, out, conditions=current, runs=3)
    assert not out.exists()


@pytest.mark.parametrize(
    "mode",
    ["missing_conditions", "corrupt_conditions", "result_mismatch", "missing_identity", "bad_scoring"],
)
def test_refuses_unbound_or_corrupt_source_before_copying(tmp_path, mode):
    conditions = _conditions()
    prev = _prev(tmp_path, conditions=conditions)
    result_path = prev / "results.json"
    result = json.loads(result_path.read_text())
    if mode == "missing_conditions":
        (prev / "run_conditions.json").unlink()
    elif mode == "corrupt_conditions":
        binding_path = prev / "run_conditions.json"
        binding = json.loads(binding_path.read_text())
        binding["conditions"]["facts"] = {"changed": True}
        binding_path.write_text(json.dumps(binding))
    elif mode == "result_mismatch":
        result["run_conditions_sha256"] = "wrong"
        result_path.write_text(json.dumps(result))
    elif mode == "missing_identity":
        result.pop("baseline_reuse_identity_sha256")
        result_path.write_text(json.dumps(result))
    else:
        result["scoring"] = {**SCORING_BINDING, "version": "legacy"}
        result_path.write_text(json.dumps(result))

    out = tmp_path / "rows.jsonl"
    with pytest.raises(SystemExit):
        rr.seed_baseline_rows(prev, out, conditions=conditions, runs=3)
    assert not out.exists()


def test_copies_failure_and_retry_history_in_order(tmp_path):
    conditions = _conditions()
    prev = _prev(tmp_path, conditions=conditions)
    rows = read_rows(prev / "rows.jsonl")
    first = next(row for row in rows if row["arm"] == "baseline" and row["run"] == 1)
    retry = {**first, "attempt_id": first["attempt_id"] + "-retry", "reason_codes": [], "success": True}
    first["reason_codes"] = ["system_failure"]
    first["success"] = False
    insert_at = rows.index(next(row for row in rows if row["arm"] == "candidate" and row["run"] == 1))
    rows.insert(insert_at, retry)
    (prev / "rows.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    out = tmp_path / "new" / "rows.jsonl"
    out.parent.mkdir()
    assert rr.seed_baseline_rows(prev, out, conditions=conditions, runs=1) == 3
    copied = read_rows(out)
    validate_replay_attempts(copied, conditions)
    attempts = [row for row in copied if row["replay_id"] == first["replay_id"]]
    assert [row["reason_codes"] for row in attempts] == [["system_failure"], []]


@pytest.mark.parametrize("mode", ["missing", "unresolved_failure"])
def test_refuses_an_incomplete_baseline(tmp_path, mode):
    conditions = _conditions()
    prev = _prev(tmp_path, conditions=conditions)
    rows = read_rows(prev / "rows.jsonl")
    target = next(row for row in rows if row["arm"] == "baseline" and row["run"] == 2 and row["replay_id"] == "rp-0001")
    if mode == "missing":
        rows.remove(target)
    else:
        target["reason_codes"] = ["system_failure"]
        target["success"] = False
    (prev / "rows.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    out = tmp_path / "rows.jsonl"
    with pytest.raises(SystemExit, match="incomplete|unresolved system failures"):
        rr.seed_baseline_rows(prev, out, conditions=conditions, runs=2)
    assert not out.exists()
