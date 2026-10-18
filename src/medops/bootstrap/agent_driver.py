"""Actual PostgreSQL loop driver and write-ahead owner; no public API or terminal publisher."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from medops.application.agent_contracts import context_binding
from medops.application.agent_final_gate import FinalGateConfig, check_structure, derived_profile
from medops.application.agent_loop_ports import AgentLoopAbort, LoopCheckpoint
from medops.application.agent_loop_state import CommittedDecision, LoopState, rebuild_loop_state
from medops.application.agent_loop_validation import validate_tool_commit
from medops.application.agent_review import PreparedReview, compile_review, structure_rejection, validate_review_binding
from medops.application.agent_runtime_state import (
    DurableCall,
    PendingTool,
    PlanningFrame,
    RuntimeBody,
    owned_request,
    request_call,
    run_with_budget,
)
from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentToolOutcome
from medops.application.agent_tools import AgentTools, tool_contract_sha256
from medops.core.deadline import CURRENT_DEADLINE, Deadline, deadline_scope
from medops.core.envelope import KeyProvider
from medops.core.errors import BusinessError
from medops.domain.agent_execution import AgentContext, BoundAction, EvidenceHandle, PVAgentRun, StopReason
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.db.agent_fact_scope import AgentFactScope
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts
from medops.infrastructure.db.agent_runtime import PgAgentRuntime, RuntimeHead
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState
from medops.infrastructure.llm.execution_budget import ExecutionBudget, current_budget, finalization_scope
from medops.infrastructure.llm.gateway import ModelCallReceipt, ModelRequest, ModelResponse
from medops.infrastructure.llm.meter import MeteredGateway
from medops.skills.registry import SkillContext, SkillRegistry

Connection = Callable[[], AbstractContextManager[Any]]


@dataclass(frozen=True)
class AgentResources:
    registry: SkillRegistry
    skill_context: SkillContext
    # Mandatory actual resource/version selection check inside the caller's
    # current identity-bound transaction. No permissive deployment default.
    check_bindings: Callable[[Any, AgentContext], None]
    # Explicit None is only for low-level/offline composition; production requires the real gate.
    final_config: FinalGateConfig | None


@contextmanager
def financial_cleanup() -> Iterator[None]:
    """Five seconds for accounting only, including after run cancellation/expiry.

    No provider operation belongs here. The original root's absolute expiration
    and every subsequent call guard remain unchanged.
    """
    token = CURRENT_DEADLINE.set(Deadline(time.monotonic() + 5))
    try:
        yield
    finally:
        CURRENT_DEADLINE.reset(token)


class PgAgentDriver:
    def __init__(
        self,
        *,
        connection: Connection,
        head: RuntimeHead,
        root: ExecutionBudget,
        meter: MeteredGateway,
        lease: AgentLease,
        database_binding: FactDatabaseBinding,
        provider: KeyProvider,
        resources: AgentResources,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.connection, self.head, self.root, self.meter, self.lease = connection, head, root, meter, lease
        self.database_binding, self.provider, self.resources, self.clock = database_binding, provider, resources, clock
        self.context = head.body.run.context
        skill = resources.skill_context
        if (
            head.lease != lease
            or skill.deps.gateway is not meter
            or skill.user != self.context.principal
            or skill.versions != self.context.versions.versions
            or skill.trace_id != self.context.identity.trace_id
            or skill.run_id != str(self.context.identity.run_id)
            or skill.query_context != self.context.query_context
            or self.context.versions.tool_contract_sha256 != tool_contract_sha256(resources.registry)
        ):
            raise AgentLoopAbort("version_conflict")
        resources.registry.agent_adapter().validate_versions(skill.versions.skill_version_set)
        if (
            resources.final_config is not None
            and derived_profile(self.context, resources.final_config, meter.execution_prices) != self.context.profile
        ):
            raise AgentLoopAbort("version_conflict")
        self._lock = threading.RLock()
        self._active_call: str | None = None
        self._prepared_review: PreparedReview | None = None
        self._frozen = False
        self._failed = False
        self._stop_reason: StopReason | None = None

    def freeze_root(self) -> FrozenBudgetState:
        """Suspend once; later accounting snapshots preserve late settlements."""
        with self._lock:
            if self._frozen:
                return FrozenBudgetState.model_validate(self.root.journal_state())
            state = FrozenBudgetState.model_validate(self.root.freeze_state())
            self._frozen = True
            return state

    def _control(self, conn: Any) -> PgAgentControl:
        conn.execute("select set_config('medops.dept',%s,true)", (self.context.principal.dept.value,))
        return PgAgentControl(conn, self.context, database_binding=self.database_binding)

    def _store(self, conn: Any) -> PgAgentRuntime:
        return PgAgentRuntime(self._control(conn), self.provider)

    def _root(self, budget: ExecutionBudget) -> None:
        if self._stop_reason is not None:
            raise AgentLoopAbort(self._stop_reason)
        if self._failed or budget is not self.root or current_budget() is not self.root:
            raise AgentLoopAbort("unsupported_recovery")

    def _facts(self, conn: Any, registry: tuple[EvidenceHandle, ...]) -> None:
        self.resources.check_bindings(conn, self.context)
        facts = PgAgentFacts(conn, self.context.principal, database_binding=self.database_binding)
        facts.check(self.context)
        if self.context.source_scope.resolution == "resolved":
            facts.sources(self.context)
        if registry:
            binding = context_binding(self.context)
            if any(h.binding != binding or h.expires_at <= self.clock() for h in registry):
                raise AgentLoopAbort("version_conflict")
            ids = tuple(dict.fromkeys(h.evidence.citation.chunk_id for h in registry))
            current = {f.evidence.citation.chunk_id: f for f in facts.lookup(self.context, ids)}
            if any(
                (
                    h.evidence.citation.chunk_id not in current
                    or current[h.evidence.citation.chunk_id].evidence != h.evidence
                    or current[h.evidence.citation.chunk_id].source_sha256 != h.source_sha256
                )
                for h in registry
            ):
                raise AgentLoopAbort("version_conflict")

    def check_access(self, context: AgentContext, evidence_registry: tuple[EvidenceHandle, ...]) -> None:
        if self._stop_reason is not None:
            raise AgentLoopAbort(self._stop_reason)
        if context != self.context or self._failed:
            raise AgentLoopAbort("lease_lost" if context != self.context else "audit_failure")
        try:
            with self.connection() as conn:
                self._control(conn).assert_owned(self.lease)
                self._facts(conn, evidence_registry)
        except AgentLoopAbort:
            raise
        except BusinessError:
            raise AgentLoopAbort("safety_boundary") from None
        except AgentToolFault:
            raise AgentLoopAbort("safety_boundary") from None

    def validate_recovery(self, state: LoopState, budget: ExecutionBudget) -> PlanningFrame | None:
        self._root(budget)
        if state != self.head.body.loop or run_with_budget(state.run, budget.snapshot()) != state.run:
            raise AgentLoopAbort("unsupported_recovery")
        if (
            budget.snapshot().reserved_tokens
            or self.head.budget.pending
            or (budget.snapshot().blocked_reason or "").startswith("recovery_")
        ):
            raise AgentLoopAbort("unsupported_recovery")
        rebuilt = rebuild_loop_state(state, expected_run=self.head.body.run, config=self.head.body.config)
        self.check_access(self.context, rebuilt.evidence_registry)
        with self.connection() as conn:
            store = self._store(conn)
            store.control.fence(self.lease)
            actual = store.read()
            if actual.revision != self.head.revision or actual.lease != self.lease:
                raise AgentLoopAbort("unsupported_recovery")
            calls = store.calls()
        frame = self.head.body.frame
        if state.phase in {"decision_started", "planning_returned"}:
            if frame is None or frame.decision_id != state.decision_id:
                raise AgentLoopAbort("unsupported_recovery")
            if frame.receipt is None and any(
                request_call(c.request).call_id == request_call(frame.request).call_id for c in calls
            ):
                raise AgentLoopAbort("unsupported_recovery")
        pending = self.head.body.tool
        if pending is not None and any(
            f"action:{pending.action.action_id}" in (request_call(c.request).attempt_id or "").split("/") for c in calls
        ):
            raise AgentLoopAbort("unsupported_recovery")  # a started tool without committed result is not repeated
        return frame

    def _save(self, store: PgAgentRuntime, body: RuntimeBody) -> RuntimeHead:
        state = FrozenBudgetState.model_validate(self.root.journal_state())
        return store.save(self.lease, body.with_budget(state), state, expected_revision=self.head.revision)

    def _late_stop(self, event: LoopCheckpoint) -> None:
        if event.run.context != self.context:
            raise AgentLoopAbort("lease_lost")
        with financial_cleanup(), self.connection() as conn:
            self._store(conn).append(
                self.lease,
                "late_stop",
                uuid4(),
                {
                    "run": event.run.model_dump(mode="json"),
                    "reason": event.reason,
                    "state": event.state.model_dump(mode="json") if event.state else None,
                },
                retained_until=self.head.retained_until,
            )

    def checkpoint(self, event: LoopCheckpoint) -> None:
        if event.state is None or self._failed or (event.phase == "handoff" and self._stop_reason is not None):
            self._late_stop(event)
            return
        self._root(self.root)
        state = event.state
        if state.run.context != self.context or state.run != run_with_budget(event.run, self.root.snapshot()):
            raise AgentLoopAbort("audit_failure")
        with self._lock:
            try:
                with self.connection() as conn:
                    store = self._store(conn)
                    try:
                        store.control.fence(self.lease)
                    except (AgentLoopAbort, BusinessError):
                        if event.phase != "handoff":
                            raise
                        self._late_stop(event)
                        return
                    old = self.head.body
                    old_history = old.loop.history if old.loop else ()
                    if len(state.history) < len(old_history):
                        raise AgentLoopAbort("audit_failure")
                    for before, after in zip(old_history, state.history, strict=False):
                        if before.model_dump(exclude={"observed_at"}) != after.model_dump(exclude={"observed_at"}):
                            raise AgentLoopAbort("audit_failure")
                    # Keep committed observation times canonical; the in-memory
                    # loop observes the returned result a little later.
                    state = state.model_copy(update={"history": tuple(old_history) + state.history[len(old_history) :]})
                    frame: PlanningFrame | None
                    if event.phase == "decision_started":
                        store.control.consume_decision(self.lease, expected_decisions=old.run.decisions_consumed)
                        if event.request is None or event.decision_id is None:
                            raise AgentLoopAbort("audit_failure")
                        frame = PlanningFrame(
                            decision_id=event.decision_id,
                            request=event.request,
                            receipt=None,
                            response=None,
                            invalid=False,
                            deadline_at=min(
                                state.run.expires_at, state.captured_at + timedelta(seconds=event.request.timeout_s)
                            ),
                        )
                    else:
                        if state.run.decisions_consumed != old.run.decisions_consumed:
                            raise AgentLoopAbort("audit_failure")
                        frame = old.frame
                        if event.phase == "planning_returned":
                            if frame is None:
                                raise AgentLoopAbort("audit_failure")
                            receipt = next(
                                (
                                    r
                                    for r in self.meter.receipts
                                    if r.call.call_id == request_call(frame.request).call_id
                                ),
                                frame.receipt,
                            )
                            saved_response = (
                                frame.response.model_dump(exclude={"call_receipt"}) if frame.response else None
                            )
                            returned_response = (
                                event.response.model_dump(exclude={"call_receipt"}) if event.response else None
                            )
                            if saved_response != returned_response or frame.receipt != receipt:
                                raise AgentLoopAbort("audit_failure")
                            frame = frame.model_copy(
                                update={
                                    "receipt": receipt,
                                    "response": event.response,
                                    "invalid": bool(
                                        (event.response and event.response.truncated)
                                        or (receipt and receipt.error_type == "ModelOutputInvalid")
                                    ),
                                }
                            )
                    if event.phase == "tool_committed" and len(old_history) != len(state.history):
                        raise AgentLoopAbort("audit_failure")  # only execute_tool can commit a tool observation
                    body = RuntimeBody(
                        version=old.version, run=state.run, config=old.config, loop=state, frame=frame, tool=None
                    )
                    head = self._save(store, body)
                    store.append(
                        self.lease,
                        "checkpoint",
                        uuid4(),
                        {
                            "state": state.model_dump(mode="json"),
                            "receipt_ids": list(event.receipt_ids),
                            "progress": asdict(event.progress) if event.progress else None,
                        },
                        retained_until=self.head.retained_until,
                    )
                self.head = head
            except Exception:
                self._failed = True
                raise

    def _call_record(
        self, request: ModelRequest, receipt: ModelCallReceipt | None, response: ModelResponse | None
    ) -> DurableCall:
        owned_request(request, self.context)
        entry = next(
            (dict(e) for e in self.meter.call_journal.snapshot() if e["call_id"] == request_call(request).call_id), None
        )
        if entry is None:
            raise AgentLoopAbort("audit_failure")
        entry.update(
            receipt=receipt.model_dump(mode="json") if receipt else None,
            response=response.model_dump(mode="json") if response else None,
            error_type=receipt.error_type if receipt else None,
        )
        state = FrozenBudgetState.model_validate(self.root.journal_state()) if receipt is None else self.head.budget
        reserve = next((p for p in state.pending if p.call_id == request_call(request).call_id), None)
        if reserve is None:
            raise AgentLoopAbort("audit_failure")
        return DurableCall(request=request, allowance=reserve, receipt=receipt, response=response, audit_entry=entry)

    def admitted(self, request: ModelRequest, budget: ExecutionBudget) -> None:
        self._root(budget)
        record = self._call_record(request, None, None)
        with self._lock:
            try:
                if self._active_call is not None:
                    raise AgentLoopAbort("audit_failure")
                self._active_call = request_call(request).call_id
                with self.connection() as conn:
                    store = self._store(conn)
                    store.control.fence(self.lease)
                    body = self.head.body
                    expected = (
                        f"decision:{body.frame.decision_id}"
                        if request.purpose == "agent_plan" and body.frame
                        else f"action:{body.tool.action.action_id}"
                        if body.tool
                        else f"final:{body.loop.terminal_request.action_id}"
                        if (body.loop and body.loop.phase == "handoff" and body.loop.terminal_request)
                        else None
                    )
                    if expected is None or expected not in (request_call(request).attempt_id or "").split("/"):
                        raise AgentLoopAbort("audit_failure")
                    store.append(
                        self.lease,
                        "call_admitted",
                        UUID(request_call(request).call_id),
                        record.model_dump(mode="json"),
                        retained_until=self.head.retained_until,
                    )
                    head = self._save(store, body)
                self.head = head
            except Exception:
                self._failed = True
                raise

    def settled(
        self, request: ModelRequest, receipt: ModelCallReceipt, response: ModelResponse | None, budget: ExecutionBudget
    ) -> None:
        if budget is not self.root:
            raise AgentLoopAbort("audit_failure")
        record = self._call_record(request, receipt, response)
        with self._lock, financial_cleanup():
            with self.connection() as conn:
                store = self._store(conn)
                start = next(
                    (
                        e
                        for e in store.events()
                        if e.kind == "call_admitted" and e.item_id == UUID(request_call(request).call_id)
                    ),
                    None,
                )
                if (
                    start is None
                    or start.lease != self.lease
                    or DurableCall.model_validate(start.body).request != request
                ):
                    raise AgentLoopAbort("audit_failure")
                store.append(
                    self.lease,
                    "call_settled",
                    UUID(request_call(request).call_id),
                    record.model_dump(mode="json"),
                    retained_until=self.head.retained_until,
                )
                head = None
                try:
                    with conn.transaction():
                        store.control.fence(self.lease)
                        if self._failed:
                            raise AgentLoopAbort("audit_failure")
                        body = self.head.body
                        if (
                            request.purpose == "agent_plan"
                            and body.frame
                            and request_call(body.frame.request).call_id == request_call(request).call_id
                        ):
                            frame = body.frame.model_copy(
                                update={
                                    "receipt": receipt,
                                    "response": response,
                                    "invalid": bool(
                                        (response and response.truncated) or receipt.error_type == "ModelOutputInvalid"
                                    ),
                                }
                            )
                            body = body.model_copy(update={"frame": frame})
                        head = self._save(store, body)
                except (AgentLoopAbort, BusinessError):
                    pass  # fee retention succeeded; an old holder cannot advance progress
            if head is not None:
                self.head = head
            self._active_call = None

    def execute_tool(
        self,
        action: BoundAction,
        *,
        admission_run: PVAgentRun,
        admitted_at: datetime,
        evidence_registry: tuple[EvidenceHandle, ...],
    ) -> AgentToolOutcome:
        self._root(self.root)
        with self._lock:
            pending = self.head.body.tool
            if pending is not None:
                if pending.action != action:
                    raise AgentLoopAbort("audit_failure")
            else:
                pending = PendingTool(action=action, admitted_at=admitted_at, admission_budget=admission_run.budget)
                with self.connection() as conn:
                    head = self._save(self._store(conn), self.head.body.model_copy(update={"tool": pending}))
                self.head = head
        timeout = 20 if action.proposal.action == "search_documents" else 60
        remaining = (
            min(admission_run.expires_at, pending.admitted_at + timedelta(seconds=timeout)) - self.clock()
        ).total_seconds()
        with AgentFactScope(
            self.connection, self.context, self.lease, self.database_binding, self.resources.check_bindings
        ) as facts:
            tool = AgentTools(
                context=self.context,
                facts=facts,
                registry=self.resources.registry,
                skill_context=self.resources.skill_context,
                clock=self.clock,
            )
            with deadline_scope(remaining):
                outcome = tool.execute(action, run=admission_run, evidence_registry=evidence_registry)
            observed_at = self.clock()
            run = run_with_budget(self.head.body.run, self.root.snapshot())
            validate_tool_commit(action, outcome, run, evidence_registry, now=observed_at)
            with self._lock:
                old = self.head.body
                if old.loop is None:
                    raise AgentLoopAbort("audit_failure")
                decision = CommittedDecision(
                    decision_id=action.action_id,
                    decision_index=action.decision_index,
                    admitted_at=pending.admitted_at,
                    observed_at=observed_at,
                    admission_budget=pending.admission_budget,
                    action=action,
                    outcome=outcome,
                    rejected=None,
                )
                state = old.loop.model_copy(
                    update={
                        "run": run,
                        "phase": "tool_committed",
                        "captured_at": observed_at,
                        "history": old.loop.history + (decision,),
                    }
                )
                rebuild_loop_state(state, expected_run=run, config=old.config)
                conn = facts.completion_connection()
                store = self._store(conn)
                store.append(
                    self.lease,
                    "tool_committed",
                    action.action_id,
                    {
                        "outcome": outcome.model_dump(mode="json"),
                        "audit": {
                            "version": "execution-audit-v1",
                            "events": list(tool.audit_snapshot().events),
                            "evidence": [e.model_dump(mode="json") for e in tool.audit_snapshot().evidence],
                            "flagged": list(tool.audit_snapshot().flagged),
                            "spans": [s.model_dump(mode="json") for s in tool.audit_snapshot().spans],
                        },
                    },
                    retained_until=self.head.retained_until,
                )
                head = self._save(store, old.model_copy(update={"run": run, "loop": state, "tool": None}))
                facts.commit()  # commit acknowledgement precedes accepting this observation in memory
                self.head = head
        return outcome

    @contextmanager
    def _review_boundary(self) -> Iterator[None]:
        """A failed/uncertain commit must not advance this instance's stale head."""
        try:
            yield
        except BaseException:
            self._failed = True
            raise

    def verify_final(self):
        """Validate the saved finish request; never publish business completion."""
        self._root(self.root)
        with self._review_boundary():
            state = self.head.body.loop
            if (
                state is None
                or state.phase != "handoff"
                or state.terminal_request is None
                or state.terminal_request.proposal.action != "finish"
                or self.resources.final_config is None
            ):
                raise AgentLoopAbort("unsupported_requirement")
            rebuilt = rebuild_loop_state(state, expected_run=self.head.body.run, config=self.head.body.config)
            self.check_access(self.context, rebuilt.evidence_registry)
            with AgentFactScope(
                self.connection, self.context, self.lease, self.database_binding, self.resources.check_bindings
            ) as facts:
                tool = AgentTools(
                    context=self.context,
                    facts=facts,
                    registry=self.resources.registry,
                    skill_context=self.resources.skill_context,
                    clock=self.clock,
                )
                result = tool.verify_final_citations(
                    state.terminal_request,
                    run=self.head.body.run,
                    evidence_registry=rebuilt.evidence_registry,
                    final_config=self.resources.final_config,
                )
                prepared = compile_review(
                    self.context, state.terminal_request, rebuilt.evidence_registry, result, self.resources.final_config
                )
                conn = facts.completion_connection()
                store = self._store(conn)
                store.append(
                    self.lease,
                    "checkpoint",
                    uuid4(),
                    {
                        "kind": "final_material_check",
                        "draft_sha256": result.draft_sha256,
                        "profile": result.profile.model_dump(mode="json"),
                        "material_check": result.material_check.model_dump(mode="json")
                        if result.material_check
                        else None,
                        "prepared_review": prepared.model_dump(mode="json"),
                        "events": list(tool.audit_snapshot().events),
                    },
                    retained_until=self.head.retained_until,
                )
                head = self._save(store, self.head.body)
                facts.commit()
                self.head = head
                self._prepared_review = prepared
            return result

    def prepare_review(self) -> PreparedReview:
        """Return only committed private material; stopped/unknown work is never reissued."""
        self._root(self.root)
        with self._review_boundary():
            state = self.head.body.loop
            config = self.resources.final_config
            if state is None or state.phase != "handoff" or state.terminal_request is None or config is None:
                raise AgentLoopAbort("unsupported_requirement")
            action = state.terminal_request
            if action.proposal.action != "finish":
                raise AgentLoopAbort("unsupported_requirement")
            rebuilt = rebuild_loop_state(state, expected_run=self.head.body.run, config=self.head.body.config)
            self.check_access(self.context, rebuilt.evidence_registry)
            if self._prepared_review is None and self.root.finalization_snapshot() is not None:
                # Only a confirmed encrypted material event may be reused. A known
                # model receipt without this commit remains a stopped final phase.
                with self.connection() as conn:
                    store = self._store(conn)
                    store.control.fence(self.lease)
                    rows = [
                        e
                        for e in store.events()
                        if e.kind == "checkpoint"
                        and e.body.get("kind") in {"final_material_check", "final_review_rejected"}
                        and e.body.get("prepared_review") is not None
                    ]
                    if len(rows) != 1:
                        raise AgentLoopAbort("unsupported_recovery")
                    review = PreparedReview.model_validate(rows[0].body["prepared_review"])
                    validate_review_binding(review, self.context, action, rebuilt.evidence_registry, config)
                    calls = store.calls()
                    known = {
                        c.allowance.call_id
                        for c in calls
                        if c.receipt is not None
                        and f"final:{action.action_id}" in (request_call(c.request).attempt_id or "").split("/")
                    }
                    if not set(review.call_receipt_ids) <= known:
                        raise AgentLoopAbort("unsupported_recovery")
                self._prepared_review = review
            if self._prepared_review is None:
                try:
                    check_structure(self.context, action.proposal.draft)
                except AgentToolFault:
                    review = structure_rejection(self.context, action, config)
                    with (
                        finalization_scope((), prices=self.meter.execution_prices),
                        AgentFactScope(
                            self.connection,
                            self.context,
                            self.lease,
                            self.database_binding,
                            self.resources.check_bindings,
                        ) as facts,
                    ):
                        facts.final_check(self.context, ())
                        conn = facts.completion_connection()
                        store = self._store(conn)
                        store.append(
                            self.lease,
                            "checkpoint",
                            uuid4(),
                            {
                                "kind": "final_review_rejected",
                                "prepared_review": review.model_dump(mode="json"),
                                "reason": "unsupported_requirement",
                                "semantic_model_run": False,
                            },
                            retained_until=self.head.retained_until,
                        )
                        head = self._save(store, self.head.body)
                        facts.commit()
                        self.head = head
                        self._prepared_review = review
                else:
                    self.verify_final()
            if self._prepared_review is None:
                raise AgentLoopAbort("audit_failure")
            validate_review_binding(self._prepared_review, self.context, action, rebuilt.evidence_registry, config)
            self.check_access(self.context, rebuilt.evidence_registry)
            return self._prepared_review
