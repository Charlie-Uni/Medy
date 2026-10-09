"""Required groups cannot be flattened into interchangeable chunks."""

import runpy
from pathlib import Path

import pytest

from medops.evals.evidence import all_required_evidence, replay_gold_cited

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("groups", "cited", "expected"),
    [
        ([["a", "a-copy"], ["b"]], ["a-copy", "b"], True),
        ([["a", "a-copy"], ["b"]], ["a", "a-copy"], False),
        ([["a"], []], ["a"], False),
        ([], ["a"], False),
        ([["a"]], ["unrelated"], False),
    ],
)
def test_required_evidence_groups(groups, cited, expected):
    assert all_required_evidence(groups, cited) is expected


def test_legacy_replays_keep_their_original_rule_but_explicit_groups_are_strict():
    legacy = {"kind": "answerable", "gold_chunks": ["a", "b"]}
    grouped = {**legacy, "required_gold_groups": [["a"], ["b"]]}
    namespace = runpy.run_path(str(REPO / "evals/replay/tools/replay_run.py"))
    assert replay_gold_cited(legacy, ["a"])
    assert namespace["main_success"](legacy, "answered", ["a"])
    assert not namespace["main_success"](grouped, "answered", ["a"])
    assert namespace["main_success"](grouped, "answered", ["a", "b"])
    assert not replay_gold_cited({**legacy, "required_gold_groups": []}, ["a"])


def test_replay_export_preserves_groups_without_adding_them_to_historical_rows():
    namespace = runpy.run_path(str(REPO / "evals/replay/tools/build_replay_set.py"))
    row = {
        "kind": "answerable",
        "outcome": "answered",
        "gold_cited": False,
        "gold_chunks": ["a", "b"],
        "dept": "PV",
        "query": "joint evidence",
    }
    old = namespace["build_main_items"]({}, {"ms-1": row}, {})[0]
    groups = [["a"], ["b"]]
    new = namespace["build_main_items"]({}, {"ms-1": {**row, "required_gold_groups": groups}}, {})[0]
    assert "required_gold_groups" not in old
    assert new["required_gold_groups"] == groups and new["label"] == "bad"
