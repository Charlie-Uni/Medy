"""Action-scoped, sequential PV tool adapters. No planner, terminal handler or retry loop.

The caller owns the root allowance, absolute deadline and transaction. Persist the
outcome under the returned fact fence and commit before starting another action.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from medops.application.agent_contracts import AgentContractError, admit_action, context_binding
from medops.application.agent_tool_ports import AgentFacts, AgentToolFault
from medops.application.agent_tool_results import (
    AgentFact,
    AgentToolOutcome,
    EvidenceView,
    ExtractionPayload,
    ReadPayload,
    SearchPayload,
    ToolPayload,
)
from medops.core.canonical import canonical_hash
from medops.core.deadline import CURRENT_DEADLINE, DeadlineExceeded, check_deadline, deadline_scope, execution_admission
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.core.money import usd_to_microusd
from medops.core.telemetry import run_metadata
from medops.domain.agent_actions import (
    ExtractAEAction,
    PlannerProposal,
    ReadEvidenceAction,
    SearchDocumentsAction,
    VerifyCitationsAction,
)
from medops.domain.agent_execution import AgentContext, BoundAction, EvidenceHandle, ObservationKind, PVAgentRun
from medops.domain.safety import SafetyDecision
from medops.harness.audit import ExecutionAudit, ExecutionAuditSnapshot
from medops.harness.retrieval_port import RetrievalRequest
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.execution_budget import (
    EXECUTION_BUDGET_VERSION,
    BudgetProtection,
    check_execution_budget,
    current_budget,
)
from medops.infrastructure.llm.gateway import BudgetExceeded
from medops.infrastructure.llm.meter import MeteredGateway
from medops.safety.checks import SAFETY_VERSION, check_input, screen_evidence
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillContext, SkillRegistry
from medops.verification.verifier import VERIFIER_VERSION

log = logging.getLogger(__name__)
TOOL_VERSION = "pv-tools-v2+protected-headroom"
TOOL_ACTIONS = frozenset({"extract_ae", "search_documents", "read_evidence", "verify_citations"})
SEARCH_EXCERPT_CHARS = 500
READ_MAX_CHARS = 8000


def tool_contract_sha256(registry: SkillRegistry | None = None) -> str:
    return canonical_hash(
        {
            "version": TOOL_VERSION,
            "execution_budget": EXECUTION_BUDGET_VERSION,
            "safety": SAFETY_VERSION,
            "verifier": VERIFIER_VERSION,
            "planner_schema": PlannerProposal.model_json_schema(),
            "result_schema": AgentToolOutcome.model_json_schema(),
            "search_excerpt_chars": SEARCH_EXCERPT_CHARS,
            "read_max_chars": READ_MAX_CHARS,
            "skills_sha256": (registry or default_registry()).agent_adapter().contract_sha256(),
        }
    )


class AgentTools:
    def __init__(
        self,
        *,
        context: AgentContext,
        facts: AgentFacts,
        registry: SkillRegistry,
        skill_context: SkillContext,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.context = AgentContext.model_validate(context.model_dump(mode="python"))
        self.facts, self.registry, self.skill_context, self.clock = facts, registry, skill_context, clock
        self._journal = ExecutionAudit()  # one isolated journal per action; Registry binds its own Skill call
        self.skill_context = replace(skill_context, deps=replace(skill_context.deps, audit=self._journal))
        self._used = False
        self._binding = context_binding(self.context)
        if self.context.versions.tool_contract_sha256 != tool_contract_sha256(registry):
            raise AgentToolFault("dependency_error")
        if (
            skill_context.user != context.principal
            or skill_context.versions != context.versions.versions
            or skill_context.trace_id != context.identity.trace_id
            or skill_context.run_id != str(context.identity.run_id)
            or skill_context.query_context != context.query_context
            or not isinstance(skill_context.deps.gateway, MeteredGateway)
        ):
            raise AgentToolFault("dependency_error")
        self._skills = registry.agent_adapter()
        self._skills.validate_versions(skill_context.versions.skill_version_set)
        self.meter = skill_context.deps.gateway

    def execute(
        self, action: BoundAction, *, run: PVAgentRun, evidence_registry: tuple[EvidenceHandle, ...] = ()
    ) -> AgentToolOutcome:
        if self._used:
            raise AgentToolFault("dependency_error")
        self._used = True  # no hidden retry/idempotency promise at the adapter boundary
        before = {r.call.call_id for r in self.meter.receipts}
        action = BoundAction.model_validate(action.model_dump(mode="python"))
        evidence_registry = tuple(EvidenceHandle.model_validate(h.model_dump(mode="python")) for h in evidence_registry)
        try:
            expected = admit_action(
                PlannerProposal(proposal=action.proposal).model_dump_json(),
                run=run,
                action_id=action.action_id,
                evidence_registry=evidence_registry,
                now=self.clock(),
            )
            action = BoundAction.model_validate(action.model_dump(mode="python"))
            if expected != action or action.binding != self._binding:
                raise AgentContractError("agent_binding_mismatch")
            if action.proposal.action not in TOOL_ACTIONS:
                return self._outcome(action, "invalid_action", before)
            if isinstance(action.proposal, (SearchDocumentsAction, ReadEvidenceAction)):
                self._journal.bind(self.context.identity.trace_id, self.context.principal.user_id)
            self._journal.record_event("agent_tool_action", action.model_dump(mode="json"))
            self._require_parent(run)
            self._run_expiry = run.expires_at
            timeout = 20 if isinstance(action.proposal, SearchDocumentsAction) else 60
            remaining = (run.expires_at - self.clock()).total_seconds()
            with (
                deadline_scope(min(timeout, remaining)),
                execution_admission(),
                run_metadata(
                    self.context.identity.trace_id,
                    self.context.versions.versions.model_dump(mode="json"),
                    kind="agent_tool",
                ),
                call_scope(
                    run_id=str(self.context.identity.run_id),
                    attempt_id=f"{self.context.identity.attempt_id}/action:{action.action_id}",
                    before_call=lambda: self._before_call(action),
                ),
            ):
                check_deadline()
                self.facts.check(self.context)
                texts = [self.context.narrative]
                if isinstance(action.proposal, SearchDocumentsAction):
                    texts.append(action.proposal.query)
                if isinstance(action.proposal, VerifyCitationsAction):
                    texts.extend(c.text for c in action.proposal.claims)
                if any(check_input(t).decision is not SafetyDecision.allow for t in texts):
                    raise AgentToolFault("unsupported")
                payload, issued, observed = self._dispatch(action, evidence_registry)
                check_deadline()
                check_execution_budget()
                self.meter.call_journal.ensure_complete()
                # This is the last DB read/fence; caller must store and commit before another action.
                self.facts.final_check(
                    self.context, observed, check_sources=not isinstance(action.proposal, ExtractAEAction)
                )
                check_deadline()
                check_execution_budget()
                kind: ObservationKind = "ok"
                if isinstance(payload, SearchPayload) and not payload.matches:
                    kind = "empty"
                if isinstance(payload, ExtractionPayload) and (not payload.elements or payload.unaligned_elements):
                    kind = "unsupported"
                if kind != "ok":
                    issued = ()
                return self._outcome(action, kind, before, payload=payload, issued=issued)
        except AgentContractError as exc:
            errors: dict[str, ObservationKind] = {
                "agent_deadline": "timeout",
                "agent_budget_exhausted": "budget_exceeded",
                "agent_final_reserve": "budget_exceeded",
                "agent_handle_unavailable": "denied_or_unavailable",
            }
            return self._outcome(action, errors.get(exc.code, "invalid_action"), before)
        except AgentToolFault as exc:
            return self._outcome(action, exc.kind, before)
        except (DeadlineExceeded, TimeoutError):
            return self._outcome(action, "timeout", before)
        except BudgetExceeded:
            return self._outcome(action, "budget_exceeded", before)
        except InfrastructureError as exc:
            if exc.code is ErrorCode.dependency_timeout:
                return self._outcome(action, "timeout", before)
            return self._outcome(
                action,
                "dependency_error",
                before,
                retryable=exc.retryable and exc.code is ErrorCode.dependency_unavailable,
            )
        except BusinessError as exc:
            if exc.code in (ErrorCode.forbidden, ErrorCode.unauthenticated, ErrorCode.not_found):
                return self._outcome(action, "denied_or_unavailable", before)
            return self._outcome(action, "dependency_error", before)
        except Exception as exc:  # noqa: BLE001 - private boundary; no exception text/body reaches the planner
            frames = traceback.extract_tb(exc.__traceback__)[-3:]
            log.warning(
                "agent_tool_failure type=%s location=%s",
                type(exc).__name__,
                [(f.filename, f.lineno, f.name) for f in frames],
            )
            retryable = (
                isinstance(exc, InfrastructureError) and exc.retryable and exc.code is ErrorCode.dependency_unavailable
            )
            return self._outcome(action, "dependency_error", before, retryable=retryable)

    def audit_snapshot(self) -> ExecutionAuditSnapshot:
        """Restricted bodies for AGENT-06 persistence; never project this to a planner/telemetry."""
        self._journal.ensure_complete()
        return self._journal.snapshot()

    def _before_call(self, action: BoundAction) -> None:
        check_deadline()
        check_execution_budget()
        self.facts.check(self.context)
        if not isinstance(action.proposal, ExtractAEAction):
            self.facts.sources(self.context)

    def _require_parent(self, run: PVAgentRun) -> None:
        budget = current_budget()
        if budget is None or CURRENT_DEADLINE.get() is None:
            raise AgentToolFault("dependency_error")
        snapshot = budget.snapshot()
        profile = self.context.profile
        if (
            snapshot.limits.token_limit > profile.token_cap
            or usd_to_microusd(snapshot.limits.cost_limit_usd) > profile.cost_cap_microusd
            or snapshot.limits.timeout_s > profile.timeout_ms / 1000
        ):
            raise AgentToolFault("dependency_error")
        b = run.budget
        if (b.accounted_tokens, b.reserved_tokens, b.accounted_cost_microusd, b.reserved_cost_microusd) != (
            snapshot.accounted_tokens,
            snapshot.reserved_tokens,
            usd_to_microusd(snapshot.accounted_cost_usd),
            usd_to_microusd(snapshot.reserved_cost_usd),
        ):
            raise AgentToolFault("dependency_error")
        budget.protect_remaining(
            BudgetProtection(
                tokens=profile.final_reserve_tokens, cost_usd=profile.final_reserve_cost_microusd / 1_000_000
            )
        )
        check_deadline()
        check_execution_budget()

    def _outcome(
        self,
        action: BoundAction,
        kind: ObservationKind,
        before: set[str],
        *,
        payload: ToolPayload | None = None,
        issued: tuple[EvidenceHandle, ...] = (),
        retryable: bool = False,
    ) -> AgentToolOutcome:
        return AgentToolOutcome(
            action_id=action.action_id,
            binding=self._binding,
            kind=kind,
            payload=payload,
            issued_handles=issued,
            new_handles_issued=bool(issued),
            retryable=retryable,
            call_receipt_ids=tuple(
                r.call.call_id
                for r in self.meter.receipts
                if r.call.call_id not in before
                and r.call.run_id == str(self.context.identity.run_id)
                and f"action:{action.action_id}" in (r.call.attempt_id or "").split("/")
            ),
        )

    def _dispatch(
        self, action: BoundAction, registry: tuple[EvidenceHandle, ...]
    ) -> tuple[ToolPayload, tuple[EvidenceHandle, ...], tuple[AgentFact, ...]]:
        proposal = action.proposal
        if isinstance(proposal, ExtractAEAction):
            return self._skills.extract(self.context, self.skill_context)
        self.facts.sources(self.context)
        if isinstance(proposal, SearchDocumentsAction):
            result = self.skill_context.deps.retrieval.retrieve(
                RetrievalRequest(
                    query=proposal.query,
                    user=self.context.principal,
                    as_of=self.context.query_context.as_of,
                    historical_requested=self.context.query_context.historical_requested,
                    source_document_ids=tuple(s.doc_id for s in self.context.source_scope.allowed_sources),
                )
            )
            facts = self.facts.lookup(self.context, tuple(e.citation.chunk_id for e in result.evidence))
            if tuple(f.evidence for f in facts) != result.evidence:
                raise AgentToolFault("denied_or_unavailable")
            visible, flagged = screen_evidence(tuple(f.evidence for f in facts))
            self._journal.observe(visible, flagged)
            facts = tuple(f for f in facts if f.evidence in visible)
            views, issued = self._views(facts, registry, SEARCH_EXCERPT_CHARS)
            return SearchPayload(matches=views), issued, facts
        by_handle = {h.handle: h for h in registry}
        if isinstance(proposal, ReadEvidenceAction):
            old = by_handle[proposal.handle]
            # Revalidate original even when the next block is independently visible.
            original = self.facts.lookup(self.context, (old.evidence.citation.chunk_id,))
            if original != (AgentFact(evidence=old.evidence, source_sha256=old.source_sha256),):
                raise AgentToolFault("denied_or_unavailable")
            fact = self.facts.read(self.context, old.evidence, proposal.region)
            if fact is None:
                raise AgentToolFault("denied_or_unavailable")
            if len(fact.evidence.text) > READ_MAX_CHARS:
                raise AgentToolFault("unsupported")
            visible, flagged = screen_evidence((fact.evidence,))
            self._journal.observe(visible, flagged)
            if not visible:
                raise AgentToolFault("unsupported")
            views, issued = self._views((fact,), registry, READ_MAX_CHARS)
            return ReadPayload(evidence=views[0]), issued, tuple(dict.fromkeys((*original, fact)))
        if isinstance(proposal, VerifyCitationsAction):
            return self._skills.verify(proposal, self.context, by_handle, self.skill_context, self.facts)
        raise AgentToolFault("unsupported")

    def _views(
        self, facts: tuple[AgentFact, ...], registry: tuple[EvidenceHandle, ...], limit: int
    ) -> tuple[tuple[EvidenceView, ...], tuple[EvidenceHandle, ...]]:
        views = []
        issued = []
        for fact in facts:
            candidates = [
                h
                for h in registry
                if h.binding == self._binding
                and h.evidence == fact.evidence
                and h.source_sha256 == fact.source_sha256
                and h.expires_at > self.clock()
            ]
            record = (
                candidates[0]
                if candidates
                else EvidenceHandle(
                    handle=uuid4(),
                    binding=self._binding,
                    source_sha256=fact.source_sha256,
                    evidence=fact.evidence,
                    expires_at=self._run_expiry,
                )
            )
            if not candidates:
                issued.append(record)
            excerpt = fact.evidence.text[:limit]
            views.append(
                EvidenceView(
                    handle=record.handle,
                    citation=fact.evidence.citation,
                    text=excerpt,
                    char_end=len(excerpt),
                    truncated=len(excerpt) < len(fact.evidence.text),
                    evidence_text_sha256=fact.evidence.evidence_text_hash,
                    source_sha256=fact.source_sha256,
                )
            )
        if len(registry) + len(issued) > 64:
            raise AgentToolFault("unsupported")
        return tuple(views), tuple(issued)
