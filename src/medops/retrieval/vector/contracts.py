"""Vector retrieval contracts (M1-16; baseline 5.2, 3.7; ADR-0007).

Same shape and invariants as the lexical contract: candidates carry `chunk_id/raw_score/rank`, the result
carries `requested_k/returned_count/candidate_exhausted` and the versions the index was BUILT with. For
vectors the version tuple is `(retriever_version, embedding_version, normalization_version)`; the composite
`retrieval_version` (baseline 3.6) takes `embedding_version` from here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from medops.retrieval.contracts import LexicalCandidate, check_candidates

Candidate = LexicalCandidate  # identical shape: chunk_id, raw_score, rank


class VectorVersions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    retriever_version: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)


class VectorSearchResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    candidates: tuple[Candidate, ...]
    requested_k: int = Field(ge=1)
    returned_count: int = Field(ge=0)
    candidate_exhausted: bool
    retriever_version: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> VectorSearchResult:
        check_candidates(
            self.candidates,
            self.requested_k,
            self.returned_count,
            self.candidate_exhausted,
            exhaustion_message="candidate_exhausted must be True exactly when fewer than requested_k were returned",
        )
        return self

    @property
    def versions(self) -> VectorVersions:
        return VectorVersions(
            retriever_version=self.retriever_version,
            embedding_version=self.embedding_version,
            normalization_version=self.normalization_version,
        )


class VectorRetriever(Protocol):
    @property
    def versions(self) -> VectorVersions: ...

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> VectorSearchResult: ...
