"""Retrieve node port: the harness sees one call that returns rechecked, reranked Evidence (baseline 5.2).

`ProductionRetrieval` composes the M1 pieces (bounded rewrite -> hybrid search -> fact-plane recheck ->
reranker) inside the caller's identity-bound transaction. Tests use a fake port; the port never returns
candidates as facts (only `evidence` may be cited) and never exceeds the state caps.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Protocol

from medops.domain.common import DomainModel, NonEmptyStr
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.state import MAX_CANDIDATES, MAX_EVIDENCE, CandidateRef
from medops.retrieval.contracts import LexicalRetriever, LexicalVersions
from medops.retrieval.hybrid import HybridConfig, retrieve_evidence
from medops.retrieval.recheck import Rejection
from medops.retrieval.rerank import Reranker, rerank_evidence
from medops.retrieval.rewrite import Glossary, rewrite
from medops.retrieval.vector.contracts import VectorRetriever, VectorVersions


class RetrievalRequest(DomainModel):
    query: NonEmptyStr
    user: UserContext
    historical_requested: bool = False
    as_of: date | None = None
    session_entities: tuple[Entity, ...] = ()


class RetrievalOutcome(DomainModel):
    rewritten_queries: tuple[NonEmptyStr, ...]
    candidates: tuple[CandidateRef, ...]
    evidence: tuple[Evidence, ...]
    rejected: tuple[Rejection, ...] = ()
    degraded: bool = False  # a channel failed and the result is partial (baseline 5.3 degradation rule)
    detail: str = ""

    def model_post_init(self, __context: Any) -> None:
        if len(self.candidates) > MAX_CANDIDATES or len(self.evidence) > MAX_EVIDENCE:
            raise ValueError("retrieval outcome exceeds the state caps (20 candidates / 8 evidence)")


class RetrievalPort(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalOutcome: ...


class ProductionRetrieval:
    def __init__(
        self,
        *,
        conn_for_user: Callable[[UserContext], AbstractContextManager[Any]],
        lexical: LexicalRetriever,
        vector: VectorRetriever,
        reranker: Reranker,
        config: HybridConfig,
        lexical_versions: LexicalVersions,
        vector_versions: VectorVersions,
        glossary: Glossary | None = None,
    ) -> None:
        self._conn_for_user = conn_for_user
        self._lexical = lexical
        self._vector = vector
        self._reranker = reranker
        self._config = config
        self._lv = lexical_versions
        self._vv = vector_versions
        self._glossary = glossary

    def retrieve(self, request: RetrievalRequest) -> RetrievalOutcome:
        rw = rewrite(request.query, entities=request.session_entities, glossary=self._glossary)
        query = rw.queries[0]
        with self._conn_for_user(request.user) as conn:
            hybrid, rechecked = retrieve_evidence(
                conn,
                self._lexical,
                self._vector,
                query,
                config=self._config,
                lexical_expected=self._lv,
                vector_expected=self._vv,
                as_of=request.as_of,
                allow_historical=request.historical_requested,
            )
        ranked = rerank_evidence(self._reranker, query, rechecked.evidence)
        evidence = tuple(r.evidence for r in ranked)[:MAX_EVIDENCE]
        return RetrievalOutcome(
            rewritten_queries=rw.queries,
            candidates=hybrid.candidate_refs[:MAX_CANDIDATES],
            evidence=evidence,
            rejected=rechecked.rejected,
        )
