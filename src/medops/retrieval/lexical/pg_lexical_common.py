"""Shared pieces of the PostgreSQL lexical candidates (ADR-0002 A and B; C reuses the identity, meta
and result helpers). Everything here is experiment-scoped: candidate tables are installed by the admin
connection, not by an Alembic revision, until DEC-001 is decided.

Fixed recipe shared by the tsvector-based candidates (any change is a new retriever version):
- matching predicate: OR across the distinct query lexemes;
- ranking: `ts_rank_cd(tsv, query, 0)` descending, ties broken by `chunk_id` ascending (baseline 3.7);
- filtering only inside the query: the RLS chain `index -> chunks -> documents -> document_acl` of the
  ordinary role plus `documents.status = 'active'` and the effective window at `as_of`;
- exact candidate count and the ranked page come from ONE statement over the SAME predicate and
  filters (`count(*) over ()`), so `candidate_exhausted` is proven, never inferred (hard gate 4).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg.pq import TransactionStatus

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.contracts import LexicalCandidate, LexicalSearchResult, LexicalVersions

META_TABLE = "lexical_index_meta"
MAX_POSITION = 16383  # tsvector positions above this are clamped by PostgreSQL; we clamp explicitly
MAX_POSITIONS_PER_LEXEME = 256  # PostgreSQL keeps at most 256 positions per lexeme
MAX_LEXEME_BYTES = 2046  # tsvector lexeme limit (2047 including terminator)

META_DDL = f"""
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
alter table {META_TABLE} enable row level security;
alter table {META_TABLE} force row level security;
drop policy if exists {META_TABLE}_read on {META_TABLE};
create policy {META_TABLE}_read on {META_TABLE} for select to medops_app, medops_readonly using (true);
drop policy if exists {META_TABLE}_admin_all on {META_TABLE};
create policy {META_TABLE}_admin_all on {META_TABLE} for all to medops_admin_role using (true) with check (true);
grant select on {META_TABLE} to medops_app, medops_readonly;
grant select, insert, update, delete on {META_TABLE} to medops_admin_role;
"""


def tsvector_index_ddl(table: str) -> str:
    """A `chunk_id -> tsv` index table with GIN, FORCE RLS, read access only through the `chunks`
    policy for the ordinary roles and full access for the admin role."""
    return f"""
create table if not exists {table} (
    chunk_id uuid primary key references chunks (chunk_id) on delete cascade,
    tsv      tsvector not null
);
create index if not exists {table}_tsv_gin on {table} using gin (tsv);
alter table {table} enable row level security;
alter table {table} force row level security;
drop policy if exists {table}_via_chunk on {table};
create policy {table}_via_chunk on {table} for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = {table}.chunk_id));
drop policy if exists {table}_admin_all on {table};
create policy {table}_admin_all on {table} for all to medops_admin_role using (true) with check (true);
grant select on {table} to medops_app, medops_readonly;
grant select, insert, update, delete on {table} to medops_admin_role;
"""


def text_index_ddl(table: str) -> str:
    """A `chunk_id -> content` table for engines that index text themselves (candidate C's bm25 index is
    created by its own module); FORCE RLS and grants identical to the tsvector tables."""
    return f"""
create table if not exists {table} (
    chunk_id uuid primary key references chunks (chunk_id) on delete cascade,
    content  text not null
);
alter table {table} enable row level security;
alter table {table} force row level security;
drop policy if exists {table}_via_chunk on {table};
create policy {table}_via_chunk on {table} for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = {table}.chunk_id));
drop policy if exists {table}_admin_all on {table};
create policy {table}_admin_all on {table} for all to medops_admin_role using (true) with check (true);
grant select on {table} to medops_app, medops_readonly;
grant select, insert, update, delete on {table} to medops_admin_role;
"""


def tsvector_search_sql(table: str) -> str:
    return f"""
