"""ADR-0002 candidate C: `pg_search` BM25 (ParadeDB, Tantivy) with the `pdb.jieba` tokenizer inside the database.

DEC-001 experiment adapter. Licence status of the component is `release_blocked` (AGPL-3.0 community
edition without a written approval for this project's release model); this adapter exists to produce
comparison evidence, and a technically better score cannot select it for production (ADR-0002).

Fixed configuration (builds/c/smoke.sql, before any observation): tokenizer
`pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')`, no custom
dictionary, no stemming/stopwords/length filters, no script conversion.

Pre-run rules (declared before any probe query is executed):
- the query is norm-v1 normalized, tokenized by the SAME `pdb.jieba` configuration in SQL, and lexemes
  that are whitespace- or punctuation-only are dropped (the default jieba tokenizer keeps whitespace as a
  token, which would make an OR query match almost every chunk);
- the predicate is the match-disjunction operator `|||` over the remaining distinct terms passed as a
  text[] (OR across query terms, like A and B); ranking is `paradedb.score()` descending with `chunk_id`
  ascending on ties; filters are the RLS chain plus `status = 'active'` and the effective window, and the
  exact count and the ranked page come from one statement (`count(*) over ()`).

Versions: `tokenizer_version` is computed at runtime from the live extension version and the tokenizer
configuration string; `dictionary_version` pins the embedded jieba dictionary through the SHA-256 of the
extension shared object that `install()` verifies byte-for-byte (an ordinary role cannot read it).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

import psycopg

from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text
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

RETRIEVER_VERSION = "pg-search-bm25-v1"
RELEASE_STATUS = "release_blocked"
INDEX_NAME = "c"
INDEX_TABLE = "lexical_index_c"
BM25_INDEX = f"{INDEX_TABLE}_bm25"
EXTENSION = "pg_search"
EXPECTED_EXTENSION_VERSION = "0.25.9"
TOKENIZER_SQL = "pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')"
TOKENIZER_CONFIG = "pdb.jieba;lowercase=true;ascii_folding=false;alpha_num_only=false;trim=false"
EXTENSION_BINARY = "/usr/lib/postgresql/16/lib/pg_search.so"
EXTENSION_BINARY_SHA256 = (
    "74e90e4f8015246af4a03b15201abf092efd238b5552556dcf1daa604c4fd50b"  # builds/c/build-metadata.json
)
DICTIONARY_VERSION = "jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:" + EXTENSION_BINARY_SHA256[:16]
INSTALL_SQL = (
    META_DDL
    + text_index_ddl(INDEX_TABLE)
    + f"create index if not exists {BM25_INDEX} on {INDEX_TABLE} using bm25 (chunk_id, (content::{TOKENIZER_SQL})) "
    f"with (key_field = 'chunk_id');\n"
)
SEARCH_SQL = f"""
with eligible as (
    select i.chunk_id, paradedb.score(i.chunk_id) as score
    from {INDEX_TABLE} i
    join chunks c on c.chunk_id = i.chunk_id
    join documents d on d.doc_id = c.doc_id
    where (i.content::{TOKENIZER_SQL}) ||| %(terms)s::text[]
      and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
      and d.effective_from <= %(as_of)s
      and (d.effective_to is null or d.effective_to > %(as_of)s)
)
select chunk_id, score, count(*) over () as eligible_count
from eligible
order by score desc, chunk_id asc
limit %(k)s
"""
_PUNCT_OR_SPACE_ONLY = re.compile(r"^[\W_]+$")


class InstallError(RuntimeError):
    """The server does not match the fixed candidate C identity (extension version or binary bytes)."""


def _extension_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("select extversion from pg_extension where extname = %s", (EXTENSION,)).fetchone()
    return None if row is None else str(row[0])


def verify_extension_binary(conn: psycopg.Connection[Any], expected: str = EXTENSION_BINARY_SHA256) -> None:
    """Superuser-only byte check of the extension shared object (embedded jieba dictionary) in the image."""
    row = conn.execute("select encode(sha256(pg_read_binary_file(%s)), 'hex')", (EXTENSION_BINARY,)).fetchone()
    actual = None if row is None else str(row[0])
    if actual != expected:
        raise InstallError(f"{EXTENSION_BINARY} sha256 {actual} != expected {expected}")


def install(conn: psycopg.Connection[Any]) -> None:
    """Create/verify the extensions at the fixed versions and the candidate C table + bm25 index
    (idempotent). Must run as the superuser owner: it reads the extension binary."""
    conn.execute("create extension if not exists vector")  # pg_search 0.25.9 loads only after vector
    conn.execute(f"create extension if not exists {EXTENSION} version '{EXPECTED_EXTENSION_VERSION}'")
    version = _extension_version(conn)
    if version != EXPECTED_EXTENSION_VERSION:
        raise InstallError(f"{EXTENSION} version {version} != expected {EXPECTED_EXTENSION_VERSION}")
    verify_extension_binary(conn)
    conn.execute(INSTALL_SQL)


def runtime_tokenizer_version(conn: psycopg.Connection[Any]) -> str:
    version = _extension_version(conn)
    if version is None:
        raise InstallError(f"{EXTENSION} is not installed in this database")
    cfg_hash = hashlib.sha256(TOKENIZER_CONFIG.encode()).hexdigest()[:8]
    return f"{EXTENSION}-{version}+{TOKENIZER_CONFIG.split(';')[0]}:{cfg_hash}"


def configured_versions(
    conn: psycopg.Connection[Any], *, dictionary_version: str = DICTIONARY_VERSION
) -> LexicalVersions:
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=runtime_tokenizer_version(conn),
        dictionary_version=dictionary_version,
        normalization_version=NORMALIZATION_VERSION,
    )


def query_terms(conn: psycopg.Connection[Any], text: str) -> list[str]:
    """norm-v1, then the fixed `pdb.jieba` tokenizer in SQL; distinct terms in first-occurrence order with
    whitespace- and punctuation-only tokens dropped."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    row = conn.execute(f"select %s::{TOKENIZER_SQL}::text[]", (normalized,)).fetchone()
    tokens = [] if row is None else [str(t) for t in row[0]]
    return list(dict.fromkeys(t for t in tokens if not _PUNCT_OR_SPACE_ONLY.match(t)))


