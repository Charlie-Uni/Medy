"""Common request and adapter-result checks. Public channel wrappers retain their typed version contracts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar, cast

from pydantic import BaseModel, ValidationError

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.knowledge.normalization import normalize_text
from medops.retrieval.contracts import LexicalSearchResult
from medops.retrieval.vector.contracts import VectorSearchResult

MAX_K = 20  # Both retrieval channels use K=20; independent of the reranker/evidence cap.
R = TypeVar("R", bound=LexicalSearchResult | VectorSearchResult)


class _Retriever(Protocol):
    @property
    def versions(self) -> BaseModel: ...

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> LexicalSearchResult | VectorSearchResult: ...


def run_search(
    retriever: _Retriever,
    query: str,
    k: int,
    expected: BaseModel,
    *,
    result_model: type[R],
    conflict_message: str,
    allow_historical: bool,
    doc_ids: Sequence[str] | None,
) -> R:
    if isinstance(k, bool) or not isinstance(k, int):
        raise BusinessError(ErrorCode.invalid_request, "k must be an integer")
    if not 1 <= k <= MAX_K:
        raise BusinessError(ErrorCode.invalid_request, f"k must be between 1 and {MAX_K}")
    if not normalize_text(query):
        raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
    declared = retriever.versions  # Snapshot before the call; never compare with a post-call version.
    if expected != declared:
        raise BusinessError(
            ErrorCode.version_conflict,
            conflict_message,
            detail=f"expected={expected.model_dump()} index={declared.model_dump()}",
        )
    try:
        # Omit this optional keyword for legacy adapters unless the caller supplied a document filter.
        if doc_ids is None:
            result = retriever.search(query, k, allow_historical=allow_historical)
        else:
            result = retriever.search(query, k, allow_historical=allow_historical, doc_ids=doc_ids)
        checked = result_model.model_validate(result.model_dump())  # Never trust model_construct/model_copy.
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
    return cast(R, checked)  # model_validate returns the requested channel model; mypy sees the union bound.
