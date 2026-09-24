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
from dataclasses import dataclass
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

# Variant B2 (ADR-0002 amendment 2): same parser and POS mapping, but the lexemes go through a `simple`
# dictionary with PostgreSQL's English stopword list, so English function words are dropped on the index
# and query side alike. The stopword file bytes are verified by install() and pinned in dictionary_version.
STOPWORD_FILE = "/usr/share/postgresql/16/tsearch_data/english.stop"
STOPWORD_SHA256 = "b3f772a000465cb76e23adb03b47073c591c156fad8f7af09c8b8e80d6bd8eac"


@dataclass(frozen=True)
class ZhparserVariant:
    index_name: str
    table: str
    ts_config: str
    dictionary: str  # PostgreSQL text search dictionary the token types map to
    dictionary_version: str
    stopwords: bool

    @property
    def install_sql(self) -> str:
        return META_DDL + tsvector_index_ddl(self.table)

    @property
    def search_sql(self) -> str:
        return tsvector_search_sql(self.table)


VARIANT_B = ZhparserVariant("b", INDEX_TABLE, TS_CONFIG, "simple", DICTIONARY_VERSION, False)
VARIANT_B2 = ZhparserVariant(
    "b2",
    "lexical_index_b2",
    "dec001_b2",
    "dec001_simple_en_stop",
    DICTIONARY_VERSION + "+stop-english:" + STOPWORD_SHA256[:16],
    True,
)
VARIANTS = {"b": VARIANT_B, "b2": VARIANT_B2}
_PUNCT_ONLY = re.compile(r"^[\W_]+$")


class InstallError(RuntimeError):
    """The server does not match the fixed candidate B identity (extension, mapping or dictionary bytes)."""


# ------------------------------------------------------------------------------- install / identity


def _extension_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("select extversion from pg_extension where extname = %s", (EXTENSION,)).fetchone()
    return None if row is None else str(row[0])


def _mapping(conn: psycopg.Connection[Any], ts_config: str = TS_CONFIG) -> list[tuple[str, int, str]]:
    rows = conn.execute(
        "select chr(maptokentype), mapseqno, mapdict::regdictionary::text from pg_ts_config_map "
        "where mapcfg = %s::regconfig order by maptokentype, mapseqno",
        (ts_config,),
    ).fetchall()
    return [(str(t), int(n), str(d)) for t, n, d in rows]


def verify_dictionary_files(conn: psycopg.Connection[Any], expected: dict[str, str] | None = None) -> None:
    """Superuser-only byte check of the SCWS dictionary and rules inside the image."""
    for path, digest in (expected or DICTIONARY_FILES).items():
        row = conn.execute("select encode(sha256(pg_read_binary_file(%s)), 'hex')", (path,)).fetchone()
        actual = None if row is None else str(row[0])
        if actual != digest:
            raise InstallError(f"dictionary file {path} sha256 {actual} != expected {digest}")


def install(conn: psycopg.Connection[Any], variant: ZhparserVariant = VARIANT_B) -> None:
    """Create/verify the extension at the fixed version, the fixed text search configuration and the
    candidate B tables (idempotent). Must run as the superuser owner: it reads dictionary bytes."""
    conn.execute(f"create extension if not exists {EXTENSION} version '{EXPECTED_EXTENSION_VERSION}'")
    version = _extension_version(conn)
    if version != EXPECTED_EXTENSION_VERSION:
        raise InstallError(f"{EXTENSION} version {version} != expected {EXPECTED_EXTENSION_VERSION}")
    verify_dictionary_files(conn)
    if variant.stopwords:
        verify_dictionary_files(conn, {STOPWORD_FILE: STOPWORD_SHA256})
        if conn.execute("select 1 from pg_ts_dict where dictname = %s", (variant.dictionary,)).fetchone() is None:
            conn.execute(f"create text search dictionary {variant.dictionary} (template = simple, stopwords = english)")
    exists = conn.execute("select 1 from pg_ts_config where cfgname = %s", (variant.ts_config,)).fetchone()
    if exists is None:
        conn.execute(f"create text search configuration {variant.ts_config} (parser = {EXTENSION})")
        conn.execute(
            f"alter text search configuration {variant.ts_config} add mapping for {', '.join(MAPPED_TOKEN_TYPES)} "
            f"with {variant.dictionary}"
        )
    mapping = _mapping(conn, variant.ts_config)
    expected = [(t, 1, variant.dictionary) for t in MAPPED_TOKEN_TYPES]
    if mapping != expected:
        raise InstallError(f"text search configuration {variant.ts_config} mapping {mapping} != fixed {expected}")
    conn.execute(variant.install_sql)


def runtime_tokenizer_version(conn: psycopg.Connection[Any], ts_config: str = TS_CONFIG) -> str:
    """Live identity of the database-side tokenizer, readable by the ordinary role."""
    conn.execute(f"select to_tsvector('{ts_config}', 'x')")  # loads the parser library so its GUCs are visible
    version = _extension_version(conn)
    if version is None:
        raise InstallError(f"{EXTENSION} is not installed in this database")
    mapping = _mapping(conn, ts_config)
    gucs = conn.execute(
        "select name, setting from pg_settings where name like %s order by name", (f"{EXTENSION}.%",)
    ).fetchall()
    map_hash = hashlib.sha256(json.dumps(mapping).encode()).hexdigest()[:8]
    guc_hash = hashlib.sha256(json.dumps([(str(n), str(s)) for n, s in gucs]).encode()).hexdigest()[:8]
    return f"{EXTENSION}-{version}+scws-{SCWS_VERSION}+cfg-{ts_config}:{map_hash}+guc:{guc_hash}"


