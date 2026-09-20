"""M1-19 candidate cache: fingerprints, key composition, TTL/jitter, single flight, degraded stores,
epoch invalidation and the outbox handler, all without a database or Redis."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, date, datetime

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain import CandidateRef, Dept, Entity, SourceRank, UserContext
from medops.ingestion.outbox import OutboxEvent
from medops.retrieval import cache_consumer
from medops.retrieval.cache import (
    CACHE_KEY_VERSION,
    CachedCandidates,
    CacheKeyInputs,
    CacheStoreError,
    CandidateCache,
    InMemoryCandidateCacheStore,
    cache_key,
    context_fingerprint,
    permission_fingerprint,
)

R1 = "a" * 64
R2 = "b" * 64
AS_OF = date(2026, 6, 1)
MA = UserContext(user_id="u-1", dept=Dept.MA, roles=("reader",), acl_scopes=frozenset({"MA:read", "MA:label"}))


def inputs(**overrides) -> CacheKeyInputs:
    base = {
        "query": "  阿司匹林　用法用量 ",
        "user": MA,
        "as_of": AS_OF,
        "retrieval_version": R1,
        "policy_version": "policy-v1",
    }
    base.update(overrides)
    return CacheKeyInputs.build(**base)


def candidates(*ids: str) -> tuple[CandidateRef, ...]:
    return tuple(
        CandidateRef(chunk_id=i, source_ranks=(SourceRank(source="lexical", rank=n),)) for n, i in enumerate(ids, 1)
    )


class FailingStore(InMemoryCandidateCacheStore):
    def __init__(self, *, fail_get=False, fail_set=False, fail_epoch=False):
        super().__init__()
        self.fail_get, self.fail_set, self.fail_epoch = fail_get, fail_set, fail_epoch

    def get(self, key):
        if self.fail_get:
            raise CacheStoreError("ConnectionError")
        return super().get(key)

    def set(self, key, value, ttl_seconds):
        if self.fail_set:
            raise CacheStoreError("TimeoutError")
        super().set(key, value, ttl_seconds)

    def get_epoch(self, dept):
        if self.fail_epoch:
            raise CacheStoreError("ConnectionError")
        return super().get_epoch(dept)


# ------------------------------------------------------------------------------------ fingerprints / keys


def test_permission_fingerprint_depends_on_permissions_only_and_not_on_order_or_identity():
    same = UserContext(
        user_id="someone-else", dept=Dept.MA, roles=("reader",), acl_scopes=frozenset({"MA:label", "MA:read"})
    )
    assert permission_fingerprint(MA) == permission_fingerprint(same)
    assert permission_fingerprint(MA) != permission_fingerprint(MA.model_copy(update={"dept": Dept.PV}))
    assert permission_fingerprint(MA) != permission_fingerprint(
        MA.model_copy(update={"acl_scopes": frozenset({"MA:read"})})
    )
    assert permission_fingerprint(MA) != permission_fingerprint(MA.model_copy(update={"roles": ()}))
    assert "u-1" not in permission_fingerprint(MA)


def test_context_fingerprint_is_order_independent_and_deduplicated():
    a, b = Entity(kind="drug", value="阿司匹林"), Entity(kind="protocol", value="PROT-2024-017")
    assert context_fingerprint([a, b]) == context_fingerprint([b, a]) == context_fingerprint([b, a, a])
    assert context_fingerprint([a]) != context_fingerprint([a, b]) != context_fingerprint()


def test_build_normalizes_the_query_and_refuses_an_empty_one():
    assert inputs().normalized_query == "阿司匹林用法用量"  # norm-v1 drops whitespace between CJK characters
    with pytest.raises(BusinessError) as exc:
        inputs(query="  　 ")
    assert exc.value.code is ErrorCode.invalid_request


@pytest.mark.parametrize(
    "change",
    [
        {"query": "阿司匹林 禁忌"},
        {"user": MA.model_copy(update={"dept": Dept.PV})},
        {"user": MA.model_copy(update={"acl_scopes": frozenset({"MA:read"})})},
        {"entities": (Entity(kind="drug", value="阿司匹林"),)},
        {"as_of": date(2026, 6, 2)},
        {"allow_historical": True},
        {"retrieval_version": R2},
        {"policy_version": "policy-v2"},
    ],
)
def test_every_key_member_changes_the_key(change):
    base = cache_key(inputs(), epoch=0)
    assert cache_key(inputs(**change), epoch=0) != base
    assert cache_key(inputs(), epoch=0) == base  # and it is stable otherwise


def test_key_layout_carries_version_department_and_epoch():
    key = cache_key(inputs(), epoch=7)
    prefix, dept, epoch, digest = key.split(":")
    assert (prefix, dept, epoch) == (CACHE_KEY_VERSION, "MA", "7") and len(digest) == 64
    assert cache_key(inputs(), epoch=8) != key
    for bad in (-1, True, 1.0):
        with pytest.raises(ValueError):
            cache_key(inputs(), epoch=bad)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------ in-memory store


def test_in_memory_store_expires_by_ttl_and_keeps_epochs_per_department():
    now = [1000.0]
    store = InMemoryCandidateCacheStore(clock=lambda: now[0])
    store.set("k", "v", 10)
    now[0] = 1009.9
    assert store.get("k") == "v" and len(store) == 1
    now[0] = 1010.0
    assert store.get("k") is None and len(store) == 0
    with pytest.raises(ValueError):
        store.set("k", "v", 0)
    assert store.get_epoch("MA") == 0
    assert store.bump_epoch("MA") == 1 and store.bump_epoch("MA") == 2
    assert store.get_epoch("PV") == 0


# ------------------------------------------------------------------------------------ facade


def test_miss_computes_and_stores_then_hits_with_the_same_value():
    cache = CandidateCache(InMemoryCandidateCacheStore())
    calls = []

    def compute():
        calls.append(1)
        return candidates("c1", "c2")

    value, hit = cache.get_or_compute(inputs(), compute)
    assert hit is False and value.candidates == candidates("c1", "c2") and value.retrieval_version == R1
    again, hit = cache.get_or_compute(inputs(), compute)
    assert hit is True and again == value and len(calls) == 1
    assert cache.lookup(inputs(retrieval_version=R2)) is None


def test_concurrent_misses_for_one_key_compute_once():
    cache = CandidateCache(InMemoryCandidateCacheStore())
    started = threading.Barrier(4)
    calls = []
    results = []

    def compute():
        calls.append(1)
        return candidates("c1")

    def worker():
        started.wait()
        results.append(cache.get_or_compute(inputs(), compute))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1 and len(results) == 4 and {r[0] for r in results} == {results[0][0]}
    assert sorted(r[1] for r in results) == [False, True, True, True]


def test_ttl_jitter_stays_within_bounds_and_never_below_one():
    cache = CandidateCache(InMemoryCandidateCacheStore(), ttl_seconds=300, jitter=0.1)
    draws = {cache.ttl_with_jitter() for _ in range(500)}
    assert min(draws) >= 270 and max(draws) <= 330 and len(draws) > 1
    assert CandidateCache(InMemoryCandidateCacheStore(), ttl_seconds=1, jitter=0.9).ttl_with_jitter() >= 1
    with pytest.raises(ValueError):
        CandidateCache(InMemoryCandidateCacheStore(), ttl_seconds=0)
    with pytest.raises(ValueError):
        CandidateCache(InMemoryCandidateCacheStore(), jitter=1.0)


def test_invalidate_dept_makes_that_departments_entries_miss_and_leaves_others():
    store = InMemoryCandidateCacheStore()
    cache = CandidateCache(store)
    pv = UserContext(user_id="u-2", dept=Dept.PV)
    cache.get_or_compute(inputs(), lambda: candidates("ma1"))
    cache.get_or_compute(inputs(user=pv), lambda: candidates("pv1"))
    assert cache.invalidate_dept(Dept.MA) == 1
    _, hit_ma = cache.get_or_compute(inputs(), lambda: candidates("ma2"))
    _, hit_pv = cache.get_or_compute(inputs(user=pv), lambda: candidates("pv2"))
    assert hit_ma is False and hit_pv is True
    assert cache.lookup(inputs()).candidates == candidates("ma2")
    with pytest.raises(ValueError):
        cache.invalidate_dept("HR")


@pytest.mark.parametrize("failure", ["fail_get", "fail_set", "fail_epoch"])
def test_a_failing_store_degrades_to_a_miss_and_never_raises(failure):
    store = FailingStore(**{failure: True})
    cache = CandidateCache(store)
    calls = []

    def compute():
        calls.append(1)
        return candidates("c1")

    for _ in range(2):
        value, hit = cache.get_or_compute(inputs(), compute)
        assert hit is False and value.candidates == candidates("c1")
    assert len(calls) == 2 and cache.degraded >= 2


def test_corrupted_or_foreign_values_are_misses_and_wrong_version_is_refused_on_store():
    store = InMemoryCandidateCacheStore()
    cache = CandidateCache(store)
    store.set(cache.key_for(inputs()), "{not json", 60)
    assert cache.lookup(inputs()) is None
    store.set(
        cache.key_for(inputs()),
        '{"candidates": [], "retrieval_version": "' + R2 + '", "computed_at": "2026-06-01T00:00:00Z"}',
        60,
    )
    assert cache.lookup(inputs()) is None
    value = CachedCandidates(candidates=candidates("c1"), retrieval_version=R2, computed_at=datetime.now(UTC))
    with pytest.raises(InfrastructureError):
        cache.store(inputs(), value)


def test_cached_candidates_model_rules():
    with pytest.raises(ValueError, match="unique"):
        CachedCandidates(
            candidates=candidates("c1") + candidates("c1"), retrieval_version=R1, computed_at=datetime.now(UTC)
        )
    with pytest.raises(ValueError, match="timezone"):
        CachedCandidates(candidates=(), retrieval_version=R1, computed_at=datetime(2026, 6, 1))
    with pytest.raises(ValueError):
        CachedCandidates(
            candidates=candidates(*[f"c{i}" for i in range(21)]), retrieval_version=R1, computed_at=datetime.now(UTC)
        )


# ------------------------------------------------------------------------------------ consumer


def event(event_type="document_activated", **payload) -> OutboxEvent:
    return OutboxEvent(1, event_type, uuid.uuid4(), uuid.uuid4(), payload, "reviewer-01", datetime.now(UTC))


def test_consumer_bumps_the_epoch_of_every_reading_department_only():
    store = InMemoryCandidateCacheStore()
    handle = cache_consumer.handler_for(CandidateCache(store))
    handle(None, event(acl_depts=["PV", "MA", "MA"], owner_dept="MA"))  # type: ignore[arg-type]
    assert (store.get_epoch("MA"), store.get_epoch("PV"), store.get_epoch("CO")) == (1, 1, 0)
    handle(None, event("document_archived", acl_depts=[], owner_dept="CO"))  # type: ignore[arg-type]
    assert store.get_epoch("CO") == 1
    assert cache_consumer.departments_of(event(acl_depts=["CO", "MA"])) == (Dept.CO, Dept.MA)


def test_consumer_refuses_malformed_events_instead_of_skipping_them():
    handle = cache_consumer.handler_for(CandidateCache(InMemoryCandidateCacheStore()))
    with pytest.raises(ValueError, match="no department"):
        handle(None, event())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        handle(None, event(acl_depts=["HR"]))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown outbox event type"):
        handle(None, event("document_deleted", acl_depts=["MA"]))  # type: ignore[arg-type]
