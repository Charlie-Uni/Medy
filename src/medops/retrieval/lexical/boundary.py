"""The single call boundary for lexical retrieval (M1-03).

Everything that calls a `LexicalRetriever` goes through `run_lexical_search`, which
- validates the request (k is a strict integer within 1..MAX_K, query non-empty after norm-v1),
- requires the run's fixed `expected` versions and refuses when the index was built with others
  (baseline 3.6): the check is mandatory, never skipped by default,
- snapshots the adapter's declared versions BEFORE the call and re-validates the returned result
  against the contract model and that snapshot, so an adapter that mutates versions during the call,
  builds an invalid result or returns a malformed one fails closed with a non-retryable internal
  error. Business and infrastructure errors raised by the adapter itself propagate unchanged.

Authorization is not provided here: the offline reference receives a pre-authorized corpus, and
production adapters filter inside a database transaction bound to the trusted identity (3.7).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.contracts import LexicalRetriever, LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.normalization import normalize_text

MAX_K = 20  # ADR-0002 experiment setting (K=20 for Lexical Recall@20); not derived from the reranker cap


def run_lexical_search(
    retriever: LexicalRetriever,
    query: str,
    k: int,
    expected: LexicalVersions,
    *,
    allow_historical: bool = False,
    doc_ids: Sequence[str] | None = None,
) -> LexicalSearchResult:
    if isinstance(k, bool) or not isinstance(k, int):
        raise BusinessError(ErrorCode.invalid_request, "k must be an integer")
    if not 1 <= k <= MAX_K:
        raise BusinessError(ErrorCode.invalid_request, f"k must be between 1 and {MAX_K}")
    if not normalize_text(query):
        raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
    declared = retriever.versions  # snapshot before the call
    if expected != declared:
        raise BusinessError(
            ErrorCode.version_conflict,
            "lexical index and query versions differ; rebuild the index or use the matching versions",
            detail=f"expected={expected.model_dump()} index={declared.model_dump()}",
        )
    try:
        if doc_ids is None:
            result = retriever.search(query, k, allow_historical=allow_historical)
        else:
            result = retriever.search(query, k, allow_historical=allow_historical, doc_ids=doc_ids)
        checked = LexicalSearchResult.model_validate(result.model_dump())  # re-validate, never trust model_construct
    except ValidationError as exc:  # an adapter building an invalid result (inside search or here) is an adapter defect
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
