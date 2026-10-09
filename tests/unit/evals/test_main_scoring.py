"""A failed request cannot improve quality, and incompatible scores cannot join a comparison."""

import json
import runpy
from pathlib import Path

import pytest

from medops.evals.main_scoring import (
    SCORING_BINDING,
    SCORING_VERSION,
    abstention_metrics,
    bind_run_scoring,
    main_success,
    validate_expectations,
    validate_row_scoring,
)

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("outcome", "codes", "passed"),
    [
        ("escalated", ["insufficient_evidence"], True),
        ("escalated", ["system_failure"], False),
        ("escalated", ["system_failure", "insufficient_evidence"], False),
        ("escalated", ["high_risk_medical"], False),
        ("escalated", [], False),
        ("answered", ["insufficient_evidence"], False),
        ("refused", ["insufficient_evidence"], False),
        ("timeout", [], False),
    ],
)
def test_no_answer_requires_the_expected_behavior_not_merely_no_answer(outcome, codes, passed):
    assert main_success({"kind": "no_answer"}, outcome, [], codes) is passed


def test_answered_with_system_failure_is_not_a_success_even_with_all_gold():
    item = {"kind": "answerable", "required_gold_groups": [["a"], ["b"]]}
    assert main_success(item, "answered", ["a", "b"])
    assert not main_success(item, "answered", ["a", "b"], ["system_failure"])
    assert not main_success(item, "answered", ["a"])


@pytest.mark.parametrize("item", [{"kind": "unknown"}, {"kind": "no_answer", "expected_behaviour": "refuse"}])
def test_uncalibrated_expectations_fail_preflight(item):
    with pytest.raises(ValueError):
        validate_expectations([item])


def test_diagnostics_keep_failures_in_denominator_and_include_conflict_in_false_abstention():
    rows = [
        {"kind": "no_answer", "outcome": "escalated", "reason_codes": ["insufficient_evidence"]},
        {"kind": "no_answer", "outcome": "escalated", "reason_codes": ["system_failure", "insufficient_evidence"]},
        {"kind": "no_answer", "outcome": "answered", "reason_codes": []},
        {"kind": "conflict", "outcome": "escalated", "reason_codes": ["insufficient_evidence"]},
        {"kind": "answerable", "outcome": "escalated", "reason_codes": ["system_failure"]},
    ]
    metrics = abstention_metrics(rows)
    assert metrics["no_answer_correct"] == {"numerator": 1, "denominator": 3, "rate": 1 / 3}
    assert metrics["false_abstention_answerable_including_conflict"]["rate"] == 0.5
    assert metrics["system_failure"]["rate"] == 0.4
    assert metrics["no_answer_system_failures"] == 1 and metrics["no_answer_other_failures"] == 1
    assert abstention_metrics([])["no_answer_correct"]["rate"] is None


def test_score_binding_is_idempotent_and_refuses_changed_rules(tmp_path):
    bind_run_scoring(tmp_path)
    bind_run_scoring(tmp_path)
    binding = tmp_path / "scoring_binding.json"
    assert json.loads(binding.read_text()) == SCORING_BINDING
    binding.write_text(json.dumps({**SCORING_BINDING, "version": "another"}))
    with pytest.raises(ValueError, match="scoring differs"):
        bind_run_scoring(tmp_path)


def test_legacy_rows_cannot_acquire_a_new_binding(tmp_path):
    (tmp_path / "rows.jsonl").write_text('{"success":true}\n')
    with pytest.raises(ValueError, match="no scoring binding"):
        bind_run_scoring(tmp_path)
    assert not (tmp_path / "scoring_binding.json").exists()


def test_mixed_row_versions_are_rejected_even_with_an_external_binding():
    with pytest.raises(ValueError, match="row scoring version"):
        validate_row_scoring([{"scoring_version": SCORING_VERSION}, {"success": True}])


def test_legacy_default_expectation_matches_all_three_frozen_main_sources():
    for version in (1, 2, 3):
        path = REPO / f"evals/main_set/main-v{version}-provisional/samples.jsonl"
        samples = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        expected = [s["expected_behaviour"] for s in samples if not s.get("answerable", True)]
        assert len(expected) == 61 and set(expected) == {"insufficient_evidence"}


def test_replay_export_uses_new_scores_and_preserves_old_label_rule():
    builder = runpy.run_path(str(REPO / "evals/replay/tools/build_replay_set.py"))
    legacy = {"kind": "no_answer", "outcome": "escalated", "reason_codes": ["system_failure"]}
    current = {**legacy, "scoring_version": SCORING_VERSION, "expected_behaviour": "insufficient_evidence"}
    assert builder["label_main"](legacy) == ("good", "no_answer_abstained")
    assert builder["label_main"](current) == ("bad", "system_failure")
    current.update(dept="PV", query="q")
    item = builder["build_main_items"]({}, {"ms-x": current}, {})[0]
    assert item["expected_behaviour"] == "insufficient_evidence"
    assert item["scoring_version"] == SCORING_VERSION and item["label"] == "bad"
