"""The single call boundary for vector retrieval (mirror of `medops.retrieval.lexical.boundary`)."""

from __future__ import annotations

from pydantic import ValidationError

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.lexical.boundary import MAX_K
from medops.retrieval.lexical.normalization import normalize_text
from medops.retrieval.vector.contracts import VectorRetriever, VectorSearchResult, VectorVersions


def run_vector_search(retriever: VectorRetriever, query: str, k: int, expected: VectorVersions) -> VectorSearchResult:
    if isinstance(k, bool) or not isinstance(k, int):
        raise BusinessError(ErrorCode.invalid_request, "k must be an integer")
    if not 1 <= k <= MAX_K:
        raise BusinessError(ErrorCode.invalid_request, f"k must be between 1 and {MAX_K}")
    if not normalize_text(query):
        raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
    declared = retriever.versions
    if expected != declared:
        raise BusinessError(
            ErrorCode.version_conflict,
            "vector index and query versions differ; rebuild the index or use the matching provider",
            detail=f"expected={expected.model_dump()} index={declared.model_dump()}",
        )
    try:
        result = retriever.search(query, k)
        checked = VectorSearchResult.model_validate(result.model_dump())
    except ValidationError as exc:
        raise InfrastructureError(
            ErrorCode.internal_error,
            detail=f"adapter produced an invalid result: {exc.error_count()} error(s)",
            retryable=False,
        ) from None
    if checked.versions != declared:
        raise InfrastructureError(
            ErrorCode.internal_error,
            detail=f"adapter returned versions {checked.versions.model_dump()} != declared {declared.model_dump()}",
            retryable=False,
        )
    if checked.requested_k != k:
        raise InfrastructureError(
            ErrorCode.internal_error,
            detail=f"adapter echoed requested_k={checked.requested_k} for k={k}",
            retryable=False,
        )
    return checked
