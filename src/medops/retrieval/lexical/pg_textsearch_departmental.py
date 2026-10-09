"""Production BM25 with one physical corpus per department.

``pg_textsearch`` computes inverse document frequency over every row in one BM25
index, including rows hidden by PostgreSQL row-level security.  MedOps therefore
does not put the three departments in one index.  A chunk is copied into every
department corpus named by its read ACL and each table has its own BM25 index.
The table policy also pins the current transaction identity to that department;
the normal ``table -> chunks -> documents -> document_acl`` RLS chain remains a
second, authoritative permission check.

The adapter deliberately keeps the candidate-D tokenizer and BM25 parameters.
Only the physical corpus layout and the production retriever identity differ.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

import psycopg

from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical import index_consumer
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION
from medops.retrieval.lexical.pg_lexical_common import (
    IndexBuildReport,
    check_k,
    check_versions_match,
    empty_result,
    explain_json,
    page_to_result,
    read_built_versions,
    require_identity,
    upsert_meta,
)
from medops.retrieval.lexical.tokenizer import Tokenizer

RETRIEVER_VERSION = "pg-textsearch-bm25-departmental-v1"
INDEX_NAME = "production-lexical"
EXTENSION = "pg_textsearch"
EXPECTED_EXTENSION_VERSION = "1.5.1"
TEXT_CONFIG = "simple"
K1 = 1.2
B = 0.75
DEPARTMENTS = ("MA", "PV", "CO")
TABLES = {dept: f"chunk_lexical_bm25_{dept.lower()}" for dept in DEPARTMENTS}
INDEXES = {dept: f"{TABLES[dept]}_idx" for dept in DEPARTMENTS}


class InstallError(RuntimeError):
    """The database server cannot run the pinned production BM25 adapter."""


def extension_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("select extversion from pg_extension where extname = %s", (EXTENSION,)).fetchone()
    return None if row is None else str(row[0])


def require_extension(conn: psycopg.Connection[Any]) -> None:
    version = extension_version(conn)
    if version != EXPECTED_EXTENSION_VERSION:
        raise InstallError(f"{EXTENSION} version {version} != expected {EXPECTED_EXTENSION_VERSION}")


def configured_versions(tokenizer: Tokenizer) -> LexicalVersions:
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=(
            f"{tokenizer.tokenizer_version}+{EXTENSION}-{EXPECTED_EXTENSION_VERSION}:"
            f"{TEXT_CONFIG}:k1={K1}:b={B}:corpus=department"
        ),
        dictionary_version=tokenizer.dictionary_version,
        normalization_version=NORMALIZATION_VERSION,
    )


def _search_sql(dept: str) -> str:
    table, index = TABLES[dept], INDEXES[dept]
    return f"""
select i.chunk_id, -(i.content <@> to_bm25query(%(q)s, '{index}')) as score
from {table} i
join chunks c on c.chunk_id = i.chunk_id
join documents d on d.doc_id = c.doc_id
where (i.content <@> to_bm25query(%(q)s, '{index}')) < 0
  and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
  and d.effective_from <= %(as_of)s
  and (d.effective_to is null or d.effective_to > %(as_of)s)
  and (%(doc_ids)s::uuid[] is null or c.doc_id = any(%(doc_ids)s::uuid[]))
