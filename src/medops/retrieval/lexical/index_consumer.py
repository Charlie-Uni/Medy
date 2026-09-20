"""Outbox consumer that keeps the DEC-001 candidate index tables in step with document status (M1-11).

`document_activated` adds the document's chunks to every registered index table; `document_archived`
and `document_withdrawn` remove them. Each index maintains itself idempotently (insert ... on conflict do
nothing / delete), and the outbox ack ledger prevents a second application, so redelivery is harmless.

Correctness does not wait for this consumer: every candidate filters `documents.status = 'active'` and the
effective window inside the search statement, so an archived version stops being evidence the moment the
publish transaction commits, even while its rows are still in an index table (tested in
tests/integration/test_publish_outbox.py). This consumer only restores availability of the new version
and reclaims space.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg

from medops.ingestion import outbox
from medops.retrieval.lexical.pg_lexical_common import tsvector_literal
from medops.retrieval.lexical.tokenizer import Tokenizer

CONSUMER = "lexical-index"


@dataclass(frozen=True)
class IndexTarget:
    """One index table and how to produce its rows for a document."""

    name: str
    add: Callable[[psycopg.Connection[Any], uuid.UUID], int]
    remove: Callable[[psycopg.Connection[Any], uuid.UUID], int]


def tsvector_target(table: str, tokenizer: Tokenizer) -> IndexTarget:
    """Candidate A family: application-side tokens written as position-preserving tsvector literals."""

    def add(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
        rows = conn.execute("select chunk_id, content from chunks where doc_id = %s order by seq", (doc_id,)).fetchall()
        n = 0
        with conn.cursor() as cur:
            for chunk_id, content in rows:
                tokens = tokenizer.tokenize(content)
                if not tokens:
                    continue
                cur.execute(
                    f"insert into {table} (chunk_id, tsv) values (%s, %s::tsvector) on conflict (chunk_id) do nothing",
                    (chunk_id, tsvector_literal(tokens)),
                )
                n += cur.rowcount
        return n

    return IndexTarget(table, add, _remover(table))


def sql_tsvector_target(table: str, ts_config: str) -> IndexTarget:
    """Candidate B family: the database tokenizes with a fixed text search configuration."""

    def add(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
        cur = conn.execute(
            f"insert into {table} (chunk_id, tsv) "
            f"select chunk_id, to_tsvector('{ts_config}', content) from chunks where doc_id = %s "
            f"and to_tsvector('{ts_config}', content) <> ''::tsvector on conflict (chunk_id) do nothing",
            (doc_id,),
        )
        return cur.rowcount

    return IndexTarget(table, add, _remover(table))


def content_target(table: str) -> IndexTarget:
    """Candidate C: the bm25 index is maintained by the extension; the table holds chunk text."""

    def add(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
        cur = conn.execute(
            f"insert into {table} (chunk_id, content) select chunk_id, content from chunks where doc_id = %s "
            f"and content <> '' on conflict (chunk_id) do nothing",
            (doc_id,),
        )
        return cur.rowcount

    return IndexTarget(table, add, _remover(table))


def _remover(table: str) -> Callable[[psycopg.Connection[Any], uuid.UUID], int]:
    def remove(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
        cur = conn.execute(
            f"delete from {table} i using chunks c where c.chunk_id = i.chunk_id and c.doc_id = %s", (doc_id,)
        )
        return cur.rowcount

    return remove


def handler_for(targets: Sequence[IndexTarget]) -> outbox.Handler:
    def handle(conn: psycopg.Connection[Any], event: outbox.OutboxEvent) -> None:
        for target in targets:
            if event.event_type == "document_activated":
                target.add(conn, event.aggregate_id)
            elif event.event_type in ("document_archived", "document_withdrawn"):
                target.remove(conn, event.aggregate_id)

    return handle


def consume(conn: psycopg.Connection[Any], targets: Sequence[IndexTarget], *, limit: int = 50) -> list[int]:
    """Apply pending outbox events to the given index tables; returns acked event ids."""
    return outbox.run(conn, CONSUMER, handler_for(targets), limit=limit)
