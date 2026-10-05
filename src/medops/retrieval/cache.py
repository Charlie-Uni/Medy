"""Retrieval candidate cache (M1-19; baseline 5.2, 3.6; threat model boundary B5).

What is cached is the fused, not yet re-checked candidate list of one retrieval (`CandidateRef`s in rank
order), never Evidence. Every hit still goes through `recheck_candidates` under the caller's identity in
the request transaction, so a revoked ACL, an archived version or a corrupted chunk is filtered on the hit
path exactly as on the miss path: the cache saves the retrieval work, it cannot bypass authorization or
the fact plane. `fetch_evidence` is the only function here that turns a cached entry into Evidence, and
it always re-checks.

Key: `rcache-v1:<dept>:<dept epoch>:<sha256(canonical_json(CacheKeyInputs))>`. The inputs are the
normalized query, the caller's permission fingerprint (department, roles and scopes; never the user id),
the session-context fingerprint, the resolved `as_of` date, the historical flag, the composite
`retrieval_version` (baseline 3.6: only the composite may enter a cache key) and the `policy_version`.
Any change in any of them is a different key.

Invalidation is a per-department epoch. Publishing, archiving or withdrawing a document bumps the epoch of
every department that may read it (`medops.retrieval.cache_consumer`, fed by the transactional outbox), so
every entry of those departments misses from then on while other departments keep theirs. Superseded
entries expire by TTL, with jitter so they do not all expire in the same second. A failing store degrades
to a miss (counted and logged by exception type), never to an error and never to a stale hit past the epoch.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Protocol

from pydantic import Field, ValidationError, model_validator

from medops.core.canonical import canonical_hash
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept, DomainModel, NonEmptyStr, Sha256
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.state import MAX_CANDIDATES, CandidateRef
from medops.retrieval.lexical.normalization import normalize_text
from medops.retrieval.recheck import RecheckResult, recheck_candidates

log = logging.getLogger(__name__)

CACHE_KEY_VERSION = "rcache-v1"
DEFAULT_TTL_SECONDS = 300
DEFAULT_TTL_JITTER = 0.1  # +-10 % of the TTL


class CacheStoreError(Exception):
    """A store operation failed (connection, timeout, protocol). The message names the failure type only."""


# ------------------------------------------------------------------------------------ fingerprints


def permission_fingerprint(user: UserContext) -> str:
    """What the caller may see: department, roles and scopes, order-independent. The user id is not part
    of it: two users with identical permissions share entries, and no identity enters a key (INV-OBS-02)."""
    return canonical_hash({"dept": user.dept.value, "roles": sorted(user.roles), "acl_scopes": sorted(user.acl_scopes)})


def context_fingerprint(entities: Sequence[Entity] = ()) -> str:
    """The trusted session entities that shape query rewriting, order-independent and de-duplicated."""
    items = sorted({(e.kind, e.value) for e in entities})
    return canonical_hash([{"kind": kind, "value": value} for kind, value in items])


class CacheKeyInputs(DomainModel):
    normalized_query: NonEmptyStr
    dept: Dept
    permission_fingerprint: Sha256
    context_fingerprint: Sha256
    as_of: date
    allow_historical: bool
    retrieval_version: Sha256
    policy_version: NonEmptyStr

    @classmethod
    def build(
        cls,
        *,
        query: str,
        user: UserContext,
        as_of: date,
        retrieval_version: str,
        policy_version: str,
        entities: Sequence[Entity] = (),
        allow_historical: bool = False,
    ) -> CacheKeyInputs:
        normalized = normalize_text(query)
        if not normalized:
            raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
        return cls(
            normalized_query=normalized,
            dept=user.dept,
            permission_fingerprint=permission_fingerprint(user),
            context_fingerprint=context_fingerprint(entities),
            as_of=as_of,
            allow_historical=allow_historical,
            retrieval_version=retrieval_version,
            policy_version=policy_version,
        )

    def digest(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def cache_key(inputs: CacheKeyInputs, *, epoch: int) -> str:
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise ValueError("epoch must be a non-negative integer")
    return f"{CACHE_KEY_VERSION}:{inputs.dept.value}:{epoch}:{inputs.digest()}"


# ------------------------------------------------------------------------------------ values


class CachedCandidates(DomainModel):
    """A retrieval's fused candidates. They are not facts: `fetch_evidence` re-checks them on every use."""

    candidates: tuple[CandidateRef, ...] = Field(max_length=MAX_CANDIDATES)
    retrieval_version: Sha256
    computed_at: datetime
    # The reranker's order over the candidates that passed the re-check when the entry was written (record 121).
    # Still not facts: on a hit it only orders evidence that has just been re-checked, and a chunk whose text
    # changed fails the content-hash check before its old position could matter. Empty = rerank on every hit.
    reranked: tuple[NonEmptyStr, ...] = Field(default=(), max_length=MAX_CANDIDATES)

    @model_validator(mode="after")
    def _rules(self) -> CachedCandidates:
        ids = [c.chunk_id for c in self.candidates]
        if len(set(ids)) != len(ids):
            raise ValueError("cached candidates must have unique chunk ids")
        if len(set(self.reranked)) != len(self.reranked) or not set(self.reranked) <= set(ids):
            raise ValueError("the reranked order must be unique ids drawn from the candidates")
        if self.computed_at.tzinfo is None:
            raise ValueError("computed_at must be timezone-aware")
        return self


# ------------------------------------------------------------------------------------ stores


class CandidateCacheStore(Protocol):
    """String in, string out; TTL in seconds; a per-department epoch counter. Implementations raise
    `CacheStoreError` for every operational failure and nothing else."""

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    def get_epoch(self, dept: str) -> int: ...

    def bump_epoch(self, dept: str) -> int: ...


