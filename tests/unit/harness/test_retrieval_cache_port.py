"""The retrieval cache in the production port (M1-19 wired, record 121): a hit skips the searches (and with them the
translation call) but never the fact-plane re-check or the reranker; hit and miss return the same evidence; a
different department, version or epoch is a miss; without a cache nothing changes."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import date

import pytest

from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import CandidateRef, SourceRank
from medops.harness import retrieval_port as rp
from medops.harness.retrieval_port import ProductionRetrieval, RetrievalRequest
from medops.retrieval.cache import CandidateCache, InMemoryCandidateCacheStore
from medops.retrieval.doc_focus import DocRef
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.recheck import RecheckResult, Rejection
from medops.retrieval.rerank import OverlapReranker
from tests.unit.harness._fixtures import evidence

RV = hashlib.sha256(b"retrieval-version").hexdigest()
RV2 = hashlib.sha256(b"retrieval-version-2").hexdigest()
TEXTS = {
    "c1": "成人起始劑量為每日 50 毫克。",
    "c2": "腎功能不全者應調整劑量。",
    "c3": "本品應置於兒童伸手不及之處。",
}
QUERY = "成人 起始 劑量"


def user(dept: Dept = Dept.MA) -> UserContext:
    return UserContext(user_id="u-1", dept=dept, roles=("analyst",), acl_scopes=frozenset({f"{dept.value}:read"}))


class CountingReranker(OverlapReranker):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = 0

    def score(self, query, texts):
        self.calls += 1
        return super().score(query, texts)


class Port(ProductionRetrieval):
    """The real port with the search stage replaced by a counter; cache, re-check call and rerank are the real code."""

    def __init__(self, **kw):
        @contextmanager
        def conn_for_user(_user):
            yield object()

        super().__init__(
            conn_for_user=conn_for_user,
            lexical_factory=lambda c: None,
            vector_factory=lambda c: None,
            reranker=kw.pop("reranker", None) or CountingReranker(),
            config=HybridConfig(),
            **kw,
        )
        self.searches = 0
        self.source_doc_ids = None

    @property
    def reranks(self) -> int:
        return self._reranker.calls

    def _search(self, request, rewritten, query, *, source_doc_ids=None):
        self.searches += 1
        self.source_doc_ids = source_doc_ids
        candidates = tuple(
            CandidateRef(chunk_id=c, source_ranks=(SourceRank(source="lexical", rank=i),))
            for i, c in enumerate(TEXTS, 1)
        )
        return candidates, tuple(evidence(c, t) for c, t in TEXTS.items()), ()


@pytest.fixture
def visible(monkeypatch):
    """What the fact plane would accept right now; the re-check of a cache hit goes through it."""
    allowed = set(TEXTS)
    calls: list[list[str]] = []

    def fake_recheck(conn, cached, inputs):
        ids = [c.chunk_id for c in cached.candidates]
        calls.append(ids)
        return RecheckResult(
            as_of=inputs.as_of,
            historical_allowed=inputs.allow_historical,
            evidence=tuple(evidence(c, TEXTS[c]) for c in ids if c in allowed),
            rejected=tuple(
                Rejection(chunk_id=c, rank=i, reason="not_visible") for i, c in enumerate(ids, 1) if c not in allowed
            ),
        )

    monkeypatch.setattr(rp, "recheck_cached", fake_recheck)
    return allowed, calls


def request(dept: Dept = Dept.MA, query: str = QUERY) -> RetrievalRequest:
    return RetrievalRequest(query=query, user=user(dept), as_of=date(2026, 10, 5))


def test_without_a_cache_every_call_searches(visible):
    port = Port()
    a, b = port.retrieve(request()), port.retrieve(request())
    assert port.searches == 2 and not a.cache_hit and not b.cache_hit
    assert visible[1] == []  # the cache re-check is not involved at all


def test_hit_skips_the_search_and_returns_the_same_candidates_and_evidence(visible):
    cache = CandidateCache(InMemoryCandidateCacheStore())
    port = Port(cache=cache, cache_versions=(RV, "policy-1"))
    miss = port.retrieve(request())
    hit = port.retrieve(request())
    assert port.searches == 1 and not miss.cache_hit and hit.cache_hit
    assert hit.candidates == miss.candidates
    assert [e.citation.chunk_id for e in hit.evidence] == [e.citation.chunk_id for e in miss.evidence]
    assert [e.text for e in hit.evidence] == [e.text for e in miss.evidence]
    assert visible[1] == [["c1", "c2", "c3"]]  # the hit was re-checked, once
    assert hit.evidence[0].citation.chunk_id == "c1"  # in the reranker's order
    assert port.reranks == 1  # the order came from the entry: no second reranker call


def test_a_revoked_chunk_disappears_on_the_hit_path(visible):
    allowed, _ = visible
    port = Port(cache=CandidateCache(InMemoryCandidateCacheStore()), cache_versions=(RV, "policy-1"))
    port.retrieve(request())
    allowed.discard("c1")  # ACL revoked or version archived after the entry was written
    hit = port.retrieve(request())
    assert hit.cache_hit and port.searches == 1
    assert "c1" not in [e.citation.chunk_id for e in hit.evidence]
    assert [r.chunk_id for r in hit.rejected] == ["c1"]
    # the remaining chunks keep the order a fresh rerank of them would give
    fresh = Port()
    allowed_now = [e.citation.chunk_id for e in fresh.retrieve(request()).evidence if e.citation.chunk_id != "c1"]
    assert [e.citation.chunk_id for e in hit.evidence] == allowed_now and port.reranks == 1


def test_an_entry_without_an_order_or_with_an_incomplete_one_is_reranked(visible):
    from datetime import UTC, datetime

    from medops.retrieval.cache import CachedCandidates

    cache = CandidateCache(InMemoryCandidateCacheStore())
    port = Port(cache=cache, cache_versions=(RV, "policy-1"))
    miss = port.retrieve(request())
    inputs = port._cache_inputs(request())
    cache.store(  # an entry written by an older build: candidates only
        inputs,
        CachedCandidates(candidates=miss.candidates, retrieval_version=RV, computed_at=datetime.now(UTC)),
    )
    hit = port.retrieve(request())
    assert hit.cache_hit and port.reranks == 2  # reranked because the entry carries no order
    assert [e.citation.chunk_id for e in hit.evidence] == [e.citation.chunk_id for e in miss.evidence]
    with pytest.raises(ValueError, match="reranked order"):
        CachedCandidates(
            candidates=miss.candidates, retrieval_version=RV, computed_at=datetime.now(UTC), reranked=("zz",)
        )


def test_department_question_versions_and_epoch_each_make_a_different_key(visible):
    cache = CandidateCache(InMemoryCandidateCacheStore())
    port = Port(cache=cache, cache_versions=(RV, "policy-1"))
    port.retrieve(request())
    assert port.retrieve(request(Dept.PV)).cache_hit is False  # another department never reads MA's entry
    assert port.retrieve(request(query="腎功能 劑量 調整")).cache_hit is False
    assert port.searches == 3
    other_policy = Port(cache=cache, cache_versions=(RV, "policy-1+canary:abcd"))
    assert other_policy.retrieve(request()).cache_hit is False  # a canary side has its own entries
    other_retrieval = Port(cache=cache, cache_versions=(RV2, "policy-1"))
    assert other_retrieval.retrieve(request()).cache_hit is False
    assert port.retrieve(request()).cache_hit is True
    cache.invalidate_dept(Dept.MA)  # what the outbox consumer does when a document MA can read is published
    assert port.retrieve(request()).cache_hit is False and port.searches == 4


def test_a_cache_without_versions_is_refused_and_a_failing_store_degrades_to_a_miss(visible):
    from medops.retrieval.cache import CacheStoreError

    with pytest.raises(ValueError, match="retrieval_version, policy_version"):
        Port(cache=CandidateCache(InMemoryCandidateCacheStore()))

    class Broken(InMemoryCandidateCacheStore):
        def get(self, key):
            raise CacheStoreError("ConnectionError")

        def set(self, key, value, ttl_seconds):
            raise CacheStoreError("ConnectionError")

    cache = CandidateCache(Broken())
    port = Port(cache=cache, cache_versions=(RV, "policy-1"))
    a, b = port.retrieve(request()), port.retrieve(request())
    assert port.searches == 2 and not a.cache_hit and not b.cache_hit and cache.degraded >= 2
    assert [e.citation.chunk_id for e in a.evidence] == [e.citation.chunk_id for e in b.evidence]


def test_source_constraint_scopes_search_or_fails_closed_without_revealing_a_document(monkeypatch, visible):
    doc = DocRef("doc-1", "ICH E2F: Development Safety Update Report", "guideline", "ich-e2f-step4-2010")
    monkeypatch.setattr(rp, "load_documents", lambda conn: [doc])
    port = Port(source_constraint=True)
    found = port.retrieve(request(query="ICH E2F 的 DSUR 需要涵蓋哪些內容？"))
    assert found.source_constraint_applied and not found.source_constraint_missing
    assert port.source_doc_ids == ("doc-1",)

    monkeypatch.setattr(rp, "load_documents", lambda conn: [])
    missing_port = Port(source_constraint=True)
    missing = missing_port.retrieve(request(query="ICH E2F 的 DSUR 需要涵蓋哪些內容？"))
    assert missing.source_constraint_applied and missing.source_constraint_missing
    assert not missing.candidates and not missing.evidence and missing_port.searches == 0
    assert "ICH E2F" not in missing.detail and "Development Safety Update Report" not in missing.detail
