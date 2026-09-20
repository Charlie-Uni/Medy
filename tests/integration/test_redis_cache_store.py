"""M1-19 Redis store against a real Redis (skipped without one): TTL, epochs, namespace isolation, and a
failing server degrading the cache to misses instead of errors. Keys live under a random namespace and are
removed afterwards; nothing else on the instance is touched."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import date

import pytest
import redis

from medops.core.config import Settings
from medops.domain import CandidateRef, Dept, SourceRank, UserContext
from medops.infrastructure.cache import RedisCandidateCacheStore
from medops.retrieval.cache import CacheKeyInputs, CacheStoreError, CandidateCache

R1 = "c" * 64
MA = UserContext(user_id="u", dept=Dept.MA)


@pytest.fixture
def namespace() -> str:
    return f"medops-test:{secrets.token_hex(4)}:"


@pytest.fixture
def client(redis_url: str) -> Iterator[redis.Redis]:
    c = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
    yield c
    c.close()


@pytest.fixture
def store(client: redis.Redis, namespace: str) -> Iterator[RedisCandidateCacheStore]:
    s = RedisCandidateCacheStore(client, namespace=namespace)
    yield s
    keys = list(client.scan_iter(match=namespace + "*"))
    if keys:
        client.delete(*keys)


def _inputs(query="阿司匹林"):
    return CacheKeyInputs.build(query=query, user=MA, as_of=date(2026, 6, 1), retrieval_version=R1, policy_version="p1")


def test_set_get_with_ttl_and_epochs(store, client, namespace):
    assert store.ping() is True
    assert store.get("k") is None
    store.set("k", "v", 30)
    assert store.get("k") == "v"
    assert 0 < client.ttl(namespace + "k") <= 30
    assert store.get_epoch("MA") == 0
    assert store.bump_epoch("MA") == 1 and store.bump_epoch("MA") == 2 and store.get_epoch("MA") == 2
    assert store.get_epoch("PV") == 0
    with pytest.raises(ValueError):
        store.set("k", "v", 0)


def test_namespaces_are_isolated(client, namespace):
    one = RedisCandidateCacheStore(client, namespace=namespace + "a:")
    two = RedisCandidateCacheStore(client, namespace=namespace + "b:")
    try:
        one.set("k", "one", 30)
        one.bump_epoch("MA")
        assert two.get("k") is None and two.get_epoch("MA") == 0
    finally:
        keys = list(client.scan_iter(match=namespace + "*"))
        if keys:
            client.delete(*keys)


def test_cache_round_trip_and_epoch_invalidation_through_redis(store):
    cache = CandidateCache(store, ttl_seconds=30)
    cands = (CandidateRef(chunk_id="c1", source_ranks=(SourceRank(source="lexical", rank=1),)),)
    value, hit = cache.get_or_compute(_inputs(), lambda: cands)
    assert hit is False
    again, hit = cache.get_or_compute(_inputs(), lambda: ())
    assert hit is True and again == value
    cache.invalidate_dept(Dept.MA)
    _, hit = cache.get_or_compute(_inputs(), lambda: ())
    assert hit is False


def test_an_unreachable_server_degrades_to_misses():
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2, socket_timeout=0.2)
    store = RedisCandidateCacheStore(dead, namespace="medops-test:dead:")
    with pytest.raises(CacheStoreError) as exc:
        store.get("k")
    assert "127.0.0.1" not in str(exc.value)
    cache = CandidateCache(store)
    value, hit = cache.get_or_compute(_inputs(), lambda: ())
    assert hit is False and value.candidates == () and cache.degraded >= 1


def test_from_settings_builds_a_working_store_without_exposing_the_dsn(redis_url, namespace, capsys):
    settings = Settings(_env_file=None, database_url="postgresql://u:p@localhost:5432/db", redis_url=redis_url)
    store = RedisCandidateCacheStore.from_settings(settings, namespace=namespace)
    assert store.ping() is True and store.namespace == namespace
    assert redis_url not in repr(store) and redis_url not in capsys.readouterr().out
