"""Retrieval contracts (ADR-0002 `LexicalRetriever` output; baseline 5.2, 3.6).

`LexicalRetriever` is the adapter boundary every lexical implementation (offline BM25 now, the
DEC-001 production candidates later) must satisfy; `LexicalVersions` is the version tuple that
indexes and queries must agree on, and that flows into `retrieval_version`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkRecord(BaseModel):
    """Minimal chunk view accepted by lexical indexes. The caller supplies only chunks that
    already passed database-side ACL, status and effective-time filtering (baseline 3.7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str = Field(min_length=1)
    text: str


class LexicalVersions(BaseModel):
    """Versions that shape lexical results. A query may only run against an index built with the
    same tuple (baseline 3.6: mismatch is rejected, never tolerated)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retriever_version: str = Field(min_length=1)
    tokenizer_version: str = Field(min_length=1)
    dictionary_version: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)


class LexicalCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    chunk_id: str = Field(min_length=1)
    raw_score: Annotated[float, Field(allow_inf_nan=False)]
    rank: int = Field(ge=1)


class LexicalSearchResult(BaseModel):
    """Result-level contract. `raw_score` is for traces and diagnostics only; RRF uses `rank`.
    `returned_count` is the number of candidates after all database-side filtering; when it is
    below `requested_k` the retriever must set `candidate_exhausted=True` (ADR-0002 hard gate 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidates: tuple[LexicalCandidate, ...]
    requested_k: int = Field(ge=1)
    returned_count: int = Field(ge=0)
    candidate_exhausted: bool
    retriever_version: str = Field(min_length=1)
    tokenizer_version: str = Field(min_length=1)
    dictionary_version: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> LexicalSearchResult:
        if self.returned_count != len(self.candidates):
            raise ValueError("returned_count must equal len(candidates)")
        if self.returned_count > self.requested_k:
            raise ValueError("returned_count must not exceed requested_k")
        if self.candidate_exhausted != (self.returned_count < self.requested_k):
            raise ValueError(
                "candidate_exhausted must be True exactly when fewer than requested_k candidates were returned"
            )
        ranks = [c.rank for c in self.candidates]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("ranks must be 1..n in order")
        if len({c.chunk_id for c in self.candidates}) != len(self.candidates):
            raise ValueError("chunk_id must be unique within a result")
        for earlier, later in zip(self.candidates, self.candidates[1:], strict=False):
            if later.raw_score > earlier.raw_score:
                raise ValueError("raw_score must be non-increasing along rank")
            if later.raw_score == earlier.raw_score and later.chunk_id <= earlier.chunk_id:
                raise ValueError("equal raw_score must be ordered by chunk_id ascending (baseline 3.7)")
        return self

    @property
    def versions(self) -> LexicalVersions:
        return LexicalVersions(
            retriever_version=self.retriever_version,
            tokenizer_version=self.tokenizer_version,
            dictionary_version=self.dictionary_version,
            normalization_version=self.normalization_version,
        )


class LexicalRetriever(Protocol):
    """Adapter boundary. `versions` is the tuple the current index was BUILT with; it may only change
    by rebuilding the index, and a query configuration that drifted from it must be refused by the
    adapter. Authorization is not provided here: the offline reference receives a pre-authorized
    corpus, production adapters filter inside a database transaction bound to the trusted identity.
    `medops.retrieval.lexical.boundary` enforces the rest of the contract."""

    @property
    def versions(self) -> LexicalVersions: ...

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> LexicalSearchResult: ...