order by i.content <@> to_bm25query(%(q)s, '{index}'), i.chunk_id
limit %(k_plus_one)s
"""


def _department(conn: psycopg.Connection[Any]) -> str:
    require_identity(conn)
    row = conn.execute("select medops_current_dept()::text").fetchone()
    dept = None if row is None else row[0]
    if dept not in TABLES:
        # ``require_identity`` normally catches this first.  Keep the mapping
        # failure sanitized if the database enum and application ever drift.
        raise ValueError("unsupported department identity")
    return str(dept)


def _params(
    query: str,
    k: int,
    as_of: date | None,
    allow_historical: bool,
    doc_ids: Sequence[str] | None,
) -> dict[str, Any]:
    return {
        "q": query,
        "as_of": as_of or date.today(),
        "k_plus_one": k + 1,
        "allow_historical": bool(allow_historical),
        "doc_ids": list(doc_ids) if doc_ids else None,
    }


def _page(rows: Sequence[tuple[Any, Any]], k: int) -> list[tuple[Any, Any, int]]:
    eligible = len(rows) if len(rows) <= k else k + 1
    return [(chunk_id, score, eligible) for chunk_id, score in rows[:k]]


class DepartmentalBm25Retriever:
    """BM25 retrieval over the physical corpus for the transaction department."""

    def __init__(self, conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, as_of: date | None = None) -> None:
        self._conn = conn
        self._tokenizer = tokenizer
        self._as_of = as_of

    @property
    def configured(self) -> LexicalVersions:
        require_extension(self._conn)
        return configured_versions(self._tokenizer)

    @property
    def versions(self) -> LexicalVersions:
        return read_built_versions(self._conn, INDEX_NAME)

    def query_text(self, query: str) -> str:
        return " ".join(dict.fromkeys(self._tokenizer.tokenize(query)))

    def search(
        self,
        query: str,
        k: int,
        *,
        allow_historical: bool = False,
        doc_ids: Sequence[str] | None = None,
    ) -> LexicalSearchResult:
        check_k(k)
        dept = _department(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        normalized = self.query_text(query)
        if not normalized:
            return empty_result(k, built)
        rows = self._conn.execute(
            _search_sql(dept), _params(normalized, k, self._as_of, allow_historical, doc_ids)
        ).fetchall()
        return page_to_result(_page(rows, k), k, built)

    def explain(self, query: str, k: int, *, allow_historical: bool = False) -> str:
        check_k(k)
        dept = _department(self._conn)
        normalized = self.query_text(query)
        if not normalized:
            return ""
        return explain_json(
            self._conn,
            _search_sql(dept),
            _params(normalized, k, self._as_of, allow_historical, None),
        )


def _flush(conn: psycopg.Connection[Any], table: str, rows: list[tuple[Any, str]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(f"insert into {table} (chunk_id, content) values (%s, %s)", rows)
    return len(rows)


def build_index(
    conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, built_by: str, batch: int = 500
) -> IndexBuildReport:
    """Rebuild every department corpus from the authoritative ACL in one transaction."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    if batch < 1:
        raise ValueError("batch must be positive")
    with conn.transaction():
        require_extension(conn)
        # Keep the server-side cursor's snapshot aligned with the authoritative
        # corpus until every derived row commits.  The supported ACL/status
        # writers lock the document FOR UPDATE, while these row locks also
        # block a direct revoke of an existing ACL.  Row locks preserve the
        # admin role's least privilege; a SHARE table lock would require
        # broader privileges on immutable chunks.
        conn.execute("select doc_id from documents order by doc_id for share").fetchall()
        conn.execute(
            "select doc_id, dept, permission from document_acl order by doc_id, dept, permission for share"
        ).fetchall()
        versions = configured_versions(tokenizer)
        for table in TABLES.values():
            conn.execute(f"delete from {table}")
        pending: dict[str, list[tuple[Any, str]]] = {dept: [] for dept in DEPARTMENTS}
        indexed_chunks: set[uuid.UUID] = set()
        skipped: set[uuid.UUID] = set()
        cursor = conn.cursor(name="lexical_production_bm25_build")
        cursor.itersize = batch
        cursor.execute(
            """select c.chunk_id, c.content, array_agg(a.dept::text order by a.dept::text)
                 from chunks c
                 join documents d on d.doc_id=c.doc_id and d.status in ('active', 'archived')
                 join document_acl a on a.doc_id=c.doc_id and a.permission='read'
                group by c.chunk_id, c.content
                order by c.chunk_id"""
        )
        for chunk_id, content, depts in cursor:
            tokens = tokenizer.tokenize(content)
            if not tokens:
                skipped.add(chunk_id)
                continue
            normalized = " ".join(tokens)
            indexed_chunks.add(chunk_id)
            for dept in depts:
                if dept not in pending:
                    raise ValueError("document ACL contains an unsupported department")
                pending[dept].append((chunk_id, normalized))
                if len(pending[dept]) >= batch:
                    _flush(conn, TABLES[dept], pending[dept])
                    pending[dept] = []
        cursor.close()
        for dept in DEPARTMENTS:
            _flush(conn, TABLES[dept], pending[dept])
        upsert_meta(
            conn,
            INDEX_NAME,
            versions,
            chunk_count=len(indexed_chunks),
            built_by=built_by,
        )
    return IndexBuildReport(
        index_name=INDEX_NAME,
        chunk_count=len(indexed_chunks),
        skipped_empty=len(skipped),
        versions=versions,
    )


def _remove_document(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
    removed = 0
    for table in TABLES.values():
        removed += conn.execute(
            f"delete from {table} i using chunks c where c.chunk_id=i.chunk_id and c.doc_id=%s",
            (doc_id,),
        ).rowcount
    return removed


def index_target(tokenizer: Tokenizer) -> index_consumer.IndexTarget:
    """Outbox target that reconciles all ACL copies for one document."""

    def add(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
        _remove_document(conn, doc_id)
        rows = conn.execute(
            """select c.chunk_id, c.content, array_agg(a.dept::text order by a.dept::text)
                 from chunks c
                 join documents d on d.doc_id=c.doc_id and d.status in ('active', 'archived')
                 join document_acl a on a.doc_id=c.doc_id and a.permission='read'
                where c.doc_id=%s
                group by c.chunk_id, c.content
                order by c.chunk_id""",
            (doc_id,),
        ).fetchall()
        added = 0
        for chunk_id, content, depts in rows:
            tokens = tokenizer.tokenize(content)
            if not tokens:
                continue
            normalized = " ".join(tokens)
            for dept in depts:
                table = TABLES.get(dept)
                if table is None:
                    raise ValueError("document ACL contains an unsupported department")
                added += conn.execute(
                    f"insert into {table} (chunk_id, content) values (%s, %s) "
                    "on conflict (chunk_id) do update set content=excluded.content",
                    (chunk_id, normalized),
                ).rowcount
        return added

    return index_consumer.IndexTarget("departmental-bm25", add, _remove_document)


def document_gap_count(conn: psycopg.Connection[Any], doc_id: uuid.UUID) -> int:
    """Missing/empty department assignments for one document after reconciliation."""
    total = 0
    for dept, table in TABLES.items():
        row = conn.execute(
            f"""select count(*)
                   from chunks c
                   join document_acl a on a.doc_id=c.doc_id and a.permission='read' and a.dept=%s
                   left join {table} i on i.chunk_id=c.chunk_id
                  where c.doc_id=%s and (i.chunk_id is null or i.content='')""",
            (dept, doc_id),
        ).fetchone()
        total += int(row[0]) if row else 0
    return total
