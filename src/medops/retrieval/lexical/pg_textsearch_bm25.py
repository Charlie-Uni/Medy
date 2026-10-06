"""ADR-0002 candidate D (revision 5): `pg_textsearch` BM25 (Tiger Data, PostgreSQL License) on PostgreSQL 17.

DEC-001 experiment adapter, not a selected production engine. It differs from the production engine A2 in the
ranking function and index engine ONLY: the index column holds the same `tok-jieba-v2` tokens (with the pinned
English stopword list) that A2 puts into its tsvector, joined by spaces, and the BM25 index tokenizes them with
the `simple` text search configuration (lower-casing, whitespace splitting). Queries go through the same tokenizer.

Fixed configuration (declared before any observation, ADR-0002 revision 5): `k1 = 1.2`, `b = 0.75` (extension
defaults); query terms are OR-ed (the BM25 query's own semantics); ranking is the extension's score ascending (the
`<@>` operator returns the NEGATED BM25 score, so the best match sorts first) with `chunk_id` ascending on ties;
rows that match no query term score 0 and are excluded by the `< 0` predicate; filters are the RLS chain plus
`status = 'active'` and the effective window; exhaustion is established by fetching k+1 rows (see SEARCH_SQL).

Observed in the image smoke (2026-10-06): under FORCE RLS the planner uses the BM25 index scan with the policy as
a per-row filter and the LIMIT is satisfied from visible rows only — 20 / 500 / 1,000 of 1,000 visible matches were
returned when 19,000 hidden rows scored higher — so there is no silent shortfall by construction; the adapter
suite re-checks this on the real tables. Corpus statistics (document frequencies) include rows hidden by RLS: a
ranking inside one department is influenced by other departments' vocabulary. ADR-0002 revision 5 makes the
assessment of that channel a hard gate before any production use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

import psycopg

from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION
from medops.retrieval.lexical.pg_lexical_common import (
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
    text_index_ddl,
    upsert_meta,
)
from medops.retrieval.lexical.tokenizer import Tokenizer

RETRIEVER_VERSION = "pg-textsearch-bm25-v1"
RELEASE_STATUS = "experimental"  # PostgreSQL License; production use needs ADR-0002 revision 5's gates
INDEX_NAME = "d"
INDEX_TABLE = "lexical_index_d"
BM25_INDEX = f"{INDEX_TABLE}_bm25"
EXTENSION = "pg_textsearch"
EXPECTED_EXTENSION_VERSION = "1.5.1"
TEXT_CONFIG = "simple"
K1 = 1.2
B = 0.75
INSTALL_SQL = (
    META_DDL
    + text_index_ddl(INDEX_TABLE)
    + f"create index if not exists {BM25_INDEX} on {INDEX_TABLE} using bm25 (content) "
    f"with (text_config = '{TEXT_CONFIG}', k1 = {K1}, b = {B});\n"
)
# Top-(k+1) through the BM25 index scan. The other adapters count every eligible row in the same statement; here
# that count forces BM25 scoring of every matching row (about 800 ms on 36,100 chunks) while the index returns the
# top k in a few milliseconds, so exhaustion is established exactly by asking for one row more than k: fewer than
# k+1 rows back means the visible matches are exhausted (the index scan with the RLS / status filters does not stop
# early — builds/d smoke, 19,000 hidden rows). Ranking and filters are unchanged (ADR-0002 revision 5 addendum).
SEARCH_SQL = f"""
select i.chunk_id, -(i.content <@> to_bm25query(%(q)s, '{BM25_INDEX}')) as score
from {INDEX_TABLE} i
join chunks c on c.chunk_id = i.chunk_id
join documents d on d.doc_id = c.doc_id
where (i.content <@> to_bm25query(%(q)s, '{BM25_INDEX}')) < 0
  and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
  and d.effective_from <= %(as_of)s
  and (d.effective_to is null or d.effective_to > %(as_of)s)
order by i.content <@> to_bm25query(%(q)s, '{BM25_INDEX}'), i.chunk_id
limit %(k_plus_one)s
"""


class InstallError(RuntimeError):
    """The server does not match the fixed candidate D identity."""


def _extension_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("select extversion from pg_extension where extname = %s", (EXTENSION,)).fetchone()
    return None if row is None else str(row[0])


def install(conn: psycopg.Connection[Any]) -> None:
    """Create / verify the extension at the fixed version and the candidate D table + bm25 index (idempotent).
    Must run as the server's superuser owner; the server must preload `pg_textsearch`."""
    conn.execute(f"create extension if not exists {EXTENSION}")
    version = _extension_version(conn)
    if version != EXPECTED_EXTENSION_VERSION:
        raise InstallError(f"{EXTENSION} version {version} != expected {EXPECTED_EXTENSION_VERSION}")
    conn.execute(INSTALL_SQL)


