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

from medops.retrieval.boundary import MAX_K, run_search
from medops.retrieval.contracts import LexicalRetriever, LexicalSearchResult, LexicalVersions

__all__ = ["MAX_K", "run_lexical_search"]  # Preserve the existing public import path.


def run_lexical_search(
    retriever: LexicalRetriever,
    query: str,
    k: int,
    expected: LexicalVersions,
    *,
    allow_historical: bool = False,
    doc_ids: Sequence[str] | None = None,
) -> LexicalSearchResult:
    return run_search(
        retriever,
        query,
        k,
        expected,
        result_model=LexicalSearchResult,
        conflict_message="lexical index and query versions differ; rebuild the index or use the matching versions",
        allow_historical=allow_historical,
        doc_ids=doc_ids,
    )
