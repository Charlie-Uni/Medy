"""Pure scoring for the DEC-001 lexical comparison (ADR-0002, baseline 5.9).

- `strict_recall(hit_golds, required)`: one query's Lexical Recall@K = |required ∩ retrieved| / |required|.
  "Strict macro" recall is the plain mean of that per-query value over all queries; a query whose golds are
  unmappable contributes its misses (they stay in the denominator).
- slices, departments and script variants (zh-Hans / zh-Hant of the gold document) are reported as
  macro means over the queries that carry the label; a label with fewer than `min_support` queries is
  still computed but flagged so a report cannot silently treat a diagnostic figure as a gate.
- `paired_bootstrap_difference`: query-level percentile bootstrap of the difference of strict macro recall
  between two candidates over the SAME query set (fixed seed, fixed resample count) -> point estimate and
  two-sided CI.
- `p95_nearest_rank`: nearest-rank P95 (ceil(0.95 * n)), warm-up excluded by the caller.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


def strict_recall(retrieved: Iterable[str], required: Sequence[str]) -> float:
    """Per-query strict recall: fraction of required gold chunk groups that appear in `retrieved`.

    `required` is a sequence of gold chunk-id groups encoded as comma-joined alternatives? No: each element is
    ONE gold's mapped chunk id set joined by '|'; the gold counts as hit when ANY of its mapped chunk ids was
    retrieved (a key interval can be covered by more than one chunk only when spans overlap). An empty
    alternative set (unmappable gold) can never be hit."""
    if not required:
        raise ValueError("a query must have at least one required gold")
    got = set(retrieved)
    hits = 0
    for gold in required:
        alternatives = {alt for alt in gold.split("|") if alt}
        if alternatives and alternatives & got:
            hits += 1
    return hits / len(required)


def macro_mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


@dataclass(frozen=True)
class LabelledRecall:
    label: str
    support: int
    recall: float | None
    diagnostic_only: bool  # support below the pre-registered minimum for a gate


def grouped_recall(
    per_query: Mapping[str, float], labels: Mapping[str, Sequence[str]], *, min_support: int
) -> list[LabelledRecall]:
    """Macro recall per label. `labels` maps a label to the query ids carrying it (a query may carry many)."""
    out = []
    for label in sorted(labels):
        ids = [q for q in labels[label] if q in per_query]
        values = [per_query[q] for q in ids]
        out.append(
            LabelledRecall(
                label=label, support=len(ids), recall=macro_mean(values), diagnostic_only=len(ids) < min_support
            )
        )
    return out


@dataclass(frozen=True)
class PairedDifference:
    point: float  # macro(b) - macro(a) in percentage points
    ci_low: float
    ci_high: float
    resamples: int
    seed: int
    level: float


def paired_bootstrap_difference(
    a: Mapping[str, float], b: Mapping[str, float], *, resamples: int, seed: int, level: float
) -> PairedDifference:
    """Percentile bootstrap over queries of mean(b) - mean(a), in percentage points. Both mappings must
    cover exactly the same query ids; resampling is with replacement over query ids, identical pairs."""
    if set(a) != set(b) or not a:
        raise ValueError("paired bootstrap needs the same non-empty query set for both candidates")
    if not 0 < level < 1 or resamples < 1:
        raise ValueError("invalid bootstrap parameters")
    ids = sorted(a)
    diffs = [b[q] - a[q] for q in ids]
    n = len(diffs)
    point = 100.0 * sum(diffs) / n
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        samples.append(100.0 * total / n)
    samples.sort()
    alpha = (1 - level) / 2
    low = samples[_percentile_index(alpha, resamples)]
    high = samples[_percentile_index(1 - alpha, resamples)]
    return PairedDifference(point=point, ci_low=low, ci_high=high, resamples=resamples, seed=seed, level=level)


def _percentile_index(p: float, n: int) -> int:
    """Nearest-rank index into a sorted list of length n for percentile p (0..1)."""
    return min(n - 1, max(0, math.ceil(p * n) - 1))


def p95_nearest_rank(latencies: Sequence[float]) -> float:
    if not latencies:
        raise ValueError("no latencies")
    ordered = sorted(latencies)
    return ordered[_percentile_index(0.95, len(ordered))]


def rankings_identical(rankings: Sequence[Sequence[str]]) -> bool:
    """Reproducibility gate: every repeated execution of a query returned the same ordered candidate list."""
    return all(list(r) == list(rankings[0]) for r in rankings[1:])
