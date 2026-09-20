"""Outbox consumer that invalidates the retrieval candidate cache when a document changes status (M1-19).

For `document_activated`, `document_archived` and `document_withdrawn` the epoch of every department that
may read the document (`payload.acl_depts`, else the owner department) is bumped, so those departments'
cached candidate lists miss from then on and the next retrieval sees the new version. Other departments'
entries are untouched.

Bumping is idempotent in effect (a second bump only causes more misses), so the at-least-once delivery of
the outbox is safe: if the acknowledging transaction fails after the bump, the redelivered event bumps
again. A store failure raises, the event stays unacked and is redelivered; nothing is silently skipped.

Correctness of authorization never waits for this consumer: the hit path re-checks every candidate in the
fact plane (`medops.retrieval.cache.fetch_evidence`), so a revoked ACL or an archived version is filtered
before any evidence is built, with or without invalidation. The consumer restores freshness.
"""

from __future__ import annotations

from typing import Any

import psycopg

from medops.domain.common import Dept
from medops.ingestion import outbox
from medops.retrieval.cache import CandidateCache

CONSUMER = "retrieval-cache"


def departments_of(event: outbox.OutboxEvent) -> tuple[Dept, ...]:
    """The departments whose cache the event invalidates: the read ACL captured in the payload at publish
    time, else the owner department. An unknown department is a producer defect and is not skipped."""
    raw = event.payload.get("acl_depts") or []
    owner = event.payload.get("owner_dept")
    names = list(raw) if isinstance(raw, list) else []
    if not names and owner:
        names = [owner]
    if not names:
        raise ValueError("outbox payload names no department (acl_depts / owner_dept)")
    return tuple(sorted({Dept(name) for name in names}, key=lambda d: d.value))


def handler_for(cache: CandidateCache) -> outbox.Handler:
    def handle(conn: psycopg.Connection[Any], event: outbox.OutboxEvent) -> None:
        if event.event_type not in outbox.EVENT_TYPES:
            raise ValueError(f"unknown outbox event type {event.event_type}")
        for dept in departments_of(event):
            cache.invalidate_dept(dept)

    return handle


def consume(conn: psycopg.Connection[Any], cache: CandidateCache, *, limit: int = 50) -> list[int]:
    """Apply pending status events to the cache epochs; returns acked event ids."""
    return outbox.run(conn, CONSUMER, handler_for(cache), limit=limit)
