"""Purpose-logged historical Agent material; never a recovery or execution path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from medops.application.contracts import TracePayloadItem, TracePayloadResponse
from medops.application.metrics import has_role
from medops.core.canonical import canonical_hash
from medops.core.deadline import check_deadline, deadline_scope
from medops.core.envelope import KeyProvider, Sealed, open_sealed
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.core.strict_json import strict_json
from medops.domain.identity import UserContext

MAX_AGENT_AUDIT_BYTES = 32 * 1024 * 1024
MAX_AGENT_AUDIT_EVENTS = 512


@dataclass(frozen=True)
class AgentAuditItem:
    node: str
    kind: str
    created_at: datetime
    retained_until: datetime
    sealed: Sealed
    aad: bytes
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AgentAuditBundle:
    trace_id: str
    control: dict[str, Any]
    head: dict[str, Any]
    items: tuple[AgentAuditItem, ...]


class AgentAuditStore(Protocol):
    def load(self, run_id: UUID) -> AgentAuditBundle | None: ...

    def log_access(self, principal: str, trace_id: str, purpose: str) -> None: ...


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_agent_historical_object")
    return value


@dataclass
class AgentAuditReader:
    store: AgentAuditStore
    provider: KeyProvider

    def read(self, admin: UserContext, run_id: str, purpose: str) -> TracePayloadResponse:
        if not has_role(admin.roles, "admin"):
            raise BusinessError(ErrorCode.forbidden, "Agent audit requires the admin role")
        if not isinstance(purpose, str) or not 8 <= len(purpose.strip()) <= 500 or len(purpose) > 500:
            raise BusinessError(ErrorCode.invalid_request, "purpose must contain 8-500 non-padding characters")
        try:
            selected = UUID(run_id)
        except (ValueError, TypeError, AttributeError):
            raise BusinessError(ErrorCode.invalid_request, "run_id must be a UUID") from None
        try:
            with deadline_scope(5.0):
                bundle = self.store.load(selected)
                if bundle is None:
                    raise BusinessError(ErrorCode.not_found, "Agent audit is unavailable or outside retention")
                # The caller must commit this same transaction before returning plaintext.
                self.store.log_access(admin.user_id, bundle.trace_id, purpose)
                items: list[TracePayloadItem] = []
                total = 0
                decoded: list[dict[str, Any]] = []
                for row in bundle.items:
                    raw = open_sealed(row.sealed, aad=row.aad, provider=self.provider)
                    total += len(raw)
                    if total > MAX_AGENT_AUDIT_BYTES:
                        raise ValueError("agent_audit_too_large")
                    value = strict_json(raw)
                    if not isinstance(value, dict):
                        raise ValueError("invalid_agent_audit_body")
                    decoded.append(value)
                    items.append(
                        TracePayloadItem(
                            node=row.node,
                            kind=row.kind,
                            created_at=row.created_at,
                            expires_at=row.retained_until,
                            kek_version=row.sealed.kek_version,
                            payload={**row.metadata, "body": value},
                        )
                    )
                # Historical audit authenticates original bytes and bindings. It must
                # not replay a loop or require today's prompt/tool/budget codecs.
                body = decoded[0]
                run = _object(body.get("run"))
                context = _object(run.get("context"))
                identity = _object(context.get("identity"))
                principal = _object(context.get("principal"))
                c = bundle.control
                if (
                    body.get("version") != "pv-agent-runtime-v1"
                    or identity.get("run_id") != str(selected)
                    or canonical_hash(context) != c["context_sha256"]
                    or identity.get("trace_id") != bundle.trace_id
                    or any(identity.get(n) != c[n] for n in ("case_id", "task_id", "attempt_id"))
                    or principal.get("user_id") != c["principal"]
                    or principal.get("dept") != c["dept"]
                ):
                    raise ValueError("invalid_agent_audit_binding")
                if c["terminal_ref"] is not None:
                    matched = [
                        (r, v)
                        for r, v in zip(bundle.items[1:], decoded[1:], strict=True)
                        if r.metadata["event_id"] == c["terminal_ref"]
                    ]
                    if len(matched) != 1 or matched[0][0].kind != "late_stop":
                        raise ValueError("invalid_agent_audit_terminal")
                    row, value = matched[0]
                    envelope = _object(value.get("envelope"))
                    delivered_run = _object(_object(envelope.get("delivery")).get("run"))
                    terminal = _object(delivered_run.get("terminal"))
                    if (
                        value.get("kind") != "business_terminal"
                        or delivered_run.get("context") != context
                        or delivered_run.get("status") != c["terminal_status"]
                        or terminal.get("material_ref") != row.metadata["item_id"]
                    ):
                        raise ValueError("invalid_agent_audit_terminal")
                # Control is lifecycle metadata; the head itself remains a running checkpoint.
                items[0] = items[0].model_copy(
                    update={"payload": {"control": c, "head": bundle.head, "body": decoded[0]}}
                )
                check_deadline()
                return TracePayloadResponse(trace_id=bundle.trace_id, purpose=purpose, items=tuple(items))
        except (BusinessError, InfrastructureError):
            raise
        except Exception as exc:  # noqa: BLE001 - no sealed bodies, key details or database errors escape
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__) from None
