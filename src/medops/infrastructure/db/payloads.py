"""Restricted payload rows (migration 0015): the application role inserts inside the request transaction, the
restricted role reads, logs access and purges (DEC-013 retention)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from medops.core.envelope import Sealed


class PgPayloadStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def put(self, trace_id: str, node: str, kind: str, sealed: Sealed, expires_at: datetime) -> str:
        pid = str(uuid.uuid4())
        self._conn.execute(
            "insert into trace_payloads (payload_id, trace_id, node, kind, ciphertext, nonce, dek_wrapped, kek_version, expires_at) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                pid,
                trace_id,
                node,
                kind,
                sealed.ciphertext,
                sealed.nonce,
                sealed.dek_wrapped,
                sealed.kek_version,
                expires_at,
            ),
        )
        return pid

    def list(self, trace_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "select payload_id::text, node, kind, ciphertext, nonce, dek_wrapped, kek_version, created_at, expires_at "
            "from trace_payloads where trace_id = %s order by created_at, node, kind",
            (trace_id,),
        ).fetchall()
        return [
            {
                "payload_id": r[0],
                "node": r[1],
                "kind": r[2],
                "sealed": Sealed(bytes(r[3]), bytes(r[4]), bytes(r[5]), r[6]),
                "created_at": r[7],
                "expires_at": r[8],
            }
            for r in rows
        ]

    def log_access(self, principal: str, trace_id: str, purpose: str) -> None:
        self._conn.execute(
            "insert into payload_access_log (trace_id, principal, purpose) values (%s, %s, %s)",
            (trace_id, principal, purpose),
        )

    def purge(self, now: datetime, *, escalation_grace_days: int) -> int:
        """Delete expired rows, except while the trace's escalation is still open / acknowledged, and for closed
        escalations only after `handled_at + grace`. Deleting the row discards its DEK (crypto-shredding)."""
        cur = self._conn.execute(
            """delete from trace_payloads p
               where p.expires_at < %(now)s
                 and not exists (select 1 from escalations e where e.trace_id = p.trace_id and e.status <> 'closed')
                 and not exists (
                     select 1 from escalations e where e.trace_id = p.trace_id and e.status = 'closed'
                       and e.handled_at is not null and e.handled_at + make_interval(days => %(grace)s) > %(now)s
                 )""",
            {"now": now, "grace": escalation_grace_days},
        )
        return cur.rowcount