class InMemoryCandidateCacheStore:
    """Process-local store for development and tests (and the reference for the store semantics). Entries
    of one process are invisible to another; production uses the Redis store behind the same protocol."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[float, str]] = {}
        self._epochs: dict[str, int] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= self._clock():
                del self._entries[key]
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        with self._lock:
            self._entries[key] = (self._clock() + ttl_seconds, value)

    def get_epoch(self, dept: str) -> int:
        with self._lock:
            return self._epochs.get(dept, 0)

    def bump_epoch(self, dept: str) -> int:
        with self._lock:
            self._epochs[dept] = self._epochs.get(dept, 0) + 1
            return self._epochs[dept]

    def __len__(self) -> int:
        with self._lock:
            now = self._clock()
            return sum(1 for expires_at, _ in self._entries.values() if expires_at > now)


# ------------------------------------------------------------------------------------ facade


class CandidateCache:
    def __init__(
        self,
        store: CandidateCacheStore,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        jitter: float = DEFAULT_TTL_JITTER,
        rng: random.Random | None = None,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        if not 0 <= jitter < 1:
            raise ValueError("jitter must be within [0, 1)")
        self._store = store
        self._ttl = ttl_seconds
        self._jitter = jitter
        self._rng = rng or random.Random()
        self._flights: dict[str, tuple[threading.Lock, int]] = {}
        self._flights_guard = threading.Lock()
        self.degraded = 0  # store failures turned into misses (for metrics: baseline 5.10 "缓存命中")

    # -- key / ttl

    def key_for(self, inputs: CacheKeyInputs) -> str:
        return cache_key(inputs, epoch=self._store.get_epoch(inputs.dept.value))

    def ttl_with_jitter(self) -> int:
        spread = self._ttl * self._jitter
        return max(1, round(self._ttl + self._rng.uniform(-spread, spread)))

    # -- operations

    def lookup(self, inputs: CacheKeyInputs) -> CachedCandidates | None:
        try:
            raw = self._store.get(self.key_for(inputs))
        except CacheStoreError as exc:
            self._degrade(exc)
            return None
        if raw is None:
            return None
        try:
            value = CachedCandidates.model_validate_json(raw)
        except ValidationError:
            return None  # a foreign or corrupted value is a miss, never an error
        if value.retrieval_version != inputs.retrieval_version:
            return None  # cannot happen through `store`; defensive against a hand-written entry
        return value

    def store(self, inputs: CacheKeyInputs, value: CachedCandidates) -> bool:
        if value.retrieval_version != inputs.retrieval_version:
            raise InfrastructureError(
                ErrorCode.internal_error,
                detail="refusing to cache candidates computed under another retrieval_version",
                retryable=False,
            )
        try:
            self._store.set(self.key_for(inputs), value.model_dump_json(), self.ttl_with_jitter())
        except CacheStoreError as exc:
            self._degrade(exc)
            return False
        return True

    def get_or_compute(
        self, inputs: CacheKeyInputs, compute: Callable[[], Sequence[CandidateRef]]
    ) -> tuple[CachedCandidates, bool]:
        """Cache-aside with single flight per key inside this process: concurrent misses for the same key
        compute once. Returns `(value, hit)`."""
        found = self.lookup(inputs)
        if found is not None:
            return found, True
        with self._flight(inputs.digest()):
            found = self.lookup(inputs)
            if found is not None:
                return found, True
            value = CachedCandidates(
                candidates=tuple(compute()),
                retrieval_version=inputs.retrieval_version,
                computed_at=datetime.now(UTC),
            )
            self.store(inputs, value)
            return value, False

    def invalidate_dept(self, dept: Dept | str) -> int:
        """Every entry of `dept` misses from now on (its epoch changes); other departments are untouched."""
        return self._store.bump_epoch(dept.value if isinstance(dept, Dept) else str(Dept(dept)))

    # -- internals

    def _degrade(self, exc: Exception) -> None:
        self.degraded += 1
        log.warning("retrieval cache degraded to a miss: %s", type(exc).__name__)

    @contextmanager
    def _flight(self, digest: str) -> Iterator[None]:
        with self._flights_guard:
            lock, waiters = self._flights.get(digest, (threading.Lock(), 0))
            self._flights[digest] = (lock, waiters + 1)
        try:
            with lock:
                yield
        finally:
            with self._flights_guard:
                lock, waiters = self._flights[digest]
                if waiters <= 1:
                    del self._flights[digest]
                else:
                    self._flights[digest] = (lock, waiters - 1)


def fetch_evidence(
    conn: object,
    cache: CandidateCache,
    inputs: CacheKeyInputs,
    compute: Callable[[], Sequence[CandidateRef]],
) -> tuple[RecheckResult, bool]:
    """The only route from the cache to Evidence: take (or compute) the candidates, then re-check every one
    of them in the fact plane under the caller's identity (`conn` is the identity-bound request transaction).
    Returns `(recheck result, cache hit)`."""
    cached, hit = cache.get_or_compute(inputs, compute)
    return recheck_cached(conn, cached, inputs), hit


def recheck_cached(conn: object, cached: CachedCandidates, inputs: CacheKeyInputs) -> RecheckResult:
    """Cached candidates -> Evidence: every chunk is re-read in the fact plane under the caller's identity, so a
    revoked ACL, an archived version or a corrupted chunk is filtered on a hit exactly as on a miss. The production
    retrieval port uses this for its hit path (record 121); nothing else may turn a cache entry into evidence."""
    return recheck_candidates(
        conn,  # type: ignore[arg-type]
        [c.chunk_id for c in cached.candidates],
        as_of=inputs.as_of,
        allow_historical=inputs.allow_historical,
    )
