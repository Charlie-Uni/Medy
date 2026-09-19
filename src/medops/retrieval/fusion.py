"""Deterministic Reciprocal Rank Fusion (baseline 5.2).

RRF consumes ranks only; raw scores never enter the fusion. `k=60` is the initial
configuration, not a permanent constant, and must be part of `retrieval_version`.
Adapted from the legacy 文枢 project (`app/retrieval/hybrid.py`) as a pure function with an
explicit tie-break by candidate id so that results are reproducible across runs.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from medops.domain.state import SourceRank


class FusedCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    rrf_score: float
    rank: int = Field(ge=1)
    source_ranks: tuple[SourceRank, ...] = Field(min_length=1)


def rrf_fuse(rankings: dict[str, Sequence[str]], k: float = 60.0, limit: int | None = None) -> list[FusedCandidate]:
    """Fuse named rankings (e.g. {"lexical": [...], "vector": [...]}) of chunk ids.

    Each ranking must contain unique ids. The score of an id is the sum over rankings of
    1 / (k + rank) with rank starting at 1. Ties are broken by chunk_id ascending.
    """
    if k <= 0:
        raise ValueError("k must be > 0")
    scores: dict[str, float] = {}
    sources: dict[str, list[SourceRank]] = {}
    for name, ranking in rankings.items():
        if len(set(ranking)) != len(ranking):
            raise ValueError(f"ranking '{name}' contains duplicate ids")
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
            sources.setdefault(chunk_id, []).append(SourceRank(source=name, rank=position))
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return [
        FusedCandidate(chunk_id=chunk_id, rrf_score=score, rank=rank, source_ranks=tuple(sources[chunk_id]))
        for rank, (chunk_id, score) in enumerate(ordered, start=1)
    ]
