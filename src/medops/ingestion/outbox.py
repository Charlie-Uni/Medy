"""Transactional outbox (M1-11): emit inside the producing transaction, consume at least once, apply once per
consumer.

`emit()` is called by the publish/activate/withdraw transaction on the SAME connection, so the event commits
or rolls back together with the status change. `claim()` takes unacked events for one consumer with
`FOR UPDATE SKIP LOCKED` (several workers may run concurrently); `run()` applies a handler and records the
ack in the same transaction as the handler's own writes, so a crash between "applied" and "acked" cannot
happen, and a redelivered event is skipped because its ack already exists. `published_at` is bookkeeping
for operators (set when every registered consumer has acked); correctness never depends on it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

EVENT_TYPES = ("document_activated", "document_archived", "document_withdrawn", "document_acl_changed")


@dataclass(frozen=True)
class OutboxEvent:
    event_id: int
    event_type: str
    aggregate_id: uuid.UUID
    family_id: uuid.UUID
    payload: dict[str, Any]
    created_by: str
    created_at: datetime


def emit(
    conn: psycopg.Connection[Any],
    event_type: str,
    *,
    aggregate_id: uuid.UUID,
    family_id: uuid.UUID,
    payload: Mapping[str, Any],
    actor: str,
) -> int:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown outbox event type {event_type}")
    row = conn.execute(
        "insert into outbox_events (event_type, aggregate_id, family_id, payload, created_by) "
        "values (%s, %s, %s, %s::jsonb, %s) returning event_id",
        (event_type, aggregate_id, family_id, json.dumps(dict(payload), ensure_ascii=False, sort_keys=True), actor),
    ).fetchone()
    assert row is not None
    return int(row[0])


def claim(conn: psycopg.Connection[Any], consumer: str, *, limit: int = 50) -> list[OutboxEvent]:
    """Events not yet acked by `consumer`, oldest first, locked for this transaction; concurrent workers skip
    each other's rows."""
    rows = conn.execute(
        """select e.event_id, e.event_type, e.aggregate_id, e.family_id, e.payload, e.created_by, e.created_at
           from outbox_events e
           where not exists (select 1 from outbox_consumer_acks a where a.consumer = %s and a.event_id = e.event_id)
           order by e.event_id
           limit %s
           for update of e skip locked""",
        (consumer, limit),
    ).fetchall()
    return [OutboxEvent(int(r[0]), str(r[1]), r[2], r[3], dict(r[4]), str(r[5]), r[6]) for r in rows]


def ack(conn: psycopg.Connection[Any], consumer: str, event_id: int) -> None:
    conn.execute("insert into outbox_consumer_acks (consumer, event_id) values (%s, %s)", (consumer, event_id))


def mark_published_when_complete(conn: psycopg.Connection[Any], consumers: Sequence[str]) -> int:
    """Operator bookkeeping: set published_at on events every listed consumer has acked."""
    cur = conn.execute(
        """update outbox_events e set published_at = now()
           where e.published_at is null
             and not exists (
                 select 1 from unnest(%s::text[]) c(name)
                 where not exists (select 1 from outbox_consumer_acks a where a.consumer = c.name and a.event_id = e.event_id))""",
        (list(consumers),),
    )
    return cur.rowcount


Handler = Callable[[psycopg.Connection[Any], OutboxEvent], None]


def run(conn: psycopg.Connection[Any], consumer: str, handler: Handler, *, limit: int = 50) -> list[int]:
    """Apply `handler` to each claimed event and ack it in the same transaction. Returns the acked ids.
    A handler exception rolls back that event's work and its ack; the event is redelivered later
    (attempts/last_error are recorded outside the failed transaction by the caller if desired)."""
    done: list[int] = []
    with conn.transaction():
        for event in claim(conn, consumer, limit=limit):
            with conn.transaction():  # savepoint per event: one failure does not lose the others
                handler(conn, event)
                ack(conn, consumer, event.event_id)
                done.append(event.event_id)
    return done


def record_failure(conn: psycopg.Connection[Any], event_id: int, error: str) -> None:
    conn.execute(
        "update outbox_events set attempts = attempts + 1, last_error = left(%s, 500) where event_id = %s",
        (error, event_id),
    )
