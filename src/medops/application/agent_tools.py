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

from medops.application.agent_contracts import AgentContractError, admit_action, context_binding, validate_run_snapshot
from medops.application.agent_final_budget import FINAL_CITATION_BUDGET_VERSION, FinalCitationBudgetResult
from medops.application.agent_final_gate import (
    FinalGateConfig,
    check_final_plan,
    check_structure,
    material_request,
    parse_material_check,
)
from medops.application.agent_tool_ports import AgentFacts, AgentToolFault
from medops.application.agent_tool_results import (
    AgentFact,
    AgentToolOutcome,
    EvidenceView,
    ExtractionPayload,
    ReadPayload,
    SearchPayload,
    ToolPayload,
    VerificationPayload,
)
from medops.core.canonical import canonical_hash
from medops.core.deadline import CURRENT_DEADLINE, DeadlineExceeded, check_deadline, deadline_scope, execution_admission
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.core.money import usd_to_microusd
from medops.core.strict_json import strict_json
from medops.core.telemetry import run_metadata
from medops.domain.agent_actions import (
    ExtractAEAction,
    FinishAction,
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
from medops.infrastructure.llm.call_plan import CALL_PLAN_VERSION, ModelCallPlan
from medops.infrastructure.llm.execution_budget import (
    EXECUTION_BUDGET_VERSION,
    BudgetProtection,
    check_execution_budget,
    current_budget,
    finalization_scope,
)
from medops.infrastructure.llm.gateway import BudgetExceeded
from medops.infrastructure.llm.meter import MeteredGateway
from medops.safety.checks import SAFETY_VERSION, check_input, screen_evidence
from medops.skills.catalog import default_registry
from medops.skills.registry import MAX_RETRIES, SkillContext, SkillRegistry
from medops.verification.verifier import VERIFIER_VERSION

log = logging.getLogger(__name__)
TOOL_VERSION = "pv-tools-v4+final-citation-budget"
TOOL_ACTIONS = frozenset({"extract_ae", "search_documents", "read_evidence", "verify_citations"})
SEARCH_EXCERPT_CHARS = 500
READ_MAX_CHARS = 8000


def tool_contract_sha256(registry: SkillRegistry | None = None) -> str:
    return canonical_hash(
        {
            "version": TOOL_VERSION,
            "execution_budget": EXECUTION_BUDGET_VERSION,
            "model_call_plan": CALL_PLAN_VERSION,
            "final_citation_budget": FINAL_CITATION_BUDGET_VERSION,
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
                plan = self._model_plan(action, evidence_registry)
                self._journal.record_event("agent_tool_budget_plan", plan.audit_record(self.meter.execution_prices))
                budget = current_budget()
                if budget is None:
                    raise AgentToolFault("dependency_error")
                if not budget.fits(plan.estimate(self.meter.execution_prices)):
                    raise BudgetExceeded("agent_tool_plan_exceeds_budget")
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

    def verify_final_citations(
        self,
        action: BoundAction,
        *,
        run: PVAgentRun,
        evidence_registry: tuple[EvidenceHandle, ...],
        final_config: FinalGateConfig | None = None,
    ) -> FinalCitationBudgetResult:
        """Trusted final-owner entry, deliberately absent from the planner's tools.

        The finish decision is already consumed. Keep original root quota/time,
        pin the real draft's requests and retry bound, then seal ordinary model
        admission permanently. Exceptions propagate to the trusted terminal owner;
        a result proves citation checks only, never completed business/persistence.
        """
        if self._used:
            raise AgentToolFault("dependency_error")
        self._used = True
        run = validate_run_snapshot(run)
        action = BoundAction.model_validate(action.model_dump(mode="python", warnings=False))
        evidence_registry = tuple(
            EvidenceHandle.model_validate(h.model_dump(mode="python", warnings=False)) for h in evidence_registry
        )
        if (
            not isinstance(action.proposal, FinishAction)
            or run.decisions_consumed != action.decision_index
            or action.binding != self._binding
            or context_binding(run.context) != self._binding
        ):
            raise AgentContractError("agent_binding_mismatch")
        expected = admit_action(
            PlannerProposal(proposal=action.proposal).model_dump_json(),
            run=run.model_copy(update={"decisions_consumed": run.decisions_consumed - 1}),
            action_id=action.action_id,
            evidence_registry=evidence_registry,
            now=self.clock(),
        )
        if expected != action:
            raise AgentContractError("agent_binding_mismatch")
        self._require_parent(run)
        before = {r.call.call_id for r in self.meter.receipts}
        remaining = (run.expires_at - self.clock()).total_seconds()
        with (
            deadline_scope(min(60, remaining)),
            execution_admission(),
            run_metadata(
                self.context.identity.trace_id,
                self.context.versions.versions.model_dump(mode="json"),
                kind="agent_final_citations",
            ),
            call_scope(
                run_id=str(self.context.identity.run_id),
                attempt_id=f"{self.context.identity.attempt_id}/final:{action.action_id}",
                before_call=lambda: (
                    self._before_final_call(action, evidence_registry)
                    if final_config is not None
                    else self._before_call(action)
                ),
            ),
        ):
            if final_config is not None:
                self._before_final_call(action, evidence_registry)
            else:
                self._before_call(action)
            if any(
                check_input(t).decision is not SafetyDecision.allow
                for t in (self.context.narrative, *(c.text for c in action.proposal.draft.guideline_claims))
            ):
                raise AgentToolFault("unsupported")
            by_handle = {h.handle: h for h in evidence_registry}
            claims = action.proposal.draft.guideline_claims
            verifying = (
                VerifyCitationsAction(action="verify_citations", rationale="Final citation check", claims=claims)
                if claims
                else None
            )
            attempt_limit = (
                final_config.citation_attempts
                if final_config and final_config.citation_attempts < 1 + MAX_RETRIES
                else None
            )
            plan = (
                self._skills.plan_verify(
                    verifying, self.context, by_handle, self.skill_context, self.facts, attempt_limit=attempt_limit
                )
                if verifying
                else ModelCallPlan()
            )
            review_request = None
            if final_config is not None:
                check_structure(self.context, action.proposal.draft)
                check_final_plan(plan, final_config)
                review_request = material_request(
                    self.context, action.proposal.draft, final_config, evidence_registry=evidence_registry
                )
                if any(
                    check_input(f.value).decision is not SafetyDecision.allow
                    for f in action.proposal.draft.narrative_facts
                ):
                    raise AgentToolFault("unsupported")
            material_check = None
            self._journal.record_event("agent_final_citation_action", action.model_dump(mode="json"))
            self._journal.record_event(
                "agent_final_citation_budget_plan", plan.audit_record(self.meter.execution_prices)
            )
            # Expanded original attempt bound, not new retries or a new execution allowance.
            payload: VerificationPayload | None
            requests = plan.requests * plan.max_attempts + ((review_request,) if review_request is not None else ())
            with finalization_scope(requests, prices=self.meter.execution_prices) as profile:
                self._journal.record_event("agent_final_citation_budget_profile", profile.model_dump(mode="json"))
                if verifying is not None:
                    payload, _, observed = self._skills.verify(
                        verifying, self.context, by_handle, self.skill_context, self.facts, attempt_limit=attempt_limit
                    )
                else:
                    self._journal.bind(self.context.identity.trace_id, self.context.principal.user_id)
                    payload, observed = None, ()
                if review_request is not None and final_config is not None:
                    response = self.meter.complete(review_request)
                    try:
                        data = strict_json(response.text)
                    except (ValueError, TypeError):
                        raise AgentToolFault("dependency_error") from None
                    if response.truncated:
                        raise AgentToolFault("dependency_error")
                    try:
                        material_check = parse_material_check(
                            data,
                            self.context,
                            action.proposal.draft,
                            final_config,
                            original_citations_supported=payload is None
                            or all(c.verdict.value == "supported" for c in payload.checks),
                        )
                    except (ValueError, TypeError):
                        raise AgentToolFault("dependency_error") from None
                    self._journal.record_event(
                        "agent_final_material_checked",
                        material_check.model_dump(mode="json"),
                    )
                check_deadline()
                check_execution_budget()
                self.meter.call_journal.ensure_complete()
                receipt_ids = self._final_receipt_ids(
                    action, before, final_model_id=final_config.model_id if final_config else None
                )
                self._journal.record_event(
                    "agent_final_citations_checked",
                    payload.model_dump(mode="json")
                    if payload is not None
                    else {"claims_checked": 0, "no_guideline_claims": True},
                )
                self.facts.final_check(self.context, observed)
                check_deadline()
                check_execution_budget()
        budget = current_budget()
        if budget is None:
            raise AgentToolFault("dependency_error")
        return FinalCitationBudgetResult(
            action_id=action.action_id,
            binding=self._binding,
            draft_sha256=canonical_hash(action.proposal.draft.model_dump(mode="json")),
            payload=payload,
            profile=profile,
            budget=budget.snapshot(),
            call_receipt_ids=receipt_ids,
            material_check=material_check,
        )

    def _final_receipt_ids(
        self, action: BoundAction, before: set[str], *, final_model_id: str | None = None
    ) -> tuple[str, ...]:
        requests = {e["call_id"]: e["request"]["call"] for e in self.meter.call_journal.snapshot()}
        owned_ids = []
        for receipt in self.meter.receipts:
            call = receipt.call
            if call.call_id in before:
                continue
            recorded = requests.get(call.call_id)
            if recorded is None or call.model_dump(mode="json", exclude={"reservation_id"}) != {
                k: v for k, v in recorded.items() if k != "reservation_id"
            }:
                raise AgentToolFault("dependency_error")
            owned = (
                call.run_id == str(self.context.identity.run_id)
                and call.trace_id == self.context.identity.trace_id
                and f"final:{action.action_id}" in (call.attempt_id or "").split("/")
                and (
                    (call.purpose == "verify" and call.requested_model == self.skill_context.deps.judge_model_id)
                    or (
                        call.purpose == "agent_final_material"
                        and final_model_id is not None
                        and call.requested_model == final_model_id
                    )
                )
            )
            if receipt.provider_started and not owned:
                raise AgentToolFault("dependency_error")
            if owned:
                owned_ids.append(call.call_id)
        return tuple(owned_ids)

    def audit_snapshot(self) -> ExecutionAuditSnapshot:
        """Restricted bodies for AGENT-06 persistence; never project this to a planner/telemetry."""
        self._journal.ensure_complete()
        return self._journal.snapshot()

    def _before_final_call(self, action: BoundAction, registry: tuple[EvidenceHandle, ...]) -> None:
        self._before_call(action)
        if not isinstance(action.proposal, FinishAction):
            raise AgentToolFault("dependency_error")
        by_handle = {h.handle: h for h in registry}
        wanted = tuple(dict.fromkeys(h for c in action.proposal.draft.guideline_claims for h in c.evidence_handles))
        expected = {
            by_handle[h].evidence.citation.chunk_id: AgentFact(
                evidence=by_handle[h].evidence, source_sha256=by_handle[h].source_sha256
            )
            for h in wanted
        }
        current = (
            {f.evidence.citation.chunk_id: f for f in self.facts.lookup(self.context, tuple(expected))}
            if expected
            else {}
        )
        if current != expected:
            raise AgentToolFault("denied_or_unavailable")

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

    def _search_request(self, proposal: SearchDocumentsAction) -> RetrievalRequest:
        return RetrievalRequest(
            query=proposal.query,
            user=self.context.principal,
            as_of=self.context.query_context.as_of,
            historical_requested=self.context.query_context.historical_requested,
            source_document_ids=tuple(s.doc_id for s in self.context.source_scope.allowed_sources),
        )

    def _model_plan(self, action: BoundAction, registry: tuple[EvidenceHandle, ...]) -> ModelCallPlan:
        proposal = action.proposal
        if isinstance(proposal, ExtractAEAction):
            return self._skills.plan_extract(self.context, self.skill_context)
        self.facts.sources(self.context)
        if isinstance(proposal, SearchDocumentsAction):
            preview = getattr(self.skill_context.deps.retrieval, "model_requests", None)
            if not callable(preview):
                raise AgentToolFault("dependency_error")
            return ModelCallPlan(requests=tuple(preview(self._search_request(proposal))))
        if isinstance(proposal, VerifyCitationsAction):
            return self._skills.plan_verify(
                proposal, self.context, {h.handle: h for h in registry}, self.skill_context, self.facts
            )
        return ModelCallPlan()  # read_evidence performs no hosted model work

    def _dispatch(
        self, action: BoundAction, registry: tuple[EvidenceHandle, ...]
    ) -> tuple[ToolPayload, tuple[EvidenceHandle, ...], tuple[AgentFact, ...]]:
        proposal = action.proposal
        if isinstance(proposal, ExtractAEAction):
            return self._skills.extract(self.context, self.skill_context)
        self.facts.sources(self.context)
        if isinstance(proposal, SearchDocumentsAction):
            result = self.skill_context.deps.retrieval.retrieve(self._search_request(proposal))
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
