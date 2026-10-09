"""Redis-backed `CandidateCacheStore` (M1-19; baseline 5.12: Redis is the shared cache).

Fixed connect/read timeouts (INV-HAR-04). Every Redis failure surfaces as `CacheStoreError` carrying only
the exception type name, so neither the DSN nor server addresses reach logs through the cache. Keys are
namespaced so several deployments or test runs can share one instance without touching each other.
"""

from __future__ import annotations

from typing import cast

import redis

from medops.core.config import Settings
from medops.retrieval.cache import CacheStoreError

DEFAULT_NAMESPACE = "medops:rcache:"
CONNECT_TIMEOUT_SECONDS = 1.0
READ_TIMEOUT_SECONDS = 1.0


class RedisCandidateCacheStore:
    def __init__(self, client: redis.Redis, *, namespace: str = DEFAULT_NAMESPACE) -> None:
        if not namespace:
            raise ValueError("namespace must not be empty")
        self._client = client
        self._ns = namespace

    @classmethod
    def from_settings(cls, settings: Settings, *, namespace: str | None = None) -> RedisCandidateCacheStore:
        # Explicit overrides support isolated tests; production callers take the deployment-specific prefix.
        namespace = namespace or settings.retrieval_cache_namespace
        client = redis.Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=CONNECT_TIMEOUT_SECONDS,
            socket_timeout=READ_TIMEOUT_SECONDS,
            decode_responses=True,
        )
        return cls(client, namespace=namespace)

    @property
    def namespace(self) -> str:
        return self._ns

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError as exc:
            raise CacheStoreError(type(exc).__name__) from None

    def get(self, key: str) -> str | None:
        try:
            value = cast("str | bytes | None", self._client.get(self._ns + key))  # sync client: never awaitable
        except redis.RedisError as exc:
            raise CacheStoreError(type(exc).__name__) from None
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        try:
            self._client.set(self._ns + key, value, ex=ttl_seconds)
        except redis.RedisError as exc:
            raise CacheStoreError(type(exc).__name__) from None

    def get_epoch(self, dept: str) -> int:
        try:
            value = cast("str | bytes | None", self._client.get(self._ns + "epoch:" + dept))
            return int(value) if value else 0
        except (redis.RedisError, TypeError, ValueError) as exc:
            raise CacheStoreError(type(exc).__name__) from None

    def bump_epoch(self, dept: str) -> int:
        try:
            return int(cast(int, self._client.incr(self._ns + "epoch:" + dept)))
        except redis.RedisError as exc:
            raise CacheStoreError(type(exc).__name__) from None
