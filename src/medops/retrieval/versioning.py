"""Composite `retrieval_version` (baseline 3.6, M1-15).

    retrieval_version = SHA-256(canonical_json({
        retriever_version, tokenizer_version, dictionary_version, normalization_version,
        embedding_version, rrf_params, rerank_params, candidate_limits}))

The composite is the only retrieval identifier that may enter cache keys, operation keys and
replay records. The component versions carried by `LexicalSearchResult` / `LexicalVersions`
(retriever, tokenizer, dictionary, normalization) are diagnostics for traces and experiment
reports; changing any component or any parameter yields a different composite, so an index
built under one composite can never be served under another. Concrete values (which
tokenizer, which embedding model, which RRF k) come from DEC-001 / DEC-002; this module only
fixes the function and the input shape so that every future run computes the same bytes.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from medops.core.canonical import canonical_hash
from medops.retrieval.contracts import LexicalVersions

NonEmptyStr = Annotated[str, Field(min_length=1)]
PositiveInt = Annotated[int, Field(ge=1)]

RETRIEVAL_VERSION_FIELDS: tuple[str, ...] = (
    "retriever_version",
    "tokenizer_version",
    "dictionary_version",
    "normalization_version",
    "embedding_version",
    "rrf_params",
    "rerank_params",
    "candidate_limits",
)
"""Exactly the eight members named in baseline 3.6, in the baseline's order (hashing sorts keys anyway)."""


class RetrievalVersionInputs(BaseModel):
    """Everything that shapes retrieval results. Frozen and closed: an unknown field is rejected
    rather than silently left out of the hash."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    retriever_version: NonEmptyStr
    tokenizer_version: NonEmptyStr
    dictionary_version: NonEmptyStr
    normalization_version: NonEmptyStr
    embedding_version: NonEmptyStr
    rrf_params: dict[str, JsonValue]
    """RRF configuration; must contain a positive numeric `k` (baseline 5.2: k=60 is the initial value)."""
    rerank_params: dict[str, JsonValue]
    """Reranker configuration (model, version, thresholds). May be empty when no reranker is configured;
    the empty object is itself part of the hash."""
    candidate_limits: dict[str, PositiveInt]
    """Per-stage candidate caps (for example lexical_k, vector_k, rerank_input, rerank_output); at least one."""

    @model_validator(mode="after")
    def _rules(self) -> RetrievalVersionInputs:
        k = self.rrf_params.get("k")
        if isinstance(k, bool) or not isinstance(k, (int, float)) or k <= 0:
            raise ValueError("rrf_params must contain a positive numeric k")
        if not self.candidate_limits:
            raise ValueError("candidate_limits must not be empty")
        return self

    @classmethod
    def from_lexical(
        cls,
        lexical: LexicalVersions,
        *,
        embedding_version: str,
        rrf_params: dict[str, JsonValue],
        rerank_params: dict[str, JsonValue],
        candidate_limits: dict[str, int],
    ) -> RetrievalVersionInputs:
        return cls(
            retriever_version=lexical.retriever_version,
            tokenizer_version=lexical.tokenizer_version,
            dictionary_version=lexical.dictionary_version,
            normalization_version=lexical.normalization_version,
            embedding_version=embedding_version,
            rrf_params=rrf_params,
            rerank_params=rerank_params,
            candidate_limits=candidate_limits,
        )

    @property
    def lexical(self) -> LexicalVersions:
        """The diagnostic component tuple an index and a query must agree on."""
        return LexicalVersions(
            retriever_version=self.retriever_version,
            tokenizer_version=self.tokenizer_version,
            dictionary_version=self.dictionary_version,
            normalization_version=self.normalization_version,
        )


def compute_retrieval_version(inputs: RetrievalVersionInputs) -> str:
    """SHA-256 hex of the canonical JSON of the eight members (baseline 3.6)."""
    payload = inputs.model_dump(mode="json")
    assert tuple(sorted(payload)) == tuple(sorted(RETRIEVAL_VERSION_FIELDS))
    return canonical_hash(payload)
