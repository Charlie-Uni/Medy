"""Shared payloads test support; no collected test cases."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from medops.core.envelope import StaticKeyProvider

PROVIDER = StaticKeyProvider({"k1": secrets.token_bytes(32)}, "k1")


class MemoryPayloads:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.access: list[tuple[str, str, str]] = []

    def put(self, trace_id, node, kind, sealed, expires_at):
        self.rows.append(
            {
                "payload_id": str(len(self.rows)),
                "trace_id": trace_id,
                "node": node,
                "kind": kind,
                "sealed": sealed,
                "created_at": datetime.now(UTC),
                "expires_at": expires_at,
            }
        )
        return str(len(self.rows))

    def list(self, trace_id):
        return [r for r in self.rows if r["trace_id"] == trace_id]

    def log_access(self, principal, trace_id, purpose):
        self.access.append((principal, trace_id, purpose))

    def purge(self, now, *, escalation_grace_days):
        return 0