def configured_versions(conn: psycopg.Connection[Any], tokenizer: Tokenizer) -> LexicalVersions:
    version = _extension_version(conn)
    if version is None:
        raise InstallError(f"{EXTENSION} is not installed in this database")
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=f"{tokenizer.tokenizer_version}+{EXTENSION}-{version}:{TEXT_CONFIG}:k1={K1}:b={B}",
        dictionary_version=tokenizer.dictionary_version,
        normalization_version=NORMALIZATION_VERSION,
    )


def build_index(
    conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, built_by: str, batch: int = 500
) -> IndexBuildReport:
    """(Re)build `lexical_index_d` from every chunk visible to the connection's role: the same tokens A2 indexes,
    joined by spaces; the bm25 index is maintained by the extension. All-or-nothing in one transaction."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    with conn.transaction():
        versions = configured_versions(conn, tokenizer)
        conn.execute(f"delete from {INDEX_TABLE}")
        rows: list[tuple[Any, str]] = []
        count = skipped = 0
        cursor = conn.cursor(name=f"lexical_{INDEX_NAME}_build")
        cursor.itersize = batch
        cursor.execute("select chunk_id, content from chunks order by chunk_id")
        for chunk_id, content in cursor:
            tokens = tokenizer.tokenize(content)
            if not tokens:
                skipped += 1
                continue
            rows.append((chunk_id, " ".join(tokens)))
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
        cur.executemany(f"insert into {INDEX_TABLE} (chunk_id, content) values (%s, %s)", rows)
    return len(rows)


def _params(q: str, k: int, as_of: date | None, allow_historical: bool = False) -> dict[str, Any]:
    return {"q": q, "as_of": as_of or date.today(), "k_plus_one": k + 1, "allow_historical": bool(allow_historical)}


def _page(rows: Sequence[tuple[Any, Any]], k: int) -> list[tuple[Any, Any, int]]:
    """k+1 rows -> the page rows `page_to_result` expects: eligible is exact when the fetch came back short, and
    "at least k+1" otherwise (the page is then exactly k long and not exhausted)."""
    eligible = len(rows) if len(rows) <= k else k + 1
    return [(chunk_id, score, eligible) for chunk_id, score in rows[:k]]


class PgTextsearchBm25Retriever:
    """`LexicalRetriever` over an ORDINARY-ROLE connection; same transaction / identity and version rules as the
    other candidates. Query tokens come from the same tokenizer instance that built the index."""

    def __init__(self, conn: psycopg.Connection[Any], tokenizer: Tokenizer, *, as_of: date | None = None) -> None:
        self._conn = conn
        self._tokenizer = tokenizer
        self._as_of = as_of

    @property
    def configured(self) -> LexicalVersions:
        return configured_versions(self._conn, self._tokenizer)

    @property
    def versions(self) -> LexicalVersions:
        return read_built_versions(self._conn, INDEX_NAME)

    def query_text(self, query: str) -> str:
        """Distinct query tokens in first-occurrence order, space-joined for the BM25 query parser."""
        return " ".join(dict.fromkeys(self._tokenizer.tokenize(query)))

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> LexicalSearchResult:
        if doc_ids:
            raise NotImplementedError("named-document focus is implemented for the production retrievers only")
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        q = self.query_text(query)
        if not q:
            return empty_result(k, built)
        rows = self._conn.execute(SEARCH_SQL, _params(q, k, self._as_of, allow_historical)).fetchall()
        return page_to_result(_page(rows, k), k, built)

    def explain(self, query: str, k: int, *, allow_historical: bool = False) -> str:
        require_identity(self._conn)
        q = self.query_text(query)
        if not q:
            return ""
        return explain_json(self._conn, SEARCH_SQL, _params(q, k, self._as_of, allow_historical))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-001 candidate D (pg_textsearch): install / build the bm25 index")
    parser.add_argument("action", choices=("install", "build"))
    parser.add_argument("--admin-url", help="superuser DSN of the candidate D server (default: $DEC001_D_ADMIN_URL)")
    parser.add_argument("--built-by", default="dec001-d-build")
    args = parser.parse_args(argv)
    dsn = args.admin_url or os.environ.get("DEC001_D_ADMIN_URL")
    if not dsn:
        parser.error("--admin-url or DEC001_D_ADMIN_URL is required (candidate D runs on its own server)")
    from medops.retrieval.production import production_tokenizer

    with psycopg.connect(dsn) as conn:
        if args.action == "install":
            install(conn)
            conn.commit()
            print(json.dumps({"installed": [META_TABLE, INDEX_TABLE, BM25_INDEX], "release_status": RELEASE_STATUS}))
            return 0
        report = build_index(conn, production_tokenizer(), built_by=args.built_by)
        print(json.dumps({**report.as_dict(), "release_status": RELEASE_STATUS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
