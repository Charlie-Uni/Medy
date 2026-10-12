"""Skill smoke attempts keep a stable run identity without reusing trace identities."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _module():
    from medops.evals.tools.harness import skill_smoke

    return skill_smoke


def test_execution_run_id_is_stable_and_attempt_specific():
    module = _module()
    first = module.execution_run_id("run-a", "label_query/positive", 0)
    assert first == module.execution_run_id("run-a", "label_query/positive", 0)
    assert len(first) == 32
    assert first != module.execution_run_id("run-a", "label_query/positive", 1)
    assert first != module.execution_run_id("run-b", "label_query/positive", 0)
