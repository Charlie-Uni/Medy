"""Runtime-only retrieval adapters shared by the API and MCP entry points."""

from __future__ import annotations

from typing import Any

from medops.core.config import Settings


def candidate_cache_from_settings(settings: Settings) -> Any:
    """Build the configured candidate cache; every hit is still fact-plane rechecked by ProductionRetrieval."""
    if settings.retrieval_cache == "off":
        return None
    from medops.retrieval.cache import CandidateCache, InMemoryCandidateCacheStore

    if settings.retrieval_cache == "memory":
        return CandidateCache(InMemoryCandidateCacheStore(), ttl_seconds=settings.retrieval_cache_ttl_seconds)
    from medops.infrastructure.cache import RedisCandidateCacheStore

    return CandidateCache(
        RedisCandidateCacheStore.from_settings(settings), ttl_seconds=settings.retrieval_cache_ttl_seconds
    )
