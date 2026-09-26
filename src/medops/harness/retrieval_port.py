"""Retrieve node port: the harness sees one call that returns rechecked, reranked Evidence (baseline 5.2).

`ProductionRetrieval` composes the M1 pieces (bounded rewrite -> hybrid search -> fact-plane recheck ->
reranker) inside the caller's identity-bound transaction. Tests use a fake port; the port never returns
candidates as facts (only `evidence` may be cited) and never exceeds the state caps.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Protocol

from medops.core.errors import InfrastructureError
from medops.core.telemetry import annotate, span
from medops.domain.common import DomainModel, NonEmptyStr
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.state import MAX_CANDIDATES, MAX_EVIDENCE, CandidateRef
from medops.retrieval.contracts import LexicalRetriever, LexicalVersions
from medops.retrieval.doc_focus import FOCUS_K, focus_documents, load_documents
from medops.retrieval.hybrid import HybridConfig, fuse_rankings, retrieve_evidence
from medops.retrieval.recheck import RecheckResult, Rejection, recheck_candidates
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
        multi_query: bool = False,
        doc_focus: bool = False,
        translator: Callable[[str], str | None] | None = None,
    ) -> None:
        self._conn_for_user = conn_for_user
        self._lexical_factory = lexical_factory
        self._vector_factory = vector_factory
        self._reranker = reranker
        self._config = config
        self._lv = lexical_versions
        self._vv = vector_versions
        self._glossary = glossary
        # record 93: the rewriter has always produced up to three queries, but only the first was searched. With
        # `multi_query` (a released retrieval parameter) every rewritten query is searched and the per-query fused
        # rankings are fused again by RRF; the reranker still judges against the user's own query.
        self._multi_query = multi_query
        # record 94: when the question names a corpus document (brand, ICH code, GVP module, Chinese title), that
        # document's own chunks are searched too and join the fusion (`doc_focus`, a released retrieval parameter)
        self._doc_focus = doc_focus
        # record 95: an English rendering of a Chinese question becomes one more search query (never evidence)
        self._translator = translator

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
        queries = list(rw.queries) if self._multi_query else [query]
        if self._translator is not None:
            translated = self._translator(request.query)
            if translated and translated not in queries:
                queries.append(translated)
        with self._conn_for_user(request.user) as conn:
            lexical = self._lexical_factory(conn)
            vector = self._vector_factory(conn)
            if self._lv is None:
                self._lv = lexical.versions
            if self._vv is None:
                self._vv = vector.versions
            with span("retrieval.fact_plane", queries=len(queries)):
                results = [
                    retrieve_evidence(
                        conn,
                        lexical,
                        vector,
                        q,
                        config=self._config,
                        lexical_expected=self._lv,
                        vector_expected=self._vv,
                        as_of=request.as_of,
                        allow_historical=request.historical_requested,
                    )
                    for q in queries
                ]
                focus_rankings: dict[str, list[str]] = {}
                focus_rechecked: list[RecheckResult] = []
                if self._doc_focus:
                    focused = focus_documents(request.query, load_documents(conn))
                    for i, doc in enumerate(focused, start=1):
                        try:
                            lex_ids = [
                                c.chunk_id
                                for c in lexical.search(
                                    query, FOCUS_K, allow_historical=request.historical_requested, doc_ids=[doc.doc_id]
                                ).candidates
                            ]
                            vec_ids = [
                                c.chunk_id
                                for c in vector.search(
                                    query, FOCUS_K, allow_historical=request.historical_requested, doc_ids=[doc.doc_id]
                                ).candidates
                            ]
                        except InfrastructureError:
                            continue  # a starved or failing focused scan never blocks the corpus-wide answer
                        if lex_ids:
                            focus_rankings[f"focus{i}:lexical"] = lex_ids
                        if vec_ids:
                            focus_rankings[f"focus{i}:vector"] = vec_ids
                    extra = list(dict.fromkeys(cid for ids in focus_rankings.values() for cid in ids))
                    if extra:
                        focus_rechecked.append(
                            recheck_candidates(
                                conn, extra, as_of=request.as_of, allow_historical=request.historical_requested
                            )
                        )
        if len(results) == 1 and not focus_rankings:
            hybrid, rechecked = results[0]
            candidates = hybrid.candidate_refs[:MAX_CANDIDATES]
            accepted: tuple[Evidence, ...] = rechecked.evidence
            rejected: tuple[Rejection, ...] = rechecked.rejected
        else:
            rankings: dict[str, Sequence[str]] = {f"q{i}": h.fused_ids for i, (h, _) in enumerate(results, start=1)}
            rankings.update(focus_rankings)
            fused = fuse_rankings(rankings, k=self._config.rrf_k, limit=self._config.limit)
            candidates = tuple(CandidateRef(chunk_id=c.chunk_id, source_ranks=c.source_ranks) for c in fused)[
                :MAX_CANDIDATES
            ]
            by_id: dict[str, Evidence] = {}
            seen_rejections: dict[str, Rejection] = {}
            for _, rc in [*results, *((None, r) for r in focus_rechecked)]:
                for e in rc.evidence:
                    by_id.setdefault(e.citation.chunk_id, e)
                for r in rc.rejected:
                    seen_rejections.setdefault(r.chunk_id, r)
            accepted = tuple(by_id[c.chunk_id] for c in fused if c.chunk_id in by_id)
            rejected = tuple(r for cid, r in seen_rejections.items() if cid not in by_id)
        with span("retrieval.rerank", inputs=min(len(accepted), self._reranker.spec.max_input)):
            ranked = rerank_evidence(self._reranker, query, accepted[: self._reranker.spec.max_input])
        evidence = tuple(r.evidence for r in ranked)[:MAX_EVIDENCE]
        return RetrievalOutcome(
            rewritten_queries=rw.queries,
            candidates=candidates,
            evidence=evidence,
            rejected=rejected,
        )
