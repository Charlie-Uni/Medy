"""ADR-0002 candidate A: application-side pretokenization + PostgreSQL `simple` FTS.

DEC-001 experiment adapter, not a selected production engine. The tokenizer (`tok-jieba-v1`,
norm-v1 first) runs on both the index and the query side; its output is written as a
POSITION-PRESERVING `tsvector` literal (baseline 3.6), never re-parsed by a text search parser,
so index lexemes and query lexemes are exactly the tokenizer's tokens. Predicate, ranking, filters
and the count-and-page statement are the shared recipe in `pg_lexical_common` (any change there or
here is a new RETRIEVER_VERSION).

Schema: `lexical_index_meta` (one row per index: the versions it was built with) and
`lexical_index_a` (chunk_id -> tsv), created by `install()` under the admin connection with FORCE ROW
LEVEL SECURITY and read access for the app/readonly roles only through the `chunks` policy. They are
deliberately NOT an Alembic revision until DEC-001 is decided.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

import psycopg

from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.pg_lexical_common import (
    MAX_LEXEME_BYTES,
    MAX_POSITION,
    MAX_POSITIONS_PER_LEXEME,
    META_DDL,
    META_TABLE,
    IndexBuildReport,
    check_k,
    check_versions_match,
    empty_result,
    explain_json,
    page_to_result,
    read_built_versions,
    require_identity,
    search_params,
    tsquery_literal,
    tsvector_index_ddl,
    tsvector_literal,
    tsvector_search_sql,
    upsert_meta,
)
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, Tokenizer

__all__ = [
    "INDEX_NAME",
    "INDEX_TABLE",
    "INSTALL_SQL",
    "MAX_LEXEME_BYTES",
    "MAX_POSITION",
    "MAX_POSITIONS_PER_LEXEME",
    "META_TABLE",
    "RETRIEVER_VERSION",
    "SEARCH_SQL",
    "IndexBuildReport",
    "PgSimpleFtsRetriever",
    "build_index",
    "configured_versions",
    "install",
    "tsquery_literal",
    "tsvector_literal",
]

RETRIEVER_VERSION = "pg-simple-fts-v1"
INDEX_NAME = "a"
INDEX_TABLE = "lexical_index_a"
INSTALL_SQL = META_DDL + tsvector_index_ddl(INDEX_TABLE)
SEARCH_SQL = tsvector_search_sql(INDEX_TABLE)


def install(conn: psycopg.Connection[Any]) -> None:
    """Create the candidate A tables, policies and grants (idempotent). Needs CREATE on schema public
    and must run as the migration/admin owner, never as an application role."""
    conn.execute(INSTALL_SQL)


def configured_versions(tokenizer: Tokenizer) -> LexicalVersions:
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=tokenizer.tokenizer_version,
        dictionary_version=tokenizer.dictionary_version,
        normalization_version=tokenizer.normalization_version,
    )


def build_index(
    conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, built_by: str, batch: int = 500
) -> IndexBuildReport:
    """(Re)build `lexical_index_a` over EVERY chunk visible to the connection's role (the admin role sees
    all; status/effective filtering is applied at query time, exactly as production would).

    All-or-nothing: rows and the meta row are replaced inside one transaction; a failure leaves the
    previous index and its versions untouched. Chunks whose text yields no tokens are not indexed (they
    can never match) and are counted in `skipped_empty`."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    versions = configured_versions(tokenizer)
    with conn.transaction():
        conn.execute(f"delete from {INDEX_TABLE}")
        rows: list[tuple[Any, str]] = []
        count = skipped = 0
        cursor = conn.cursor(name="lexical_a_build")  # server-side cursor: chunks are read in batches
        cursor.itersize = batch
        cursor.execute("select chunk_id, content from chunks order by chunk_id")
        for chunk_id, content in cursor:
            tokens = tokenizer.tokenize(content)
            if not tokens:
                skipped += 1
                continue
            rows.append((chunk_id, tsvector_literal(tokens)))
            if len(rows) >= batch:
                count += _flush(conn, rows)
                rows = []
        cursor.close()
        count += _flush(conn, rows)
        upsert_meta(conn, INDEX_NAME, versions, chunk_count=count, built_by=built_by)
    return IndexBuildReport(index_name=INDEX_NAME, chunk_count=count, skipped_empty=skipped, versions=versions)


def _flush(conn: psycopg.Connection[Any], rows: list[tuple[Any, str]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(f"insert into {INDEX_TABLE} (chunk_id, tsv) values (%s, %s::tsvector)", rows)
    return len(rows)


class PgSimpleFtsRetriever:
    """`LexicalRetriever` over an ORDINARY-ROLE connection. Every `search` must run inside the request
    transaction that carries the trusted identity (`set_config('medops.dept', ..., true)`); without an open
    transaction or without a department the adapter refuses instead of letting RLS return an empty,
    misleadingly "exhausted" page.

    `as_of` fixes the effective-time filter (default: today) so an experiment run is reproducible."""

    def __init__(self, conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, as_of: date | None = None) -> None:
        self._conn = conn
        self._tokenizer = tokenizer
        self._as_of = as_of

    @property
    def configured(self) -> LexicalVersions:
        """Versions of the tokenizer this instance would use for queries (must equal the built ones)."""
        return configured_versions(self._tokenizer)

    @property
    def versions(self) -> LexicalVersions:
        """Versions the index in the database was BUILT with (meta row), never the query configuration."""
        return read_built_versions(self._conn, INDEX_NAME)

    def _query_tokens(self, query: str) -> list[str]:
        return list(dict.fromkeys(self._tokenizer.tokenize(query)))

    def search(self, query: str, k: int) -> LexicalSearchResult:
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        tokens = self._query_tokens(query)
        if not tokens:
            return empty_result(k, built)
        rows = self._conn.execute(SEARCH_SQL, search_params(tokens, k, self._as_of)).fetchall()
        return page_to_result(rows, k, built)

    def explain(self, query: str, k: int) -> str:
        """`EXPLAIN (FORMAT JSON)` of the exact search statement under the current role and identity,
        for the execution-plan evidence ADR-0002 requires. Returns '' when the query has no tokens."""
        require_identity(self._conn)
        tokens = self._query_tokens(query)
        if not tokens:
            return ""
        return explain_json(self._conn, SEARCH_SQL, search_params(tokens, k, self._as_of))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-001 candidate A: install tables / build the lexical index")
    parser.add_argument("action", choices=("install", "build"))
    parser.add_argument("--admin-url", help="admin DSN (default: DATABASE_ADMIN_URL from settings)")
    parser.add_argument("--built-by", default="dec001-a-build", help="audit label stored in the meta row")
    args = parser.parse_args(argv)
    dsn = args.admin_url
    if not dsn:
        from medops.core.config import Settings

        settings = Settings()  # type: ignore[call-arg]
        secret = settings.database_admin_url or settings.database_url
        dsn = secret.get_secret_value()
    with psycopg.connect(dsn) as conn:
        if args.action == "install":
            install(conn)
            conn.commit()
            print(json.dumps({"installed": [META_TABLE, INDEX_TABLE]}))
            return 0
        report = build_index(conn, JiebaTokenizerV1(), built_by=args.built_by)
        print(json.dumps(report.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
