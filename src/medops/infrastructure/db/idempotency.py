"""Generic receipt-bearing idempotency (baseline 3.2) for routes whose result is a small JSON document rather than
a task: scope = principal + route + key, canonical request hash, receipt stored in `idempotency_keys.receipt`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb


class PgReceiptStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def find(self, principal: str, route: str, key: str) -> tuple[str, Mapping[str, Any]] | None:
        row = self._conn.execute(
            "select request_hash, receipt from idempotency_keys where principal = %s and route = %s and key = %s "
            "and expires_at > now() and receipt is not null",
            (principal, route, key),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def put(
        self, principal: str, route: str, key: str, request_hash: str, receipt: Mapping[str, Any], expires_at: datetime
    ) -> None:
        self._conn.execute(
            "insert into idempotency_keys (principal, route, key, request_hash, receipt, expires_at) values (%s, %s, %s, %s, %s, %s)",
            (principal, route, key, request_hash, Jsonb(dict(receipt)), expires_at),
        )
