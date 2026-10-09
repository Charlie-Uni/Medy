"""Translation overlaps independent retrieval under a bounded process pool without changing query fusion inputs."""

from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain import CandidateRef, Dept, SourceRank, UserContext
from medops.harness import retrieval_port as rp
from medops.harness.retrieval_port import ProductionRetrieval, RetrievalRequest
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.query_translation import TranslationPool
from medops.retrieval.recheck import RecheckResult
from medops.retrieval.rerank import OverlapReranker
from tests.unit.harness._fixtures import evidence


def test_translation_pool_bounds_pending_work_and_propagates_context():
    pool = TranslationPool(workers=1, capacity=1, queue_wait_s=0.01)
    started, release = threading.Event(), threading.Event()
    trace = contextvars.ContextVar("trace", default="missing")
    trace.set("request-1")

    def blocked(_query):
        started.set()
        release.wait(2)
        return trace.get()

    try:
        first = pool.submit(blocked, "q1")
        assert started.wait(1)
        with pytest.raises(InfrastructureError) as caught:
            pool.submit(blocked, "q2")
        assert caught.value.code is ErrorCode.dependency_timeout and caught.value.retryable
        release.set()
        assert first.result(timeout=1) == "request-1"
    finally:
        release.set()
        pool.shutdown()


def _port(pool, translator):
    @contextmanager
    def conn_for_user(_user):
        yield object()

    return ProductionRetrieval(
        conn_for_user=conn_for_user,
        lexical_factory=lambda _conn: SimpleNamespace(versions="lex-v1"),
        vector_factory=lambda _conn: SimpleNamespace(versions="vec-v1"),
        reranker=OverlapReranker(),
        config=HybridConfig(),
        translator=translator,
        translation_pool=pool,
    )


def _request():
    return RetrievalRequest(query="原始问题", user=UserContext(user_id="u", dept=Dept.MA), as_of=date(2026, 10, 9))


def _result(query):
    cid = "c-translated" if query == "translated query" else "c-original"
    candidate = CandidateRef(chunk_id=cid, source_ranks=(SourceRank(source="lexical", rank=1),))
    hybrid = SimpleNamespace(fused_ids=[cid], candidate_refs=(candidate,))
    checked = RecheckResult(
        as_of=_request().as_of,
        historical_allowed=False,
        evidence=(evidence(cid, query),),
        rejected=(),
    )
    return hybrid, checked


def test_translation_starts_before_original_retrieval_and_then_joins_fusion(monkeypatch):
    pool = TranslationPool(workers=1, capacity=1)
    translation_started, allow_translation = threading.Event(), threading.Event()
    searched = []

    def translate(_query):
        translation_started.set()
        assert allow_translation.wait(1)
        return "translated query"

    def retrieve(_conn, _lexical, _vector, query, **_kwargs):
        searched.append(query)
        if query == "原始问题":
            assert translation_started.wait(1)
            allow_translation.set()
        return _result(query)

    monkeypatch.setattr(rp, "retrieve_evidence", retrieve)
    try:
        candidates, accepted, rejected = _port(pool, translate)._search(_request(), ["原始问题"], "原始问题")
    finally:
        allow_translation.set()
        pool.shutdown()
    assert searched == ["原始问题", "translated query"]
    assert {c.chunk_id for c in candidates} == {"c-original", "c-translated"}
    assert {e.citation.chunk_id for e in accepted} == {"c-original", "c-translated"} and not rejected


def test_saturated_pool_fails_closed_before_searching(monkeypatch):
    pool = TranslationPool(workers=1, capacity=1, queue_wait_s=0.01)
    occupied, release = threading.Event(), threading.Event()
    blocker = pool.submit(lambda _q: occupied.set() or release.wait(2), "occupied")
    assert blocker is not None and occupied.wait(1)
    calls, searched = [], []

    def translate(_query):
        calls.append(threading.current_thread().name)
        return "translated query"

    def retrieve(_conn, _lexical, _vector, query, **_kwargs):
        searched.append(query)
        return _result(query)

    monkeypatch.setattr(rp, "retrieve_evidence", retrieve)
    try:
        with pytest.raises(InfrastructureError) as caught:
            _port(pool, translate)._search(_request(), ["原始问题"], "原始问题")
    finally:
        release.set()
        blocker.result(timeout=1)
        pool.shutdown()
    assert caught.value.code is ErrorCode.dependency_timeout and caught.value.retryable
    assert calls == [] and searched == []
