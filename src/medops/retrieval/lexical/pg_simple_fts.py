"""ADR-0002 candidate A: application-side pretokenization + PostgreSQL `simple` FTS.

DEC-001 experiment adapter, not a selected production engine. The tokenizer (`tok-jieba-v1`,
norm-v1 first) runs on both the index and the query side; its output is written as a
POSITION-PRESERVING `tsvector` literal (baseline 3.6), never re-parsed by a text search parser,
so index lexemes and query lexemes are exactly the tokenizer's tokens.

Fixed recipe (any change is a new RETRIEVER_VERSION):
- matching predicate: OR across the distinct query tokens (experiment_plan `matching_predicate`);
- ranking: `ts_rank_cd(tsv, query, 0)` descending, ties broken by `chunk_id` ascending (3.7);
- database-side filtering only: RLS of the ordinary role on `lexical_index_a -> chunks -> documents`
  plus `documents.status = 'active'` and the effective window at `as_of` (3.7);
- exact candidate count and the ranked page come from ONE statement over the SAME predicate and
  filters, so `candidate_exhausted` is proven, never inferred (hard gate 4).

Schema: `lexical_index_meta` (one row per index: the versions it was built with) and
`lexical_index_a` (chunk_id -> tsv). Both are created by `install()` under the admin connection,
enabled with FORCE ROW LEVEL SECURITY and readable by the app/readonly roles only through the
`chunks` policy. They are deliberately NOT an Alembic revision: no production lexical engine has been
chosen, so candidate tables stay experiment-scoped until DEC-001 is decided.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg.pq import TransactionStatus

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.contracts import LexicalCandidate, LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, Tokenizer

RETRIEVER_VERSION = "pg-simple-fts-v1"
INDEX_NAME = "a"
INDEX_TABLE = "lexical_index_a"
META_TABLE = "lexical_index_meta"
MAX_POSITION = 16383  # tsvector positions above this are clamped by PostgreSQL; we clamp explicitly
MAX_POSITIONS_PER_LEXEME = 256  # PostgreSQL keeps at most 256 positions per lexeme
MAX_LEXEME_BYTES = 2046  # tsvector lexeme limit (2047 including terminator)

INSTALL_SQL = f"""
create table if not exists {META_TABLE} (
    index_name            text primary key,
    retriever_version     text not null,
    tokenizer_version     text not null,
    dictionary_version    text not null,
    normalization_version text not null,
    chunk_count           integer not null check (chunk_count >= 0),
    built_by              text not null,
    built_at              timestamptz not null default now()
);
create table if not exists {INDEX_TABLE} (
    chunk_id uuid primary key references chunks (chunk_id) on delete cascade,
    tsv      tsvector not null
);
create index if not exists {INDEX_TABLE}_tsv_gin on {INDEX_TABLE} using gin (tsv);

alter table {META_TABLE} enable row level security;
alter table {META_TABLE} force row level security;
alter table {INDEX_TABLE} enable row level security;
alter table {INDEX_TABLE} force row level security;

drop policy if exists {META_TABLE}_read on {META_TABLE};
create policy {META_TABLE}_read on {META_TABLE} for select to medops_app, medops_readonly using (true);
drop policy if exists {META_TABLE}_admin_all on {META_TABLE};
create policy {META_TABLE}_admin_all on {META_TABLE} for all to medops_admin_role using (true) with check (true);
drop policy if exists {INDEX_TABLE}_via_chunk on {INDEX_TABLE};
create policy {INDEX_TABLE}_via_chunk on {INDEX_TABLE} for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = {INDEX_TABLE}.chunk_id));
drop policy if exists {INDEX_TABLE}_admin_all on {INDEX_TABLE};
create policy {INDEX_TABLE}_admin_all on {INDEX_TABLE} for all to medops_admin_role using (true) with check (true);

