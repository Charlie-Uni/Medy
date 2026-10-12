"""Shared documents test support; no collected test cases."""

from __future__ import annotations

import uuid
from datetime import date

import psycopg


def _hash(n: int) -> str:
    return f"{n:064x}"


def source_object(conn: psycopg.Connection, n: int = 1, **overrides) -> uuid.UUID:
    row = {
        "source_hash": _hash(n),
        "storage_uri": f"file:///sources/{_hash(n)}.pdf",
        "byte_size": 1000 + n,
        "mime": "application/pdf",
        "created_by": "ingest-01",
    }
    row.update(overrides)
    cur = conn.execute(
        "insert into source_objects (source_hash, storage_uri, byte_size, mime, created_by) values (%(source_hash)s, %(storage_uri)s, %(byte_size)s, %(mime)s, %(created_by)s) returning source_object_id",
        row,
    )
    return cur.fetchone()[0]


def job(
    conn: psycopg.Connection, source_id: uuid.UUID, *, status: str = "succeeded", quality: str = "trusted"
) -> uuid.UUID:
    cur = conn.execute(
        "insert into ingestion_jobs (source_object_id, status, parse_quality, parser_version, failure_reason) values (%s, %s, %s, 'pypdf-6.18.1', %s) returning job_id",
        (source_id, status, quality, "boom" if status == "failed" else None),
    )
    return cur.fetchone()[0]


def document(conn: psycopg.Connection, source_id: uuid.UUID, job_id: uuid.UUID | None = None, **overrides) -> uuid.UUID:
    row = {
        "family_id": uuid.uuid4(),
        "title": "示例药品X片说明书",
        "doc_type": "label",
        "version": "2026-01",
        "status": "draft",
        "effective_from": None,
        "effective_to": None,
        "source_object_id": source_id,
        "active_ingestion_job_id": job_id,
        "parse_quality": "pending" if job_id is None else "trusted",
        "owner_dept": "MA",
        "language": "zh-Hans",
        "created_by": "ingest-01",
    }
    row.update(overrides)
    cur = conn.execute(
        """insert into documents (family_id, title, doc_type, version, status, effective_from, effective_to, source_object_id,
                                  active_ingestion_job_id, parse_quality, owner_dept, language, created_by)
           values (%(family_id)s, %(title)s, %(doc_type)s, %(version)s, %(status)s, %(effective_from)s, %(effective_to)s,
                   %(source_object_id)s, %(active_ingestion_job_id)s, %(parse_quality)s, %(owner_dept)s, %(language)s, %(created_by)s)
           returning doc_id""",
        row,
    )
    return cur.fetchone()[0]


def active_document(
    conn: psycopg.Connection, n: int = 1, family: uuid.UUID | None = None, version: str = "2026-01"
) -> tuple[uuid.UUID, uuid.UUID]:
    src = source_object(conn, n)
    j = job(conn, src)
    doc = document(
        conn,
        src,
        j,
        family_id=family or uuid.uuid4(),
        version=version,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    return doc, src


def set_actor(conn: psycopg.Connection, actor: str = "reviewer-01", reason: str | None = None) -> None:
    conn.execute("select set_config('medops.actor', %s, true)", (actor,))
    if reason is not None:
        conn.execute("select set_config('medops.reason', %s, true)", (reason,))
