"""Bounded, optimistic-consistent read on the existing restricted role.

No runtime control object, impersonated owner, lease, call or write is created.
Immutable events plus a second manifest/head check establish a historical snapshot.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from medops.application.agent_audit import (
    MAX_AGENT_AUDIT_BYTES,
    MAX_AGENT_AUDIT_EVENTS,
    AgentAuditBundle,
    AgentAuditItem,
)
from medops.application.agent_runtime_envelope import head_aad, runtime_aad
from medops.core.envelope import Sealed
from medops.core.errors import BusinessError, ErrorCode
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.db.payloads import PgPayloadStore

_CONTROL = (
    "run_id",
    "case_id",
    "task_id",
    "attempt_id",
    "principal",
    "dept",
    "trace_id",
    "context_sha256",
    "started_at",
    "expires_at",
    "decisions_consumed",
    "lease_generation",
    "cancelled_at",
    "terminal_ref",
    "terminal_at",
    "terminal_status",
)
_HEAD = (
    "revision",
    "lease_id",
    "lease_generation",
    "budget_state",
    "budget_deadline",
    "retained_until",
    "updated_at",
    "bytes",
)


def _json_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v for k, v in data.items()
    }


class PgAgentAuditStore:
    def __init__(self, conn: Any):
        self.conn = DeadlineConnection(conn)

    def _head(self, run_id: UUID) -> tuple[Any, ...] | None:
        return self.conn.execute(
            "select " + ",".join("c." + n for n in _CONTROL) + ","
            "h.revision,h.lease_id,h.lease_generation,h.budget_state,h.budget_deadline,h.retained_until,h.updated_at,"
            "octet_length(h.ciphertext)+octet_length(h.dek_wrapped)+octet_length(h.nonce)+octet_length(h.kek_version)+octet_length(h.budget_state::text) "
            "from agent_run_control c join agent_runtime_heads h using(run_id) "
            "where c.run_id=%s and c.principal=h.principal and c.dept=h.dept and c.context_sha256=h.context_sha256 "
            "and h.retained_until>clock_timestamp()",
            (run_id,),
        ).fetchone()

    def _manifest(self, run_id: UUID) -> list[tuple[Any, ...]]:
        return self.conn.execute(
            "select event_id,kind,item_id,lease_id,lease_generation,created_at,retained_until,principal,dept,"
            "octet_length(ciphertext)+octet_length(dek_wrapped)+octet_length(nonce)+octet_length(kek_version) "
            "from agent_runtime_events where run_id=%s order by created_at,event_id limit %s",
            (run_id, MAX_AGENT_AUDIT_EVENTS + 1),
        ).fetchall()

    def load(self, run_id: UUID) -> AgentAuditBundle | None:
        original = self._head(run_id)
        if original is None:
            return None
        control = dict(zip(_CONTROL, original[: len(_CONTROL)], strict=True))
        head = dict(zip(_HEAD, original[len(_CONTROL) :], strict=True))
        manifest = self._manifest(run_id)
        if (
            len(manifest) > MAX_AGENT_AUDIT_EVENTS
            or head["bytes"] + sum(r[9] for r in manifest) > MAX_AGENT_AUDIT_BYTES
        ):
            raise ValueError("agent_audit_too_large")
        if any((r[6], r[7], r[8]) != (head["retained_until"], control["principal"], control["dept"]) for r in manifest):
            raise ValueError("invalid_agent_audit_owner")
        raw = self.conn.execute(
            "select ciphertext,nonce,dek_wrapped,kek_version from agent_runtime_heads where run_id=%s and revision=%s",
            (run_id, head["revision"]),
        ).fetchone()
        if raw is None:
            self._changed()
        head_sealed = Sealed(bytes(raw[0]), bytes(raw[1]), bytes(raw[2]), raw[3])
        rows = self.conn.execute(
            "select event_id,ciphertext,nonce,dek_wrapped,kek_version from agent_runtime_events "
            "where run_id=%s and event_id=any(%s) order by created_at,event_id",
            (run_id, [r[0] for r in manifest]),
        ).fetchall()
        if (
            [r[0] for r in rows] != [r[0] for r in manifest]
            or self._head(run_id) != original
            or self._manifest(run_id) != manifest
        ):
            self._changed()
        # AES-GCM authenticates these original bytes; no old envelope is re-sealed.
        items = [
            AgentAuditItem(
                "agent.runtime.head",
                "runtime_head",
                head["updated_at"],
                head["retained_until"],
                head_sealed,
                head_aad(
                    run_id,
                    control["context_sha256"],
                    head["revision"],
                    head["lease_id"],
                    head["lease_generation"],
                    head["budget_state"],
                    head["budget_deadline"],
                    head["retained_until"],
                ),
                {},
            )
        ]
        for meta, row in zip(manifest, rows, strict=True):
            event_id, kind, item_id, lease_id, generation, created, retained = meta[:7]
            items.append(
                AgentAuditItem(
                    "agent.runtime.event",
                    kind,
                    created,
                    retained,
                    Sealed(bytes(row[1]), bytes(row[2]), bytes(row[3]), row[4]),
                    runtime_aad(
                        run_id, control["context_sha256"], "event", event_id, kind, item_id, lease_id, generation
                    ),
                    {
                        "event_id": str(event_id),
                        "item_id": str(item_id),
                        "lease_id": str(lease_id),
                        "lease_generation": generation,
                    },
                )
            )
        del head["bytes"]
        return AgentAuditBundle(control["trace_id"], _json_metadata(control), _json_metadata(head), tuple(items))

    def _changed(self) -> None:
        raise BusinessError(ErrorCode.version_conflict, "Agent audit changed during reading; request a new snapshot")

    def log_access(self, principal: str, trace_id: str, purpose: str) -> None:
        PgPayloadStore(self.conn).log_access(principal, trace_id, purpose)
