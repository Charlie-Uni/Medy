"""Fenced encrypted heads and immutable runtime events; callers own short commits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from medops.application.agent_contracts import context_binding
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_runtime_envelope import head_aad, runtime_aad
from medops.application.agent_runtime_state import DurableCall, RuntimeBody, run_with_budget
from medops.core.canonical import canonical_json
from medops.core.envelope import KeyProvider, Sealed, open_sealed, seal
from medops.core.strict_json import strict_json
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, advances_budget

MAX_RUNTIME_BYTES = 20 * 1024 * 1024
MAX_RUNTIME_EVENTS = 512
_COLUMNS = "revision,lease_id,lease_generation,budget_state,budget_deadline,ciphertext,nonce,dek_wrapped,kek_version,retained_until"


@dataclass(frozen=True)
class RuntimeHead:
    revision: int
    lease: AgentLease
    budget: FrozenBudgetState
    budget_deadline: datetime
    retained_until: datetime
    body: RuntimeBody


@dataclass(frozen=True)
class RuntimeEvent:
    kind: str
    item_id: UUID
    lease: AgentLease
    body: dict[str, Any]


class PgAgentRuntime:
    def __init__(self, control: PgAgentControl, provider: KeyProvider):
        self.control, self.conn, self.provider = control, control.conn, provider
        self.context = control.context
        self.binding = context_binding(self.context)

    def _aad(self, kind: str, *parts: object) -> bytes:
        return runtime_aad(self.binding.run_id, self.binding.conditions_sha256, kind, *parts)

    def _head_aad(
        self, revision: int, lease: AgentLease, data: dict[str, Any], deadline: datetime, retained_until: datetime
    ) -> bytes:
        return head_aad(
            self.binding.run_id,
            self.binding.conditions_sha256,
            revision,
            lease.lease_id,
            lease.generation,
            data,
            deadline,
            retained_until,
        )

    def _seal(self, body: dict[str, Any], aad: bytes) -> Sealed:
        raw = canonical_json(body).encode()
        if len(raw) > MAX_RUNTIME_BYTES:
            raise AgentLoopAbort("audit_failure")
        return seal(raw, aad=aad, provider=self.provider)

    def _open(self, row: tuple[Any, ...], aad: bytes) -> dict[str, Any]:
        if len(row[0]) > MAX_RUNTIME_BYTES + 16:
            raise AgentLoopAbort("unsupported_recovery")
        raw = open_sealed(Sealed(bytes(row[0]), bytes(row[1]), bytes(row[2]), row[3]), aad=aad, provider=self.provider)
        result = strict_json(raw)
        if not isinstance(result, dict):
            raise AgentLoopAbort("unsupported_recovery")
        return result

    def read(self, *, lock: bool = False) -> RuntimeHead:
        # Ownership/context is checked even for an already-cancelled run, so the
        # caller can retain its audit. Execution callers must ALSO fence the lease.
        self.control.get()
        row = self.conn.execute(
            f"select {_COLUMNS} from agent_runtime_heads where run_id=%s and principal=%s and context_sha256=%s"
            + (" for update" if lock else ""),
            (self.binding.run_id, self.context.principal.user_id, self.binding.conditions_sha256),
        ).fetchone()
        if row is None:
            raise AgentLoopAbort("unsupported_recovery")
        revision, lease_id, generation, data, deadline = row[:5]
        budget = FrozenBudgetState.model_validate(data)
        aad = self._head_aad(
            revision,
            AgentLease(run_id=self.binding.run_id, lease_id=lease_id, generation=generation),
            data,
            deadline,
            row[9],
        )
        body = RuntimeBody.model_validate(self._open(row[5:9], aad))
        if body.run.context != self.context or run_with_budget(body.run, budget.snapshot) != body.run:
            raise AgentLoopAbort("unsupported_recovery")
        return RuntimeHead(
            revision,
            AgentLease(run_id=self.binding.run_id, lease_id=lease_id, generation=generation),
            budget,
            deadline,
            row[9],
            body,
        )

    def initialize(
        self,
        lease: AgentLease,
        body: RuntimeBody,
        budget: FrozenBudgetState,
        *,
        budget_deadline: datetime,
        retained_until: datetime,
    ) -> RuntimeHead:
        self.control.fence(lease)
        if (
            body.run.decisions_consumed
            or any(body.run.budget.model_dump().values())
            or budget.pending
            or budget.settled
            or body.run.context != self.context
            or body.loop is not None
            or budget_deadline > body.run.expires_at
            or retained_until < body.run.expires_at
        ):
            raise AgentLoopAbort("unsupported_recovery")
        data = budget.model_dump(mode="json")
        sealed = self._seal(
            body.model_dump(mode="json"), self._head_aad(1, lease, data, budget_deadline, retained_until)
        )
        user = self.context.principal
        self.conn.execute(
            """insert into agent_runtime_heads
            (run_id,principal,dept,context_sha256,revision,lease_id,lease_generation,budget_state,budget_deadline,
             ciphertext,nonce,dek_wrapped,kek_version,retained_until)
             values (%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                lease.run_id,
                user.user_id,
                user.dept.value,
                self.binding.conditions_sha256,
                lease.lease_id,
                lease.generation,
                Jsonb(data),
                budget_deadline,
                sealed.ciphertext,
                sealed.nonce,
                sealed.dek_wrapped,
                sealed.kek_version,
                retained_until,
            ),
        )
        return RuntimeHead(1, lease, budget, budget_deadline, retained_until, body)

    def save(
        self, lease: AgentLease, body: RuntimeBody, budget: FrozenBudgetState, *, expected_revision: int
    ) -> RuntimeHead:
        self.control.fence(lease)
        old = self.read(lock=True)
        control = self.control.get()
        if (
            type(expected_revision) is not int
            or old.revision != expected_revision
            or old.lease.generation > lease.generation
            or (old.lease.generation == lease.generation and old.lease.lease_id != lease.lease_id)
            or body.run.context != self.context
            or body.run.decisions_consumed != control.decisions_consumed
            or (body.run.started_at, body.run.expires_at) != (control.started_at, control.expires_at)
            or run_with_budget(body.run, budget.snapshot) != body.run
            or not advances_budget(old.budget, budget)
        ):
            raise AgentLoopAbort("unsupported_recovery")
        revision = old.revision + 1
        data = budget.model_dump(mode="json")
        sealed = self._seal(
            body.model_dump(mode="json"),
            self._head_aad(revision, lease, data, old.budget_deadline, old.retained_until),
        )
        self.conn.execute(
            """update agent_runtime_heads set revision=%s,lease_id=%s,lease_generation=%s,budget_state=%s,
             ciphertext=%s,nonce=%s,dek_wrapped=%s,kek_version=%s,updated_at=clock_timestamp()
             where run_id=%s and revision=%s""",
            (
                revision,
                lease.lease_id,
                lease.generation,
                Jsonb(data),
                sealed.ciphertext,
                sealed.nonce,
                sealed.dek_wrapped,
                sealed.kek_version,
                lease.run_id,
                expected_revision,
            ),
        )
        return RuntimeHead(revision, lease, budget, old.budget_deadline, old.retained_until, body)

    def append(
        self, lease: AgentLease, kind: str, item_id: UUID, body: dict[str, Any], *, retained_until: datetime
    ) -> UUID:
        if kind not in {"call_admitted", "call_settled", "tool_committed", "checkpoint", "late_stop"}:
            raise ValueError("invalid_agent_runtime_event")
        # Late settlements/stops deliberately do not acquire a live lease. Their
        # immutable admission/control binding is verified by the driver; they can
        # never advance the head. A terminal event alone is not publication authority:
        # the terminal owner must also atomically seal control under its final fence.
        if kind not in {"call_settled", "late_stop"}:
            self.control.fence(lease)
        event_id = uuid4()
        sealed = self._seal(body, self._aad("event", event_id, kind, item_id, lease.lease_id, lease.generation))
        user = self.context.principal
        inserted = self.conn.execute(
            """insert into agent_runtime_events
            (event_id,run_id,principal,dept,lease_id,lease_generation,kind,item_id,
             ciphertext,nonce,dek_wrapped,kek_version,retained_until)
             values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
             on conflict(run_id,kind,item_id) do nothing returning event_id""",
            (
                event_id,
                lease.run_id,
                user.user_id,
                user.dept.value,
                lease.lease_id,
                lease.generation,
                kind,
                item_id,
                sealed.ciphertext,
                sealed.nonce,
                sealed.dek_wrapped,
                sealed.kek_version,
                retained_until,
            ),
        ).fetchone()
        if inserted is None:
            if kind != "call_settled":
                raise AgentLoopAbort("unsupported_recovery")
            prior = next((e for e in self.events() if e.kind == kind and e.item_id == item_id), None)
            if prior is None or prior.lease != lease or canonical_json(prior.body) != canonical_json(body):
                raise AgentLoopAbort("audit_failure")

        if inserted is not None:
            return inserted[0]
        row = self.conn.execute(
            "select event_id from agent_runtime_events where run_id=%s and kind=%s and item_id=%s",
            (lease.run_id, kind, item_id),
        ).fetchone()
        if row is None:
            raise AgentLoopAbort("audit_failure")
        return row[0]

    def events(self) -> tuple[RuntimeEvent, ...]:
        rows = self.conn.execute(
            """select event_id,kind,item_id,lease_id,lease_generation,ciphertext,nonce,dek_wrapped,kek_version
             from agent_runtime_events where run_id=%s and principal=%s order by created_at,event_id limit %s""",
            (self.binding.run_id, self.context.principal.user_id, MAX_RUNTIME_EVENTS + 1),
        ).fetchall()
        if len(rows) > MAX_RUNTIME_EVENTS:
            raise AgentLoopAbort("audit_failure")
        return tuple(
            RuntimeEvent(
                r[1],
                r[2],
                AgentLease(run_id=self.binding.run_id, lease_id=r[3], generation=r[4]),
                self._open(r[5:9], self._aad("event", r[0], r[1], r[2], r[3], r[4])),
            )
            for r in rows
        )

    def calls(self) -> tuple[DurableCall, ...]:
        starts: dict[UUID, RuntimeEvent] = {}
        finishes: dict[UUID, RuntimeEvent] = {}
        for event in self.events():
            if event.kind == "call_admitted":
                starts[event.item_id] = event
            elif event.kind == "call_settled":
                finishes[event.item_id] = event
        if not finishes.keys() <= starts.keys() or len(starts) > 128:
            raise AgentLoopAbort("unsupported_recovery")
        calls = []
        for call_id, event in starts.items():
            end = finishes.get(call_id)
            if end is not None and end.lease != event.lease:
                raise AgentLoopAbort("unsupported_recovery")
            record = DurableCall.model_validate(end.body if end is not None else event.body)
            first = DurableCall.model_validate(event.body)
            if (
                UUID(record.allowance.call_id) != call_id
                or record.request != first.request
                or record.allowance != first.allowance
                or (end is not None and record.receipt is None)
            ):
                raise AgentLoopAbort("unsupported_recovery")
            calls.append(record)
        return tuple(calls)
