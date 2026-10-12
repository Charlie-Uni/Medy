"""The single call boundary for vector retrieval (mirror of `medops.retrieval.lexical.boundary`)."""

from __future__ import annotations

from collections.abc import Sequence

from medops.retrieval.boundary import MAX_K, run_search
from medops.retrieval.vector.contracts import VectorRetriever, VectorSearchResult, VectorVersions

__all__ = ["MAX_K", "run_vector_search"]


def run_vector_search(
    retriever: VectorRetriever,
    query: str,
    k: int,
    expected: VectorVersions,
    *,
    allow_historical: bool = False,
    doc_ids: Sequence[str] | None = None,
) -> VectorSearchResult:
    return run_search(
        retriever,
        query,
        k,
        expected,
        result_model=VectorSearchResult,
        conflict_message="vector index and query versions differ; rebuild the index or use the matching provider",
        allow_historical=allow_historical,
        doc_ids=doc_ids,
    )
