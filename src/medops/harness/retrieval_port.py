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

from medops.core.telemetry import annotate, span
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
    """Composes the M1 retrieval stack per call. `conn_for_user` must open the caller's identity-bound transaction
    (RLS context set server-side); the channel retrievers are built inside it because they hold the connection.
    Expected channel versions are pinned at construction when known, otherwise captured from the first call and
    enforced afterwards (a version change between calls is refused by the M1 boundaries)."""

    def __init__(
        self,
        *,
        conn_for_user: Callable[[UserContext], AbstractContextManager[Any]],
        lexical_factory: Callable[[Any], LexicalRetriever],
        vector_factory: Callable[[Any], VectorRetriever],
        reranker: Reranker,
        config: HybridConfig,
        lexical_versions: LexicalVersions | None = None,
        vector_versions: VectorVersions | None = None,
        glossary: Glossary | None = None,
    ) -> None:
        self._conn_for_user = conn_for_user
        self._lexical_factory = lexical_factory
        self._vector_factory = vector_factory
        self._reranker = reranker
        self._config = config
        self._lv = lexical_versions
        self._vv = vector_versions
        self._glossary = glossary

    def retrieve(self, request: RetrievalRequest) -> RetrievalOutcome:
        with span(
            "retrieval.retrieve", dept=request.user.dept.value, historical=request.historical_requested
        ) as current:
            outcome = self._retrieve(request)
            annotate(
                current,
                candidates=len(outcome.candidates),
                evidence=len(outcome.evidence),
                rejected=len(outcome.rejected),
                degraded=outcome.degraded,
            )
            return outcome

    def _retrieve(self, request: RetrievalRequest) -> RetrievalOutcome:
        rw = rewrite(request.query, entities=request.session_entities, glossary=self._glossary)
        query = rw.queries[0]
        with self._conn_for_user(request.user) as conn:
            lexical = self._lexical_factory(conn)
            vector = self._vector_factory(conn)
            if self._lv is None:
                self._lv = lexical.versions
            if self._vv is None:
                self._vv = vector.versions
            hybrid, rechecked = retrieve_evidence(
                conn,
                lexical,
                vector,
                query,
                config=self._config,
                lexical_expected=self._lv,
                vector_expected=self._vv,
                as_of=request.as_of,
                allow_historical=request.historical_requested,
            )
        ranked = rerank_evidence(self._reranker, query, rechecked.evidence[: self._reranker.spec.max_input])
        evidence = tuple(r.evidence for r in ranked)[:MAX_EVIDENCE]
        return RetrievalOutcome(
            rewritten_queries=rw.queries,
            candidates=hybrid.candidate_refs[:MAX_CANDIDATES],
            evidence=evidence,
            rejected=rechecked.rejected,
        )
