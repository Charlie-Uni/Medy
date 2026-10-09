"""Latency reports use observed nearest-rank values, including zeros and ties."""

import pytest

from medops.evals.statistics import nearest_rank


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [
        ([], 0.95, None),
        ([4.0], 0.95, 4.0),
        ([4.0, 1.0, 3.0, 2.0], 0.5, 2.0),  # not the interpolated median, 2.5
        (list(range(1, 31)), 0.95, 29),  # the capacity run uses 30 samples per level
        ([9.0, 0.0, 0.0, 1.0], 0.5, 0.0),
        ([3.0, 1.0, 2.0], 0.0, 1.0),
        ([3.0, 1.0, 2.0], 1.0, 3.0),
    ],
)
def test_latency_percentiles(values, p, expected):
    original = list(values)
    assert nearest_rank(values, p) == expected
    assert values == original
