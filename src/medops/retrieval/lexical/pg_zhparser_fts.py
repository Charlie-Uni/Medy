"""ADR-0002 candidate B: PostgreSQL FTS with the `zhparser` parser (SCWS) tokenizing INSIDE the database.

DEC-001 experiment adapter, not a selected production engine. Tokenization happens in SQL through the
text search configuration `dec001_b` (parser zhparser, every declared POS type except `w` mapped to the
`simple` dictionary, fixed before any observation, see builds/b/smoke.sql). Chunk content is already
norm-v1 text; queries are norm-v1 normalized in the application before they reach `to_tsvector`.

Pre-run rule (declared before any probe query is executed): query lexemes that consist only of
punctuation or symbols are dropped, because zhparser keeps `。 . - /` as lexemes and an OR predicate
containing them would match almost every chunk. The index side is untouched.

Versions: `tokenizer_version` is computed at runtime from the live extension version, the configuration
mapping and the `zhparser.*` GUCs; `dictionary_version` pins the SHA-256 of the SCWS dictionary and rule
files that `install()` verifies byte-for-byte in the image (an ordinary role cannot read them), together
with the SCWS version recorded at build time. Predicate, ranking, filters and the count-and-page statement
are the shared recipe in `pg_lexical_common`.
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
    search_params,
    tsvector_index_ddl,
    tsvector_search_sql,
    upsert_meta,
)

RETRIEVER_VERSION = "pg-zhparser-fts-v1"
INDEX_NAME = "b"
INDEX_TABLE = "lexical_index_b"
TS_CONFIG = "dec001_b"
EXTENSION = "zhparser"
EXPECTED_EXTENSION_VERSION = "2.3"
SCWS_VERSION = "1.2.3"  # scws-cli/1.2.3, builds/b/evidence-2026-09-20/scws_version.txt (not queryable in SQL)
MAPPED_TOKEN_TYPES: tuple[str, ...] = tuple(t for t in "abcdefghijklmnopqrstuvwxyz" if t != "w")
DICTIONARY_FILES: dict[
    str, str
] = {  # path in the image -> SHA-256 (builds/b/evidence-2026-09-20/installed_sha256sums.txt)
    "/usr/share/postgresql/16/tsearch_data/dict.utf8.xdb": (
        "fd76a689f996c4e68ce53325a6a24dc652a678b1e7f676e4c5ca76265609a3e2"
    ),
    "/usr/share/postgresql/16/tsearch_data/rules.utf8.ini": (
        "45395f794226581fb1cc02b44ae1481804152511fc59fa677e2f7b755440479c"
    ),
}
DICTIONARY_VERSION = "scws-dict-utf8:fd76a689f996c4e6+rules-utf8:45395f794226581f+scws-" + SCWS_VERSION
INSTALL_SQL = META_DDL + tsvector_index_ddl(INDEX_TABLE)
SEARCH_SQL = tsvector_search_sql(INDEX_TABLE)
_PUNCT_ONLY = re.compile(r"^[\W_]+$")


class InstallError(RuntimeError):
    """The server does not match the fixed candidate B identity (extension, mapping or dictionary bytes)."""


# ------------------------------------------------------------------------------- install / identity


def _extension_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("select extversion from pg_extension where extname = %s", (EXTENSION,)).fetchone()
    return None if row is None else str(row[0])


def _mapping(conn: psycopg.Connection[Any]) -> list[tuple[str, int, str]]:
    rows = conn.execute(
        "select chr(maptokentype), mapseqno, mapdict::regdictionary::text from pg_ts_config_map "
        "where mapcfg = %s::regconfig order by maptokentype, mapseqno",
        (TS_CONFIG,),
    ).fetchall()
    return [(str(t), int(n), str(d)) for t, n, d in rows]


def verify_dictionary_files(conn: psycopg.Connection[Any], expected: dict[str, str] | None = None) -> None:
    """Superuser-only byte check of the SCWS dictionary and rules inside the image."""
    for path, digest in (expected or DICTIONARY_FILES).items():
        row = conn.execute("select encode(sha256(pg_read_binary_file(%s)), 'hex')", (path,)).fetchone()
        actual = None if row is None else str(row[0])
        if actual != digest:
            raise InstallError(f"dictionary file {path} sha256 {actual} != expected {digest}")


def install(conn: psycopg.Connection[Any]) -> None:
    """Create/verify the extension at the fixed version, the fixed text search configuration and the
    candidate B tables (idempotent). Must run as the superuser owner: it reads dictionary bytes."""
    conn.execute(f"create extension if not exists {EXTENSION} version '{EXPECTED_EXTENSION_VERSION}'")
    version = _extension_version(conn)
    if version != EXPECTED_EXTENSION_VERSION:
        raise InstallError(f"{EXTENSION} version {version} != expected {EXPECTED_EXTENSION_VERSION}")
    verify_dictionary_files(conn)
    exists = conn.execute("select 1 from pg_ts_config where cfgname = %s", (TS_CONFIG,)).fetchone()
    if exists is None:
        conn.execute(f"create text search configuration {TS_CONFIG} (parser = {EXTENSION})")
        conn.execute(
            f"alter text search configuration {TS_CONFIG} add mapping for {', '.join(MAPPED_TOKEN_TYPES)} with simple"
        )
    mapping = _mapping(conn)
    expected = [(t, 1, "simple") for t in MAPPED_TOKEN_TYPES]
    if mapping != expected:
        raise InstallError(f"text search configuration {TS_CONFIG} mapping {mapping} != fixed {expected}")
    conn.execute(INSTALL_SQL)


def runtime_tokenizer_version(conn: psycopg.Connection[Any]) -> str:
    """Live identity of the database-side tokenizer, readable by the ordinary role."""
    conn.execute(f"select to_tsvector('{TS_CONFIG}', 'x')")  # loads the parser library so its GUCs are visible
    version = _extension_version(conn)
    if version is None:
        raise InstallError(f"{EXTENSION} is not installed in this database")
    mapping = _mapping(conn)
    gucs = conn.execute(
        "select name, setting from pg_settings where name like %s order by name", (f"{EXTENSION}.%",)
    ).fetchall()
    map_hash = hashlib.sha256(json.dumps(mapping).encode()).hexdigest()[:8]
    guc_hash = hashlib.sha256(json.dumps([(str(n), str(s)) for n, s in gucs]).encode()).hexdigest()[:8]
    return f"{EXTENSION}-{version}+scws-{SCWS_VERSION}+cfg-{TS_CONFIG}:{map_hash}+guc:{guc_hash}"


def configured_versions(
    conn: psycopg.Connection[Any], *, dictionary_version: str = DICTIONARY_VERSION
) -> LexicalVersions:
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=runtime_tokenizer_version(conn),
        dictionary_version=dictionary_version,
        normalization_version=NORMALIZATION_VERSION,
    )


def query_tokens(conn: psycopg.Connection[Any], text: str) -> list[str]:
    """norm-v1, then the database tokenizer; distinct lexemes with punctuation-only ones dropped."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    row = conn.execute(f"select tsvector_to_array(to_tsvector('{TS_CONFIG}', %s))", (normalized,)).fetchone()
    lexemes = [] if row is None else [str(t) for t in row[0]]
    return [t for t in lexemes if not _PUNCT_ONLY.match(t)]


