"""Shared nearest-rank percentiles for offline evaluation reports."""

from __future__ import annotations

import math
from collections.abc import Sequence


def nearest_rank(values: Sequence[float], p: float) -> float | None:
    """Return rank ceil(p * n), with p in [0, 1]; empty populations have no percentile.

    Callers own population selection and units. This deliberately does not interpolate,
    round results or discard failures, zeros or repeated values.
    """
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]