grant select on {META_TABLE}, {INDEX_TABLE} to medops_app, medops_readonly;
grant select, insert, update, delete on {META_TABLE}, {INDEX_TABLE} to medops_admin_role;
"""

SEARCH_SQL = f"""
with eligible as (
    select i.chunk_id, ts_rank_cd(i.tsv, %(q)s::tsquery, 0) as score
    from {INDEX_TABLE} i
    join chunks c on c.chunk_id = i.chunk_id
    join documents d on d.doc_id = c.doc_id
    where i.tsv @@ %(q)s::tsquery
      and d.status = 'active'
      and d.effective_from <= %(as_of)s
      and (d.effective_to is null or d.effective_to > %(as_of)s)
)
select chunk_id, score, count(*) over () as eligible_count
from eligible
order by score desc, chunk_id asc
limit %(k)s
"""


# ------------------------------------------------------------------------------- literals


def _quote_lexeme(token: str) -> str:
    """tsvector/tsquery lexeme literal: single-quoted, `'` doubled, `\\` doubled."""
    if not token:
        raise ValueError("empty token")
    if len(token.encode("utf-8")) > MAX_LEXEME_BYTES:
        raise ValueError("token exceeds the tsvector lexeme limit")
    return "'" + token.replace("\\", "\\\\").replace("'", "''") + "'"


def tsvector_literal(tokens: Sequence[str]) -> str:
    """Position-preserving tsvector text for `tokens` (position = 1-based token index).

    Lexemes are emitted in first-occurrence order (PostgreSQL normalizes the order on input),
    positions are clamped to MAX_POSITION and truncated to MAX_POSITIONS_PER_LEXEME like the server
    would do, so the literal is what the server stores. Empty token lists produce an empty tsvector."""
    positions: dict[str, list[int]] = {}
    for index, token in enumerate(tokens, start=1):
        positions.setdefault(token, []).append(min(index, MAX_POSITION))
    parts = []
    for token, pos in positions.items():
        kept = pos[:MAX_POSITIONS_PER_LEXEME]
        parts.append(_quote_lexeme(token) + ":" + ",".join(str(p) for p in kept))
    return " ".join(parts)


def tsquery_literal(tokens: Sequence[str]) -> str:
    """OR query over the distinct tokens, first-occurrence order. Empty -> ValueError (callers
    short-circuit to zero eligible candidates before building a query)."""
    distinct = list(dict.fromkeys(tokens))
    if not distinct:
        raise ValueError("no tokens")
    return " | ".join(_quote_lexeme(t) for t in distinct)


# ------------------------------------------------------------------------------- install / build


def install(conn: psycopg.Connection[Any]) -> None:
    """Create the candidate A tables, policies and grants (idempotent). Needs CREATE on schema public
    and must run as the migration/admin owner, never as an application role."""
    conn.execute(INSTALL_SQL)


@dataclass(frozen=True)
class IndexBuildReport:
    index_name: str
    chunk_count: int
    skipped_empty: int
    versions: LexicalVersions


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
        conn.execute(
            f"""insert into {META_TABLE} (index_name, retriever_version, tokenizer_version, dictionary_version,
                                          normalization_version, chunk_count, built_by, built_at)
                values (%s, %s, %s, %s, %s, %s, %s, now())
                on conflict (index_name) do update set
                    retriever_version = excluded.retriever_version, tokenizer_version = excluded.tokenizer_version,
                    dictionary_version = excluded.dictionary_version, normalization_version = excluded.normalization_version,
                    chunk_count = excluded.chunk_count, built_by = excluded.built_by, built_at = now()""",
            (
                INDEX_NAME,
                versions.retriever_version,
                versions.tokenizer_version,
                versions.dictionary_version,
                versions.normalization_version,
                count,
                built_by,
            ),
        )
    return IndexBuildReport(index_name=INDEX_NAME, chunk_count=count, skipped_empty=skipped, versions=versions)


def _flush(conn: psycopg.Connection[Any], rows: list[tuple[Any, str]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(f"insert into {INDEX_TABLE} (chunk_id, tsv) values (%s, %s::tsvector)", rows)
    return len(rows)


# ------------------------------------------------------------------------------- retriever


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
        row = self._conn.execute(
            f"select retriever_version, tokenizer_version, dictionary_version, normalization_version "
            f"from {META_TABLE} where index_name = %s",
            (INDEX_NAME,),
        ).fetchone()
        if row is None:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable,
                detail=f"lexical index '{INDEX_NAME}' has not been built (no {META_TABLE} row)",
                retryable=False,
            )
        return LexicalVersions(
            retriever_version=row[0], tokenizer_version=row[1], dictionary_version=row[2], normalization_version=row[3]
        )

    def _require_identity(self) -> str:
        if self._conn.info.transaction_status != TransactionStatus.INTRANS:
            raise BusinessError(
                ErrorCode.unauthenticated,
                "lexical search must run inside the request transaction that carries the department identity",
            )
        dept = self._conn.execute("select nullif(current_setting('medops.dept', true), '')").fetchone()
        if dept is None or dept[0] is None:
            raise BusinessError(ErrorCode.unauthenticated, "no department identity bound to this transaction")
        return str(dept[0])

    def _query_tokens(self, query: str) -> list[str]:
        return list(dict.fromkeys(self._tokenizer.tokenize(query)))

    def search(self, query: str, k: int) -> LexicalSearchResult:
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise BusinessError(ErrorCode.invalid_request, "k must be a positive integer")
        self._require_identity()
        built = self.versions
        if built != self.configured:
            raise BusinessError(
                ErrorCode.version_conflict,
                "lexical index and query tokenizer versions differ; rebuild the index or use the matching versions",
                detail=f"index={built.model_dump()} query={self.configured.model_dump()}",
            )
        tokens = self._query_tokens(query)
        candidates: list[LexicalCandidate] = []
        eligible = 0
        if tokens:
            rows = self._conn.execute(SEARCH_SQL, self._params(tokens, k)).fetchall()
            eligible = int(rows[0][2]) if rows else 0
            candidates = [
                LexicalCandidate(chunk_id=str(chunk_id), raw_score=float(score), rank=rank)
                for rank, (chunk_id, score, _) in enumerate(rows, start=1)
            ]
        if len(candidates) != min(eligible, k):
            raise InfrastructureError(
                ErrorCode.internal_error,
                detail=f"candidate page size {len(candidates)} != min(eligible={eligible}, k={k})",
                retryable=False,
            )
        return LexicalSearchResult(
            candidates=tuple(candidates),
            requested_k=k,
            returned_count=len(candidates),
            candidate_exhausted=eligible < k,
            retriever_version=built.retriever_version,
            tokenizer_version=built.tokenizer_version,
            dictionary_version=built.dictionary_version,
            normalization_version=built.normalization_version,
        )

    def _params(self, tokens: Sequence[str], k: int) -> dict[str, Any]:
        return {"q": tsquery_literal(tokens), "as_of": self._as_of or date.today(), "k": k}

    def explain(self, query: str, k: int) -> str:
        """`EXPLAIN (FORMAT JSON)` of the exact search statement under the current role and identity,
        for the execution-plan evidence ADR-0002 requires. Returns '' when the query has no tokens."""
        self._require_identity()
        tokens = self._query_tokens(query)
        if not tokens:
            return ""
        row = self._conn.execute("explain (format json) " + SEARCH_SQL, self._params(tokens, k)).fetchone()
        return json.dumps(row[0], ensure_ascii=False) if row else ""


# ------------------------------------------------------------------------------- CLI


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
        print(
            json.dumps(
                {
                    "index_name": report.index_name,
                    "chunk_count": report.chunk_count,
                    "skipped_empty": report.skipped_empty,
                    "versions": report.versions.model_dump(),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
