"""Production lookups for Skills: both run inside the caller's identity-bound transaction (RLS), so a chunk or
document the caller may not see is simply absent, never an error the Skill could act on."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import date
from typing import Any

from medops.domain.common import DocType
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.retrieval.recheck import recheck_candidates

ConnForUser = Callable[[UserContext], AbstractContextManager[Any]]

_DOC_TYPE_SQL = "select doc_id::text, doc_type::text from documents where doc_id = any(%(ids)s::uuid[])"


def _uuids(ids: Sequence[str]) -> list[str]:
    out: list[str] = []
    for value in ids:
        try:
            out.append(str(uuid.UUID(value)))
        except (ValueError, AttributeError, TypeError):
            continue  # not a chunk id at all: reported by the skill as unknown
    return out


def evidence_lookup(conn_for_user: ConnForUser, *, as_of: date | None = None) -> Callable[..., tuple[Evidence, ...]]:
    def lookup(user: UserContext, chunk_ids: Sequence[str]) -> tuple[Evidence, ...]:
        ids = _uuids(chunk_ids)
        if not ids:
            return ()
        with conn_for_user(user) as conn:
            return tuple(recheck_candidates(conn, ids, as_of=as_of).evidence)

    return lookup


def doc_type_lookup(conn_for_user: ConnForUser) -> Callable[..., dict[str, DocType]]:
    def lookup(user: UserContext, doc_ids: Sequence[str]) -> dict[str, DocType]:
        ids = _uuids(doc_ids)
        if not ids:
            return {}
        with conn_for_user(user) as conn:
            rows = conn.execute(_DOC_TYPE_SQL, {"ids": ids}).fetchall()
        return {doc_id: DocType(doc_type) for doc_id, doc_type in rows}

    return lookup