def build_index(conn: psycopg.Connection[Any], *, built_by: str) -> IndexBuildReport:
    """(Re)build `lexical_index_c` from every chunk visible to the connection's role; the bm25 index is
    maintained by the extension. All-or-nothing in one transaction; empty contents are skipped."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    with conn.transaction():
        versions = configured_versions(conn)
        conn.execute(f"delete from {INDEX_TABLE}")
        total = int(conn.execute("select count(*) from chunks").fetchone()[0])  # type: ignore[index]
        cur = conn.execute(
            f"insert into {INDEX_TABLE} (chunk_id, content) select chunk_id, content from chunks where content <> ''"
        )
        count = cur.rowcount
        upsert_meta(conn, INDEX_NAME, versions, chunk_count=count, built_by=built_by)
    return IndexBuildReport(index_name=INDEX_NAME, chunk_count=count, skipped_empty=total - count, versions=versions)


def _params(terms: Sequence[str], k: int, as_of: date | None, allow_historical: bool = False) -> dict[str, Any]:
    return {"terms": list(terms), "as_of": as_of or date.today(), "k": k, "allow_historical": bool(allow_historical)}


class PgSearchBm25Retriever:
    """`LexicalRetriever` over an ORDINARY-ROLE connection; same transaction/identity and version rules as
    candidates A and B. `dictionary_version` is the operator-declared pin verified by `install()`."""

    def __init__(
        self, conn: psycopg.Connection[Any], *, as_of: date | None = None, dictionary_version: str = DICTIONARY_VERSION
    ) -> None:
        self._conn = conn
        self._as_of = as_of
        self._dictionary_version = dictionary_version

    @property
    def configured(self) -> LexicalVersions:
        return configured_versions(self._conn, dictionary_version=self._dictionary_version)

    @property
    def versions(self) -> LexicalVersions:
        return read_built_versions(self._conn, INDEX_NAME)

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> LexicalSearchResult:
        if doc_ids:
            raise NotImplementedError("named-document focus is implemented for the production retrievers only")
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        terms = query_terms(self._conn, query)
        if not terms:
            return empty_result(k, built)
        rows = self._conn.execute(SEARCH_SQL, _params(terms, k, self._as_of, allow_historical)).fetchall()
        return page_to_result(rows, k, built)

    def explain(self, query: str, k: int, *, allow_historical: bool = False) -> str:
        require_identity(self._conn)
        terms = query_terms(self._conn, query)
        if not terms:
            return ""
        return explain_json(self._conn, SEARCH_SQL, _params(terms, k, self._as_of, allow_historical))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DEC-001 candidate C (release_blocked): install / build the bm25 index"
    )
    parser.add_argument("action", choices=("install", "build"))
    parser.add_argument("--admin-url", help="superuser DSN of the candidate C server (default: $DEC001_C_ADMIN_URL)")
    parser.add_argument("--built-by", default="dec001-c-build")
    args = parser.parse_args(argv)
    dsn = args.admin_url or os.environ.get("DEC001_C_ADMIN_URL")
    if not dsn:
        parser.error("--admin-url or DEC001_C_ADMIN_URL is required (candidate C runs on its own server)")
    with psycopg.connect(dsn) as conn:
        if args.action == "install":
            install(conn)
            conn.commit()
            print(json.dumps({"installed": [META_TABLE, INDEX_TABLE, BM25_INDEX], "release_status": RELEASE_STATUS}))
            return 0
        report = build_index(conn, built_by=args.built_by)
        print(json.dumps({**report.as_dict(), "release_status": RELEASE_STATUS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