def build_index(conn: psycopg.Connection[Any], *, built_by: str) -> IndexBuildReport:
    """(Re)build `lexical_index_b` over every chunk visible to the connection's role, tokenizing in SQL.
    All-or-nothing in one transaction; chunks whose tsvector is empty are skipped and counted."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    with conn.transaction():
        versions = configured_versions(conn)
        conn.execute(f"delete from {INDEX_TABLE}")
        total = int(conn.execute("select count(*) from chunks").fetchone()[0])  # type: ignore[index]
        cur = conn.execute(
            f"insert into {INDEX_TABLE} (chunk_id, tsv) "
            f"select chunk_id, tsv from (select chunk_id, to_tsvector('{TS_CONFIG}', content) as tsv from chunks) s "
            f"where tsv <> ''::tsvector"
        )
        count = cur.rowcount
        upsert_meta(conn, INDEX_NAME, versions, chunk_count=count, built_by=built_by)
    return IndexBuildReport(index_name=INDEX_NAME, chunk_count=count, skipped_empty=total - count, versions=versions)


# ------------------------------------------------------------------------------- retriever


class PgZhparserFtsRetriever:
    """`LexicalRetriever` over an ORDINARY-ROLE connection; same transaction/identity rules as candidate A.
    `dictionary_version` is the operator-declared pin (verified by `install()`); a different declaration
    is a version drift and is refused against an index built with the fixed one."""

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

    def search(self, query: str, k: int) -> LexicalSearchResult:
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        tokens = query_tokens(self._conn, query)
        if not tokens:
            return empty_result(k, built)
        rows = self._conn.execute(SEARCH_SQL, search_params(tokens, k, self._as_of)).fetchall()
        return page_to_result(rows, k, built)

    def explain(self, query: str, k: int) -> str:
        require_identity(self._conn)
        tokens = query_tokens(self._conn, query)
        if not tokens:
            return ""
        return explain_json(self._conn, SEARCH_SQL, search_params(tokens, k, self._as_of))


# ------------------------------------------------------------------------------- CLI


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-001 candidate B: install configuration/tables, build the index")
    parser.add_argument("action", choices=("install", "build"))
    parser.add_argument("--admin-url", help="superuser DSN of the candidate B server (default: $DEC001_B_ADMIN_URL)")
    parser.add_argument("--built-by", default="dec001-b-build")
    args = parser.parse_args(argv)
    dsn = args.admin_url or os.environ.get("DEC001_B_ADMIN_URL")
    if not dsn:
        parser.error("--admin-url or DEC001_B_ADMIN_URL is required (candidate B runs on its own server)")
    with psycopg.connect(dsn) as conn:
        if args.action == "install":
            install(conn)
            conn.commit()
            print(json.dumps({"installed": [META_TABLE, INDEX_TABLE, TS_CONFIG]}))
            return 0
        report = build_index(conn, built_by=args.built_by)
        print(json.dumps(report.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
