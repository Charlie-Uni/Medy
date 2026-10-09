"""Bounded retrieval outbox maintenance with per-event rollback and durable sanitized failures.

Handlers reconcile the current document state, not an old event's status. Archived indexes are retained for
explicit historical queries. Permission/status checks in retrieval remain authoritative before consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from medops.ingestion import outbox
from medops.retrieval.lexical.pg_lexical_common import read_built_versions
from medops.retrieval.production import (
    PRODUCTION_LEXICAL_INDEX_NAME,
    production_document_lexical_gaps,
    production_index_target,
    production_lexical_versions,
)
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.embedding import EMBEDDING_FIELDS, EMBEDDING_VERSION, EmbeddingProvider

CONSUMERS = ("lexical-index", "vector-index", "retrieval-cache")


@dataclass(frozen=True)
class BatchResult:
    acknowledged: tuple[int, ...]
    failed: tuple[int, ...]
    dead_lettered: tuple[int, ...] = ()


def consume_batch(
    conn: psycopg.Connection[Any],
    consumer: str,
    handler: outbox.Handler,
    *,
    limit: int = 10,
    max_attempts: int = 10,
    backoff_base_s: int = 5,
    backoff_max_s: int = 3600,
) -> BatchResult:
    """Caller commits. Failed events keep no partial DB writes/ACK; other claimed events can complete.

    External cache invalidation may repeat on redelivery; epoch bumps are idempotent in effect. A poison event
    becomes a per-consumer dead letter after the retry limit. It never receives an ACK and needs explicit replay.
    """
    if consumer not in CONSUMERS or not 1 <= limit <= 100:
        raise ValueError("known consumer and batch size 1..100 required")
    done, failed, dead = [], [], []
    with conn.transaction():
        for event in outbox.claim(conn, consumer, limit=limit):
            try:
                with conn.transaction():
                    handler(conn, event)
                    outbox.ack(conn, consumer, event.event_id)
            except Exception as exc:  # noqa: BLE001 - rollback this event; never persist exception text/payload
                if outbox.record_failure(
                    conn,
                    consumer,
                    event.event_id,
                    f"{consumer}:{type(exc).__name__}",
                    max_attempts=max_attempts,
                    backoff_base_s=backoff_base_s,
                    backoff_max_s=backoff_max_s,
                ):
                    dead.append(event.event_id)
                failed.append(event.event_id)
            else:
                done.append(event.event_id)
    return BatchResult(tuple(done), tuple(failed), tuple(dead))


def _document_status(conn: psycopg.Connection[Any], event: outbox.OutboxEvent) -> str:
    if event.event_type not in outbox.EVENT_TYPES:
        raise ValueError("unknown document event")
    # Keep the checked state stable until the event's index writes and ACK commit.
    row = conn.execute("select status::text from documents where doc_id=%s for share", (event.aggregate_id,)).fetchone()
    if not row or row[0] not in ("draft", "active", "archived", "withdrawn"):
        raise ValueError("outbox document has no recognized state")
    if row[0] in ("active", "archived"):
        chunks = conn.execute("select exists(select 1 from chunks where doc_id=%s)", (event.aggregate_id,)).fetchone()
        if not chunks or not chunks[0]:
            raise ValueError("published document has no chunks")
    return str(row[0])


def lexical_handler() -> outbox.Handler:
    target = production_index_target()

    def handle(conn: psycopg.Connection[Any], event: outbox.OutboxEvent) -> None:
        status = _document_status(conn, event)
        if read_built_versions(conn, PRODUCTION_LEXICAL_INDEX_NAME) != production_lexical_versions():
            raise ValueError("production lexical metadata differs; explicit rebuild required")
        if status in ("draft", "withdrawn"):
            target.remove(conn, event.aggregate_id)
            return
        # The departmental target first removes stale ACL copies, then recreates
        # exactly the current department assignments from authoritative chunks.
        target.add(conn, event.aggregate_id)
        if production_document_lexical_gaps(conn, event.aggregate_id):
            raise ValueError("published document contains ACL/chunk assignments without lexical tokens")

    return handle


def vector_handler(provider: EmbeddingProvider) -> outbox.Handler:
    if provider.spec.embedding_version != EMBEDDING_VERSION:
        raise ValueError("maintenance requires the production embedding version")

    def handle(conn: psycopg.Connection[Any], event: outbox.OutboxEvent) -> None:
        status = _document_status(conn, event)
        # Missing/mismatched metadata requires an explicit full bootstrap; do not invent an index version.
        built = pg_vector.read_meta(conn, provider.spec.embedding_version)
        if built.model_dump(include=EMBEDDING_FIELDS) != provider.spec.model_dump(include=EMBEDDING_FIELDS):
            raise ValueError("production vector metadata differs; explicit rebuild required")
        if status in ("draft", "withdrawn"):
            conn.execute(
                "delete from chunk_embeddings e using chunks c where e.chunk_id=c.chunk_id "
                "and c.doc_id=%s and e.embedding_version=%s",
                (event.aggregate_id, provider.spec.embedding_version),
            )
        # Empty ids on withdrawal only refresh the aggregate metadata count; no text is embedded.
        pg_vector.build_index(
            conn,
            provider,
            built_by="outbox-vector-index",
            doc_ids=[] if status in ("draft", "withdrawn") else [event.aggregate_id],
        )

    return handle
