"""Hybrid retrieval: lexical + vector through their boundaries, deterministic RRF, then the fact-plane
re-check (M1-17 core; baseline 5.2, INV-DATA-07).

`hybrid_search` runs both channels for one query inside the caller's identity-bound transaction and fuses
their RANKS with `rrf_fuse` (raw scores never enter the fusion). `retrieve_evidence` is the only path to
Evidence: it re-checks the fused candidates in the fact plane, so a candidate that any index still holds
for an archived, revoked or corrupted chunk is dropped before it can be cited. Channels run sequentially
here; running them concurrently is an executor concern (M2/M3) and does not change the result, because the
fusion is a pure function of the two rankings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from medops.domain.state import MAX_CANDIDATES, CandidateRef
from medops.retrieval.contracts import LexicalRetriever, LexicalSearchResult, LexicalVersions
from medops.retrieval.fusion import FusedCandidate, rrf_fuse
from medops.retrieval.lexical.boundary import run_lexical_search
from medops.retrieval.recheck import RecheckResult, recheck_candidates
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.contracts import VectorRetriever, VectorSearchResult, VectorVersions

DEFAULT_RRF_K = 60.0  # baseline 5.2: the initial configuration, part of retrieval_version


@dataclass(frozen=True)
class HybridConfig:
    k_lexical: int = 20
    k_vector: int = 20
    rrf_k: float = DEFAULT_RRF_K
    limit: int = MAX_CANDIDATES  # reranker input cap (baseline 5.2: at most 20)

    def __post_init__(self) -> None:
        if not (1 <= self.k_lexical <= MAX_CANDIDATES and 1 <= self.k_vector <= MAX_CANDIDATES):
            raise ValueError("channel k must be within 1..20")
        if not 1 <= self.limit <= MAX_CANDIDATES:
            raise ValueError("limit must be within 1..20")
        if self.rrf_k <= 0:
            raise ValueError("rrf_k must be positive")

    def rrf_params(self) -> dict[str, Any]:
        return {"k": self.rrf_k, "method": "rrf-rank-only"}

    def candidate_limits(self) -> dict[str, int]:
        return {"lexical_k": self.k_lexical, "vector_k": self.k_vector, "fused_limit": self.limit}


@dataclass(frozen=True)
class HybridResult:
    fused: tuple[FusedCandidate, ...]
    lexical: LexicalSearchResult
    vector: VectorSearchResult

    @property
    def candidate_refs(self) -> tuple[CandidateRef, ...]:
        return tuple(CandidateRef(chunk_id=c.chunk_id, source_ranks=c.source_ranks) for c in self.fused)

    @property
    def fused_ids(self) -> list[str]:
        return [c.chunk_id for c in self.fused]


def hybrid_search(
    lexical: LexicalRetriever,
    vector: VectorRetriever,
    query: str,
    *,
    config: HybridConfig,
    lexical_expected: LexicalVersions,
    vector_expected: VectorVersions,
) -> HybridResult:
    lex = run_lexical_search(lexical, query, config.k_lexical, expected=lexical_expected)
    vec = run_vector_search(vector, query, config.k_vector, expected=vector_expected)
    fused = rrf_fuse(
        {"lexical": [c.chunk_id for c in lex.candidates], "vector": [c.chunk_id for c in vec.candidates]},
        k=config.rrf_k,
        limit=config.limit,
    )
    return HybridResult(tuple(fused), lex, vec)


def retrieve_evidence(
    conn: Any,
    lexical: LexicalRetriever,
    vector: VectorRetriever,
    query: str,
    *,
    config: HybridConfig,
    lexical_expected: LexicalVersions,
    vector_expected: VectorVersions,
    as_of: date | None = None,
    allow_historical: bool = False,
) -> tuple[HybridResult, RecheckResult]:
    """Hybrid candidates, then the fact-plane re-check under the same identity transaction."""
    hybrid = hybrid_search(
        lexical, vector, query, config=config, lexical_expected=lexical_expected, vector_expected=vector_expected
    )
    rechecked = recheck_candidates(conn, hybrid.fused_ids, as_of=as_of, allow_historical=allow_historical)
    return hybrid, rechecked


def top_k_ids(rechecked: RecheckResult, k: int) -> Sequence[str]:
    return rechecked.accepted_ids[:k]
