"""Department read-ACL changes on published documents (M3-03 admin action, DEC-012): grant / revoke rows in
`document_acl`, an explicit `doc_audit` row per change (the status trigger does not see ACL rows) and one
`document_acl_changed` outbox event so the retrieval cache epoch of every department involved is bumped
(record 74; closes the M1-19 note about ACL-only changes)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from medops.ingestion import outbox


class AclChangeRefused(ValueError):
    """Nothing was changed."""


@dataclass(frozen=True)
class AclChange:
    document_key: str
    doc_id: str
    granted: tuple[str, ...]
    revoked: tuple[str, ...]
    read_depts: tuple[str, ...]  # after the change
    event_id: int | None


def change_acl(
    conn: psycopg.Connection[Any],
    document_key: str,
    *,
    grant: Sequence[str],
    revoke: Sequence[str],
    actor: str,
    reason: str,
) -> AclChange:
    if not actor or not reason:
        raise AclChangeRefused("actor and reason are required (audit)")
    grant_set, revoke_set = {d for d in grant}, {d for d in revoke}
    if grant_set & revoke_set:
        raise AclChangeRefused(
            f"a department cannot be granted and revoked in one change: {sorted(grant_set & revoke_set)}"
        )
    if not grant_set and not revoke_set:
        raise AclChangeRefused("nothing to change")
    with conn.transaction():
        row = conn.execute(
            "select doc_id, family_id, status::text, owner_dept::text from documents where document_key = %s for update",
            (document_key,),
        ).fetchone()
        if row is None:
            raise AclChangeRefused(f"{document_key}: unknown document_key")
        doc_id, family_id, status, owner = row
        if status == "withdrawn":
            raise AclChangeRefused(f"{document_key}: withdrawn documents are read-only")
        if owner in revoke_set:
            raise AclChangeRefused(f"{document_key}: the owner department {owner} keeps read access")
        before = {
            r[0]
            for r in conn.execute(
                "select dept::text from document_acl where doc_id = %s and permission = 'read'", (doc_id,)
            )
        }
        granted = tuple(sorted(grant_set - before))
        revoked = tuple(sorted(revoke_set & before))
        for dept in granted:
            conn.execute(
                "insert into document_acl (doc_id, dept, permission, granted_by) values (%s, %s, 'read', %s)",
                (doc_id, dept, actor),
            )
            conn.execute(
                "insert into doc_audit (doc_id, action, actor, reason, details) values (%s, 'acl_grant', %s, %s, %s)",
                (doc_id, actor, reason, Jsonb({"dept": dept, "permission": "read"})),
            )
        for dept in revoked:
            conn.execute(
                "delete from document_acl where doc_id = %s and dept = %s and permission = 'read'", (doc_id, dept)
            )
            conn.execute(
                "insert into doc_audit (doc_id, action, actor, reason, details) values (%s, 'acl_revoke', %s, %s, %s)",
                (doc_id, actor, reason, Jsonb({"dept": dept, "permission": "read"})),
            )
        after = tuple(sorted((before | set(granted)) - set(revoked)))
        event_id = None
        if granted or revoked:
            involved = sorted(before | set(after) | {owner})
            event_id = outbox.emit(
                conn,
                "document_acl_changed",
                aggregate_id=doc_id,
                family_id=family_id,
                payload={
                    "doc_id": str(doc_id),
                    "family_id": str(family_id),
                    "document_key": document_key,
                    "owner_dept": owner,
                    "acl_depts": involved,  # every department whose cache may hold or now lacks this document
                    "granted": list(granted),
                    "revoked": list(revoked),
                    "reason": reason,
                },
                actor=actor,
            )
    return AclChange(document_key, str(doc_id), granted, revoked, after, event_id)
