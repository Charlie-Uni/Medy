"""BM25 SQL/paging mechanics shared by the production and experiment adapters.

Each adapter still owns its table layout, authorization, version identity, pinned
parameters and install/build rules. Sharing a query recipe does not approve a
global experimental corpus for production.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Any

import psycopg

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("BM25 table/index must be a fixed SQL identifier")
    return value


def bm25_search_sql(table: str, index: str) -> str:
    table, index = _identifier(table), _identifier(index)
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


def bm25_params(
    query: str, k: int, as_of: date | None, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
) -> dict[str, Any]:
    return {
        "q": query,
        "as_of": as_of or date.today(),
        "k_plus_one": k + 1,
        "allow_historical": bool(allow_historical),
        "doc_ids": list(doc_ids) if doc_ids else None,
    }


def bm25_page(rows: Sequence[tuple[Any, Any]], k: int) -> list[tuple[Any, Any, int]]:
    """k+1 fetch preserves the existing exact-short / at-least-k+1 exhaustion contract."""
    eligible = len(rows) if len(rows) <= k else k + 1
    return [(chunk_id, score, eligible) for chunk_id, score in rows[:k]]


def flush_text_rows(conn: psycopg.Connection[Any], table: str, rows: list[tuple[Any, str]]) -> int:
    table = _identifier(table)
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(f"insert into {table} (chunk_id, content) values (%s, %s)", rows)
    return len(rows)