with eligible as (
    select i.chunk_id, ts_rank_cd(i.tsv, %(q)s::tsquery, 0) as score
    from {table} i
    join chunks c on c.chunk_id = i.chunk_id
    join documents d on d.doc_id = c.doc_id
    where i.tsv @@ %(q)s::tsquery
      and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
      and d.effective_from <= %(as_of)s
      and (d.effective_to is null or d.effective_to > %(as_of)s)
)
select chunk_id, score, count(*) over () as eligible_count
from eligible
order by score desc, chunk_id asc
limit %(k)s
"""


# ------------------------------------------------------------------------------- literals


def quote_lexeme(token: str) -> str:
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
        parts.append(quote_lexeme(token) + ":" + ",".join(str(p) for p in kept))
    return " ".join(parts)


def tsquery_literal(tokens: Sequence[str]) -> str:
    """OR query over the distinct tokens, first-occurrence order. Empty -> ValueError (callers
    short-circuit to zero eligible candidates before building a query)."""
    distinct = list(dict.fromkeys(tokens))
    if not distinct:
        raise ValueError("no tokens")
    return " | ".join(quote_lexeme(t) for t in distinct)


# ------------------------------------------------------------------------------- build report


@dataclass(frozen=True)
class IndexBuildReport:
    index_name: str
    chunk_count: int
    skipped_empty: int
    versions: LexicalVersions

    def as_dict(self) -> dict[str, Any]:
        return {
            "index_name": self.index_name,
            "chunk_count": self.chunk_count,
            "skipped_empty": self.skipped_empty,
            "versions": self.versions.model_dump(),
        }


# ------------------------------------------------------------------------------- identity / meta


def require_identity(conn: psycopg.Connection[Any]) -> str:
    """The department bound to the current transaction. Refuses (identity error) without an open
    transaction or without `medops.dept`, instead of letting RLS return an empty, misleadingly
    "exhausted" page."""
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise BusinessError(
            ErrorCode.unauthenticated,
            "lexical search must run inside the request transaction that carries the department identity",
        )
    dept = conn.execute("select nullif(current_setting('medops.dept', true), '')").fetchone()
    if dept is None or dept[0] is None:
        raise BusinessError(ErrorCode.unauthenticated, "no department identity bound to this transaction")
    return str(dept[0])


def read_built_versions(conn: psycopg.Connection[Any], index_name: str) -> LexicalVersions:
    row = conn.execute(
        f"select retriever_version, tokenizer_version, dictionary_version, normalization_version "
        f"from {META_TABLE} where index_name = %s",
        (index_name,),
    ).fetchone()
    if row is None:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable,
            detail=f"lexical index '{index_name}' has not been built (no {META_TABLE} row)",
            retryable=False,
        )
    return LexicalVersions(
        retriever_version=row[0], tokenizer_version=row[1], dictionary_version=row[2], normalization_version=row[3]
    )


def upsert_meta(
    conn: psycopg.Connection[Any], index_name: str, versions: LexicalVersions, *, chunk_count: int, built_by: str
) -> None:
    conn.execute(
        f"""insert into {META_TABLE} (index_name, retriever_version, tokenizer_version, dictionary_version,
                                      normalization_version, chunk_count, built_by, built_at)
            values (%s, %s, %s, %s, %s, %s, %s, now())
            on conflict (index_name) do update set
                retriever_version = excluded.retriever_version, tokenizer_version = excluded.tokenizer_version,
                dictionary_version = excluded.dictionary_version, normalization_version = excluded.normalization_version,
                chunk_count = excluded.chunk_count, built_by = excluded.built_by, built_at = now()""",
        (
            index_name,
            versions.retriever_version,
            versions.tokenizer_version,
            versions.dictionary_version,
            versions.normalization_version,
            chunk_count,
            built_by,
        ),
    )


def check_versions_match(built: LexicalVersions, configured: LexicalVersions) -> None:
    if built != configured:
        raise BusinessError(
            ErrorCode.version_conflict,
            "lexical index and query tokenizer versions differ; rebuild the index or use the matching versions",
            detail=f"index={built.model_dump()} query={configured.model_dump()}",
        )


# ------------------------------------------------------------------------------- results


def check_k(k: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise BusinessError(ErrorCode.invalid_request, "k must be a positive integer")


def page_to_result(rows: Sequence[tuple[Any, Any, Any]], k: int, built: LexicalVersions) -> LexicalSearchResult:
    """Rows are `(chunk_id, score, eligible_count)` from a single count-and-page statement. The page must
    be exactly `min(eligible, k)` long; anything else is an adapter or planner defect and fails closed."""
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


def empty_result(k: int, built: LexicalVersions) -> LexicalSearchResult:
    return page_to_result([], k, built)


def search_params(
    tokens: Sequence[str], k: int, as_of: date | None, *, allow_historical: bool = False
) -> dict[str, Any]:
    """`allow_historical` admits archived versions whose effective window contains `as_of` (INV-DATA-03: only an
    explicit historical request may see them; the re-check then marks such evidence `historical`)."""
    return {
        "q": tsquery_literal(tokens),
        "as_of": as_of or date.today(),
        "k": k,
        "allow_historical": bool(allow_historical),
    }


def explain_json(conn: psycopg.Connection[Any], sql: str, params: dict[str, Any]) -> str:
    row = conn.execute("explain (format json) " + sql, params).fetchone()
    return json.dumps(row[0], ensure_ascii=False) if row else ""
