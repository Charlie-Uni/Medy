from __future__ import annotations

import pytest

from medops.evals.experiments import scoring as s


def test_strict_recall_counts_each_required_gold_once_and_never_hits_unmappable_golds():
    assert s.strict_recall(["c1", "c9"], ["c1"]) == 1.0
    assert s.strict_recall(["c9"], ["c1"]) == 0.0
    assert s.strict_recall(["c2"], ["c1|c2", "c3"]) == 0.5  # gold 1 hit through an alternative chunk
    assert s.strict_recall(["c1", "c2", "c3"], ["", "c3"]) == 0.5  # unmappable gold stays a miss
    with pytest.raises(ValueError):
        s.strict_recall(["c1"], [])


def test_grouped_recall_flags_labels_below_the_minimum_support():
    per_query = {"q1": 1.0, "q2": 0.0, "q3": 1.0}
    groups = s.grouped_recall(per_query, {"negation": ["q1", "q2"], "dose_unit": ["q3", "missing"]}, min_support=2)
    by = {g.label: g for g in groups}
    assert by["negation"].recall == 0.5 and by["negation"].support == 2 and not by["negation"].diagnostic_only
    assert by["dose_unit"].recall == 1.0 and by["dose_unit"].support == 1 and by["dose_unit"].diagnostic_only
    assert s.macro_mean([]) is None


def test_paired_bootstrap_is_deterministic_and_brackets_the_point_estimate():
    a = {f"q{i}": (1.0 if i % 4 else 0.0) for i in range(40)}  # 75%
    b = {f"q{i}": (1.0 if i % 8 else 0.0) for i in range(40)}  # 87.5%
    first = s.paired_bootstrap_difference(a, b, resamples=2000, seed=20260920, level=0.95)
    second = s.paired_bootstrap_difference(a, b, resamples=2000, seed=20260920, level=0.95)
    assert first == second
    assert first.point == pytest.approx(12.5)
    assert first.ci_low <= first.point <= first.ci_high and first.ci_low > 0
    same = s.paired_bootstrap_difference(a, a, resamples=500, seed=1, level=0.95)
    assert same.point == 0.0 and same.ci_low == 0.0 == same.ci_high
    with pytest.raises(ValueError):
        s.paired_bootstrap_difference(a, {"q0": 1.0}, resamples=10, seed=1, level=0.95)


def test_p95_nearest_rank_and_reproducibility_gate():
    assert s.p95_nearest_rank([5.0]) == 5.0
    assert s.p95_nearest_rank(list(range(1, 101))) == 95  # ceil(0.95 * 100) = 95th value
    assert s.p95_nearest_rank([3.0, 1.0, 2.0]) == 3.0  # ceil(2.85) = 3rd of 3
    assert s.rankings_identical([["a", "b"], ["a", "b"]]) is True
    assert s.rankings_identical([["a", "b"], ["b", "a"]]) is False
    assert s.rankings_identical([["a"]]) is True
    with pytest.raises(ValueError):
        s.p95_nearest_rank([])
