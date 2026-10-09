"""Skill smoke attempts keep a stable run identity without reusing trace identities."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _module():
    spec = importlib.util.spec_from_file_location("skill_smoke_ids", REPO / "evals/harness/tools/skill_smoke.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execution_run_id_is_stable_and_attempt_specific():
    module = _module()
    first = module.execution_run_id("run-a", "label_query/positive", 0)
    assert first == module.execution_run_id("run-a", "label_query/positive", 0)
    assert len(first) == 32
    assert first != module.execution_run_id("run-a", "label_query/positive", 1)
    assert first != module.execution_run_id("run-b", "label_query/positive", 0)