def configured_versions(
    conn: psycopg.Connection[Any],
    *,
    dictionary_version: str = DICTIONARY_VERSION,
    variant: ZhparserVariant = VARIANT_B,
) -> LexicalVersions:
    return LexicalVersions(
        retriever_version=RETRIEVER_VERSION,
        tokenizer_version=runtime_tokenizer_version(conn, variant.ts_config),
        dictionary_version=dictionary_version,
        normalization_version=NORMALIZATION_VERSION,
    )


def query_tokens(conn: psycopg.Connection[Any], text: str, ts_config: str = TS_CONFIG) -> list[str]:
    """norm-v1, then the database tokenizer; distinct lexemes with punctuation-only ones dropped."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    row = conn.execute(f"select tsvector_to_array(to_tsvector('{ts_config}', %s))", (normalized,)).fetchone()
    lexemes = [] if row is None else [str(t) for t in row[0]]
    return [t for t in lexemes if not _PUNCT_ONLY.match(t)]


def build_index(
    conn: psycopg.Connection[Any], *, built_by: str, variant: ZhparserVariant = VARIANT_B
) -> IndexBuildReport:
    """(Re)build the variant's index table over every chunk visible to the connection's role, tokenizing in
    SQL. All-or-nothing in one transaction; chunks whose tsvector is empty are skipped and counted."""
    if not built_by:
        raise ValueError("built_by is required (audit)")
    with conn.transaction():
        versions = configured_versions(conn, dictionary_version=variant.dictionary_version, variant=variant)
        conn.execute(f"delete from {variant.table}")
        total = int(conn.execute("select count(*) from chunks").fetchone()[0])  # type: ignore[index]
        cur = conn.execute(
            f"insert into {variant.table} (chunk_id, tsv) "
            f"select chunk_id, tsv from (select chunk_id, to_tsvector('{variant.ts_config}', content) as tsv from chunks) s "
            f"where tsv <> ''::tsvector"
        )
        count = cur.rowcount
        upsert_meta(conn, variant.index_name, versions, chunk_count=count, built_by=built_by)
    return IndexBuildReport(
        index_name=variant.index_name, chunk_count=count, skipped_empty=total - count, versions=versions
    )


# ------------------------------------------------------------------------------- retriever


class PgZhparserFtsRetriever:
    """`LexicalRetriever` over an ORDINARY-ROLE connection; same transaction/identity rules as candidate A.
    `dictionary_version` is the operator-declared pin (verified by `install()`); a different declaration
    is a version drift and is refused against an index built with the fixed one."""

    def __init__(
        self,
        conn: psycopg.Connection[Any],
        *,
        as_of: date | None = None,
        dictionary_version: str | None = None,
        variant: ZhparserVariant = VARIANT_B,
    ) -> None:
        self._conn = conn
        self._as_of = as_of
        self._variant = variant
        self._dictionary_version = dictionary_version or variant.dictionary_version

    @property
    def configured(self) -> LexicalVersions:
        return configured_versions(self._conn, dictionary_version=self._dictionary_version, variant=self._variant)

    @property
    def versions(self) -> LexicalVersions:
        return read_built_versions(self._conn, self._variant.index_name)

    def search(self, query: str, k: int, *, allow_historical: bool = False) -> LexicalSearchResult:
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        check_versions_match(built, self.configured)
        tokens = query_tokens(self._conn, query, self._variant.ts_config)
        if not tokens:
            return empty_result(k, built)
        rows = self._conn.execute(
            self._variant.search_sql, search_params(tokens, k, self._as_of, allow_historical=allow_historical)
        ).fetchall()
        return page_to_result(rows, k, built)

    def explain(self, query: str, k: int, *, allow_historical: bool = False) -> str:
        require_identity(self._conn)
        tokens = query_tokens(self._conn, query, self._variant.ts_config)
        if not tokens:
            return ""
        return explain_json(
            self._conn,
            self._variant.search_sql,
            search_params(tokens, k, self._as_of, allow_historical=allow_historical),
        )


# ------------------------------------------------------------------------------- CLI


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-001 candidate B: install configuration/tables, build the index")
    parser.add_argument("action", choices=("install", "build"))
    parser.add_argument("--admin-url", help="superuser DSN of the candidate B server (default: $DEC001_B_ADMIN_URL)")
    parser.add_argument("--built-by", default="dec001-b-build")
    parser.add_argument(
        "--variant", choices=tuple(VARIANTS), default="b", help="b2 = English stopwords via a simple dictionary"
    )
    args = parser.parse_args(argv)
    variant = VARIANTS[args.variant]
    dsn = args.admin_url or os.environ.get("DEC001_B_ADMIN_URL")
    if not dsn:
        parser.error("--admin-url or DEC001_B_ADMIN_URL is required (candidate B runs on its own server)")
    with psycopg.connect(dsn) as conn:
        if args.action == "install":
            install(conn, variant)
            conn.commit()
            print(json.dumps({"installed": [META_TABLE, variant.table, variant.ts_config, variant.dictionary]}))
            return 0
        report = build_index(conn, built_by=args.built_by, variant=variant)
        print(json.dumps(report.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
