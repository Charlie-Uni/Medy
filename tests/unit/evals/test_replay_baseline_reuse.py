"""`replay_run.py --baseline-from`: a finished run's baseline arm is copied only when the replay set and the baseline
versions are identical, only the requested number of runs, never the candidate arm, and every copied row says where
it came from (record 90)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[3] / "evals/replay/tools/replay_run.py"
_SPEC = importlib.util.spec_from_file_location("replay_run", _PATH)
rr = importlib.util.module_from_spec(_SPEC)
sys.modules["replay_run"] = rr
_SPEC.loader.exec_module(rr)

VERSIONS = {
    "policy_version": "policy-m3-api-1;arm=baseline",
    "retrieval_version": "a" * 64,
    "skill_version_set": ["label_query@1.0.0"],
    "model_config_version": "answer=x;judge=x",
}


def _prev(tmp_path: Path, *, dataset_hash: str = "h" * 64, subset: bool = True, versions: dict = VERSIONS) -> Path:
    prev = tmp_path / "2026-09-25-replay-eval-v1-rrf40"
    prev.mkdir()
    (prev / "results.json").write_text(
        json.dumps(
            {
                "gate": {
                    "replay_set": {"dataset_hash": dataset_hash, "subset": subset},
                    "arms": {"baseline": {"versions": versions}},
                }
            }
        ),
        encoding="utf-8",
    )
    rows = []
    for run in (1, 2, 3):
        for arm in ("baseline", "candidate"):
            rows.append({"replay_id": "rp-0001", "arm": arm, "run": run, "success": True, "cost_usd": 0.01})
            rows.append({"replay_id": "rs-0001", "arm": arm, "run": run, "success": True, "cost_usd": 0.005})
    (prev / "rows.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return prev


def test_copies_only_the_baseline_arm_for_the_requested_runs(tmp_path):
    prev = _prev(tmp_path)
    out = tmp_path / "new" / "rows.jsonl"
    out.parent.mkdir()
    n = rr.seed_baseline_rows(prev, out, versions=dict(VERSIONS), dataset_hash="h" * 64, subset=True, runs=2)
    rows = rr.read_jsonl(out)
    assert n == 4 and len(rows) == 4
    assert {r["arm"] for r in rows} == {"baseline"} and {r["run"] for r in rows} == {1, 2}
    assert all(r["reused_from"] == prev.name for r in rows)
    # idempotent on resume: the same keys are not appended twice
    assert rr.seed_baseline_rows(prev, out, versions=dict(VERSIONS), dataset_hash="h" * 64, subset=True, runs=2) == 0
    assert len(rr.read_jsonl(out)) == 4


def test_refuses_a_different_replay_set_or_released_state(tmp_path):
    prev = _prev(tmp_path)
    out = tmp_path / "rows.jsonl"
    with pytest.raises(SystemExit, match="replay set differs"):
        rr.seed_baseline_rows(prev, out, versions=dict(VERSIONS), dataset_hash="x" * 64, subset=True, runs=3)
    with pytest.raises(SystemExit, match="replay set differs"):
        rr.seed_baseline_rows(prev, out, versions=dict(VERSIONS), dataset_hash="h" * 64, subset=False, runs=3)
    other = {**VERSIONS, "retrieval_version": "b" * 64}
    with pytest.raises(SystemExit, match="baseline versions differ"):
        rr.seed_baseline_rows(prev, out, versions=other, dataset_hash="h" * 64, subset=True, runs=3)
    assert not out.exists()
