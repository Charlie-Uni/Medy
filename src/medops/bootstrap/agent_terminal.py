"""Trusted terminal owner: no model-selected commit, no external dispatch, no new budget."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from medops.application.agent_contracts import context_binding, validate_run_snapshot
from medops.application.agent_final_gate import policy_sha256
from medops.application.agent_loop_ports import AgentLoopAbort, AgentLoopResult
from medops.application.agent_loop_state import rebuild_loop_state
from medops.application.agent_review import PreparedReview, RequirementReview
from medops.application.agent_runtime_state import reconcile_budget, run_with_budget, verify_accounting
from medops.application.agent_stop_gate import StopVerdict, parse_stop_verdict, stop_digest, stop_request
from medops.application.agent_terminal import (
    AgentDelivery,
    AgentTerminalMaterial,
    CommittedActionReceipt,
    EscalationReceipt,
    TerminalEnvelope,
    TerminalStatus,
)
from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentFact, ExtractedElement, ExtractionPayload
from medops.core.canonical import canonical_hash
from medops.core.deadline import DeadlineExceeded, check_deadline, deadline_scope, execution_admission
from medops.core.errors import BusinessError
from medops.core.strict_json import strict_json
from medops.domain.agent_actions import ClarificationQuestion, ClarifyAction, EscalateAction, FinishAction
from medops.domain.agent_execution import TERMINAL_REASONS, AgentContext, EvidenceHandle, StopReason, TerminalRecord
from medops.domain.safety import SafetyDecision
from medops.infrastructure.db.agent_fact_scope import AgentFactScope
from medops.infrastructure.db.agent_facts import PgAgentFacts
from medops.infrastructure.db.agent_runtime import PgAgentRuntime
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.execution_budget import check_execution_budget, finalization_scope
from medops.infrastructure.llm.gateway import BudgetExceeded, ModelTimeout
from medops.safety.checks import check_input, check_output_text

if TYPE_CHECKING:
    from medops.bootstrap.agent_driver import PgAgentDriver
    from medops.bootstrap.agent_execution import AgentRuntime


def _status(reason: StopReason) -> TerminalStatus:
    return cast(TerminalStatus, next(s for s, reasons in TERMINAL_REASONS.items() if reason in reasons))


def _registered_facts(registry: tuple[EvidenceHandle, ...]) -> tuple[AgentFact, ...]:
    """Repeated searches can issue distinct handles for the same unchanged chunk."""
    unique: dict[str, AgentFact] = {}
    for item in registry:
        fact = AgentFact(evidence=item.evidence, source_sha256=item.source_sha256)
        chunk_id = item.evidence.citation.chunk_id
        if chunk_id in unique and unique[chunk_id] != fact:
            raise AgentToolFault("denied_or_unavailable")
        unique[chunk_id] = fact
    return tuple(unique.values())


class AgentTerminalOwner:
    def __init__(self, driver: PgAgentDriver):
        self.d = driver

    def _check_stop(self, registry: tuple[EvidenceHandle, ...]) -> tuple[StopVerdict, UUID]:
        d, state, cfg = self.d, self.d.head.body.loop, self.d.resources.final_config
        if state is None or state.terminal_request is None or cfg is None:
            raise AgentLoopAbort("unsupported_requirement")
        action = state.terminal_request
        if (
            isinstance(action.proposal, ClarifyAction)
            and d.context.source_scope.resolution == "resolved"
            and {q.field for q in action.proposal.questions} & {"source_document", "source_version"}
        ):
            raise AgentToolFault("unsupported")
        if d.root.finalization_snapshot() is not None:
            with d.connection() as conn:
                store = d._store(conn)
                store.control.fence(d.lease)
                rows = [
                    e for e in store.events() if e.kind == "checkpoint" and e.body.get("kind") == "final_stop_check"
                ]
                if (
                    len(rows) != 1
                    or rows[0].body.get("state_sha256") != stop_digest(state)
                    or rows[0].body.get("policy_sha256") != policy_sha256(cfg)
                ):
                    raise AgentLoopAbort("unsupported_recovery")
                verdict = parse_stop_verdict(rows[0].body["verdict"], d.context, action)
                calls = [
                    c
                    for c in store.calls()
                    if c.request.purpose == "agent_final_stop"
                    and c.request.call is not None
                    and f"final:{action.action_id}" in (c.request.call.attempt_id or "").split("/")
                ]
                if (
                    len(calls) != 1
                    or calls[0].receipt is None
                    or calls[0].response is None
                    or calls[0].response.truncated
                    or parse_stop_verdict(strict_json(calls[0].response.text), d.context, action) != verdict
                ):
                    raise AgentLoopAbort("unsupported_recovery")
                row = conn.execute(
                    "select event_id from agent_runtime_events where run_id=%s and kind='checkpoint' and item_id=%s",
                    (d.context.identity.run_id, rows[0].item_id),
                ).fetchone()
                if row is None:
                    raise AgentLoopAbort("audit_failure")
                return verdict, row[0]
        if isinstance(action.proposal, EscalateAction):
            rebuilt = rebuild_loop_state(state, expected_run=d.head.body.run, config=d.head.body.config)
            if (
                (
                    action.proposal.reason == "step_limit"
                    and state.run.decisions_consumed < d.context.profile.max_decision_steps
                )
                or (
                    action.proposal.reason == "no_progress"
                    and rebuilt.progress.snapshot().consecutive < d.context.profile.same_no_progress_limit
                )
                or (
                    action.proposal.reason == "source_ambiguous"
                    and d.context.source_scope.resolution != "ambiguous"
                    and not any(x.outcome and x.outcome.kind == "ambiguous" for x in state.history)
                )
            ):
                raise AgentToolFault("unsupported")
        request = stop_request(d.context, state, cfg, registry)
        with (
            deadline_scope(min(cfg.timeout_s, (d.context.profile.timeout_ms / 1000))),
            execution_admission(),
            call_scope(
                run_id=str(d.context.identity.run_id),
                attempt_id=f"{d.context.identity.attempt_id}/final:{action.action_id}",
                before_call=lambda: d.check_access(d.context, registry),
            ),
            finalization_scope((request,), prices=d.meter.execution_prices),
        ):
            response = d.meter.complete(request)
            if response.truncated:
                raise AgentToolFault("dependency_error")
            verdict = parse_stop_verdict(strict_json(response.text), d.context, action)
            check_execution_budget()
            check_deadline()
        # Save the actual check under a fresh fact fence, exactly like finish.
        with AgentFactScope(d.connection, d.context, d.lease, d.database_binding, d.resources.check_bindings) as facts:
            actual = _registered_facts(registry)
            facts.final_check(d.context, actual, check_sources=d.context.source_scope.resolution == "resolved")
            conn = facts.completion_connection()
            store = d._store(conn)
            event = store.append(
                d.lease,
                "checkpoint",
                uuid4(),
                {
                    "kind": "final_stop_check",
                    "state_sha256": stop_digest(state),
                    "policy_sha256": policy_sha256(cfg),
                    "verdict": verdict.model_dump(mode="json"),
                },
                retained_until=d.head.retained_until,
            )
            head = d._save(store, d.head.body)
            facts.commit()
            d.head = head
        return verdict, event

    def publish(self, handoff: AgentLoopResult) -> AgentDelivery:
        d = self.d
        if handoff.run.context != d.context:
            raise AgentLoopAbort("audit_failure")
        state = d.head.body.loop
        if d._failed or d._stop_reason is not None or state is None or state.phase != "handoff":
            reason = d._stop_reason or handoff.reason
            if reason not in TERMINAL_REASONS["failed"] | {"cancelled", "safety_boundary"}:
                raise AgentLoopAbort("audit_failure")
            return self._commit(reason, None, None, None, (), (), ())
        d._root(d.root)
        rebuilt = rebuild_loop_state(state, expected_run=d.head.body.run, config=d.head.body.config)
        registry, action = rebuilt.evidence_registry, state.terminal_request
        review: PreparedReview | None = None
        verdict: StopVerdict | None = None
        verification: UUID | None = None
        reason = cast(StopReason, state.stop_reason)
        questions: tuple[ClarificationQuestion, ...] = ()
        elements: tuple[ExtractedElement, ...] = ()
        try:
            d.check_access(d.context, registry)
            if action is not None and isinstance(action.proposal, FinishAction):
                review = d.prepare_review()
                reason = review.reason
                with d.connection() as conn:
                    store = d._store(conn)
                    events = store.events()
                    # The saved event is authenticated by the store, not found by a model-supplied reference.
                    found = [
                        e
                        for e in events
                        if e.kind == "checkpoint"
                        and e.body.get("kind") in {"final_material_check", "final_review_rejected"}
                    ]
                    if len(found) != 1:
                        raise AgentLoopAbort("audit_failure")
                    row = conn.execute(
                        "select event_id from agent_runtime_events where run_id=%s and kind='checkpoint' and item_id=%s",
                        (d.context.identity.run_id, found[0].item_id),
                    ).fetchone()
                    if row is None:
                        raise AgentLoopAbort("audit_failure")
                    verification = row[0]
            elif action is not None and isinstance(action.proposal, (ClarifyAction, EscalateAction)):
                verdict, verification = self._check_stop(registry)
                safe_texts = (
                    ([q.question for q in action.proposal.questions] + [q.reason for q in action.proposal.questions])
                    if isinstance(action.proposal, ClarifyAction)
                    else [f.value for f in action.proposal.draft.narrative_facts]
                    + [c.text for c in action.proposal.draft.guideline_claims]
                )
                safe = (
                    verdict.scope_safe
                    and all(check_input(t).decision is SafetyDecision.allow for t in safe_texts)
                    and check_output_text(safe_texts).decision is SafetyDecision.allow
                )
                accepted = (
                    verdict.decision_supported and safe and all(q.necessary and q.grounded for q in verdict.questions)
                )
                if accepted:
                    reason = (
                        "clarification_required"
                        if isinstance(action.proposal, ClarifyAction)
                        else action.proposal.reason
                    )
                    questions = action.proposal.questions if isinstance(action.proposal, ClarifyAction) else ()
                    if verdict.narrative_supported:
                        extracted = [
                            x
                            for entry in state.history
                            if entry.outcome
                            and entry.outcome.kind == "ok"
                            and isinstance(entry.outcome.payload, ExtractionPayload)
                            for x in entry.outcome.payload.elements
                        ]
                        elements = tuple(dict.fromkeys(extracted))
                        if (
                            len(elements) > 64
                            or any(d.context.narrative[x.char_start : x.char_end] != x.quote for x in elements)
                            or check_output_text([x.value for x in elements]).decision is not SafetyDecision.allow
                        ):
                            raise AgentToolFault("dependency_error")
                else:
                    reason = "dependency_error" if safe else "safety_boundary"
            elif reason == "completed" or reason == "clarification_required":
                raise AgentLoopAbort("audit_failure")
        except (
            AgentLoopAbort,
            AgentToolFault,
            BusinessError,
            BudgetExceeded,
            DeadlineExceeded,
            ModelTimeout,
            ValueError,
        ) as exc:
            review, verdict, verification, questions, elements = None, None, None, (), ()
            reason = (
                exc.reason
                if isinstance(exc, AgentLoopAbort)
                else "budget_exceeded"
                if isinstance(exc, BudgetExceeded)
                else "timeout"
                if isinstance(exc, (DeadlineExceeded, ModelTimeout))
                else "safety_boundary"
                if isinstance(exc, BusinessError)
                else "dependency_error"
            )
        return self._commit(reason, review, verdict, verification, questions, elements, registry)

    def _commit(
        self,
        reason: StopReason,
        review: PreparedReview | None,
        verdict: StopVerdict | None,
        verification: UUID | None,
        questions: tuple[ClarificationQuestion, ...],
        elements: tuple[ExtractedElement, ...],
        registry: tuple[EvidenceHandle, ...],
    ) -> AgentDelivery:
        d = self.d
        status = _status(reason)
        # No new provider operation is possible even if the following commit is uncertain.
        budget = d.freeze_root()
        from medops.bootstrap.agent_driver import financial_cleanup

        with financial_cleanup(), d.connection() as conn:
            store = d._store(conn)
            control = store.control
            current = control._read(lock=True)
            if (current.lease_id, current.lease_generation) != (d.lease.lease_id, d.lease.generation):
                raise AgentLoopAbort("lease_lost")
            if current.terminal_ref is not None:
                raise AgentLoopAbort("unsupported_recovery")
            now = conn.execute("select clock_timestamp()").fetchone()[0]
            if current.cancelled_at is not None:
                status, reason = "cancelled", "cancelled"
            elif now >= current.expires_at or now >= d.head.budget_deadline:
                status, reason = "failed", "timeout"
            if status in {"failed", "cancelled"}:
                review, verdict, verification, questions, elements, registry = None, None, None, (), (), ()
            else:
                control.fence(d.lease)
                d.resources.check_bindings(conn, d.context)
                facts = PgAgentFacts(conn, d.context.principal, database_binding=d.database_binding)
                facts.check(d.context)
                if d.context.source_scope.resolution == "resolved":
                    facts.sources(d.context)
                facts.final_check(
                    d.context,
                    _registered_facts(registry),
                    check_sources=d.context.source_scope.resolution == "resolved",
                )
            # Reconcile durable late receipts without resetting the actual root.
            calls = store.calls()
            reconciled = reconcile_budget(budget, calls)
            verify_accounting(reconciled, calls, d.context)
            if status not in {"failed", "cancelled"}:
                if reconciled.snapshot.blocked_reason is not None:
                    status, reason = "failed", "budget_exceeded"
                elif reconciled.pending:
                    status, reason = "failed", "unsupported_recovery"
                if status == "failed":
                    review, verdict, verification, questions, elements, registry = None, None, None, (), (), ()
            run = run_with_budget(d.head.body.run, reconciled.snapshot)
            items = (
                review.requirements
                if review
                else tuple(
                    RequirementReview(
                        requirement_id=r.requirement_id, kind=r.kind, required=r.required, state="missing"
                    )
                    for r in d.context.requirements
                )
            )
            ref = uuid4()
            material = AgentTerminalMaterial(
                binding=context_binding(d.context),
                status=status,
                reason=reason,
                continuation_mode="new_execution_required" if status == "awaiting_clarification" else "not_applicable",
                requirements=items,
                missing_requirement_ids=tuple(r.requirement_id for r in items if r.required and r.state != "verified"),
                review=review,
                questions=questions,
                extracted_elements=elements,
                stop_check=verdict,
                escalation=EscalationReceipt(receipt_id=ref) if status == "escalated" else None,
                committed_actions=tuple(
                    CommittedActionReceipt(
                        action_id=x.action.action_id,
                        action=x.action.proposal.action,
                        decision_index=x.action.decision_index,
                        outcome=x.outcome.kind,
                    )
                    for x in d.head.body.loop.history
                    if x.action and x.outcome
                )
                if d.head.body.loop
                else (),
                call_receipt_ids=tuple(c.allowance.call_id for c in calls if c.receipt is not None),
                pending_call_ids=tuple(c.allowance.call_id for c in calls if c.receipt is None),
            )
            terminal = TerminalRecord(
                binding=context_binding(d.context),
                status=status,
                reason=reason,
                material_ref=ref,
                material_sha256=canonical_hash(material.model_dump(mode="json")),
                audit_ref=ref,
                verification_ref=verification,
            )
            stopped = validate_run_snapshot(
                run.model_copy(update={"status": status, "stopped_at": now, "terminal": terminal})
            )
            result = AgentDelivery(run=stopped, material=material)
            envelope = TerminalEnvelope(
                delivery=result,
                registry=registry,
                budget=reconciled,
                verification_event=verification,
                stopped_at=now,
                accounted_complete=not reconciled.pending,
            )
            # The head is the final execution snapshot; the separate terminal is authoritative.
            if status not in {"failed", "cancelled"}:
                head = d._save(store, d.head.body)
            else:
                head = d.head
            event = store.append(
                d.lease,
                "late_stop",
                ref,
                {"kind": "business_terminal", "envelope": envelope.model_dump(mode="json")},
                retained_until=d.head.retained_until,
            )
            control.seal(d.lease, event, status)
        d.head = head
        return result


def read_delivery(runtime: AgentRuntime, context: AgentContext) -> AgentDelivery:
    """No executable root, no fee; validate current identity/facts on the same read transaction."""
    from medops.infrastructure.llm.meter import MeteredGateway

    with runtime.connection() as conn:
        control = runtime._control(conn, context)
        current = control.get()
        if current.terminal_ref is None:
            raise AgentLoopAbort("unsupported_requirement")
        store = PgAgentRuntime(control, runtime.provider)
        head = store.read()
        if head.retained_until <= conn.execute("select clock_timestamp()").fetchone()[0]:
            raise AgentLoopAbort("unsupported_requirement")
        # Authenticate all stored bodies before selecting the pointed-to event.
        row = conn.execute(
            "select kind,item_id from agent_runtime_events where event_id=%s and run_id=%s",
            (current.terminal_ref, context.identity.run_id),
        ).fetchone()
        if row is None or row[0] != "late_stop":
            raise AgentLoopAbort("audit_failure")
        events = store.events()
        entries = [
            e for e in events if e.kind == row[0] and e.item_id == row[1] and e.body.get("kind") == "business_terminal"
        ]
        if len(entries) != 1:
            raise AgentLoopAbort("audit_failure")
        envelope = TerminalEnvelope.model_validate(entries[0].body["envelope"])
        result = envelope.delivery
        if (
            result.run.context != context
            or result.run.status != current.terminal_status
            or result.run.terminal is None
            or result.run.terminal.material_ref != row[1]
        ):
            raise AgentLoopAbort("audit_failure")
        if envelope.verification_event is not None:
            proof_row = conn.execute(
                "select kind,item_id from agent_runtime_events where event_id=%s and run_id=%s",
                (envelope.verification_event, context.identity.run_id),
            ).fetchone()
            if proof_row is None or proof_row[0] != "checkpoint":
                raise AgentLoopAbort("audit_failure")
            proofs = [e for e in events if e.kind == proof_row[0] and e.item_id == proof_row[1]]
            if len(proofs) != 1:
                raise AgentLoopAbort("audit_failure")
            proof = proofs[0].body
            if result.material.review is not None:
                if (
                    proof.get("kind") not in {"final_material_check", "final_review_rejected"}
                    or PreparedReview.model_validate(proof.get("prepared_review")) != result.material.review
                ):
                    raise AgentLoopAbort("audit_failure")
            elif result.material.stop_check is not None:
                if (
                    proof.get("kind") != "final_stop_check"
                    or StopVerdict.model_validate(proof.get("verdict")) != result.material.stop_check
                ):
                    raise AgentLoopAbort("audit_failure")
            else:
                raise AgentLoopAbort("audit_failure")
        verify_accounting(envelope.budget, store.calls(), context)
        if result.material.review is not None or result.material.questions or result.material.extracted_elements:
            resources = runtime.resources(context, MeteredGateway(runtime.gateway))
            resources.check_bindings(conn, context)
            facts = PgAgentFacts(conn, context.principal, database_binding=runtime.database_binding)
            facts.final_check(
                context,
                _registered_facts(envelope.registry),
                check_sources=context.source_scope.resolution == "resolved",
            )
        return result
