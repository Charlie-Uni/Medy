"""Pure PV action admission; no tools, models, authentication or state mutation.

Only a trusted server may supply the run, action ID, registry and current time.
Accepting a proposal neither performs an action nor marks the task completed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeVar
from uuid import UUID

from medops.core.canonical import canonical_hash
from medops.core.strict_json import strict_json
from medops.domain.agent_actions import (
    AgentModel,
    ClarifyAction,
    EscalateAction,
    ExtractAEAction,
    FinishAction,
    GuidelineClaim,
    PlannerProposal,
    ReadEvidenceAction,
    ReviewDraft,
    VerifyCitationsAction,
)
from medops.domain.agent_execution import (
    AgentBinding,
    AgentContext,
    AgentObservation,
    BoundAction,
    EvidenceHandle,
    PVAgentRun,
    utc_time,
)

Failure = Literal[
    "invalid_agent_payload",
    "invalid_agent_metadata",
    "agent_payload_limit",
    "agent_binding_mismatch",
    "agent_handle_unavailable",
    "agent_not_running",
    "agent_deadline",
    "agent_step_limit",
    "agent_budget_exhausted",
    "agent_final_reserve",
]
MAX_PLANNER_BYTES = 65536
T = TypeVar("T", bound=AgentModel)


class AgentContractError(ValueError):
    def __init__(self, code: Failure):
        self.code = code
        super().__init__(code)


def _validated(model: type[T], value: T) -> T:
    try:
        return model.model_validate(value.model_dump(mode="python", warnings=False))
    except (ValueError, TypeError, AttributeError):
        raise AgentContractError("invalid_agent_metadata") from None


def context_binding(context: AgentContext) -> AgentBinding:
    context = _validated(AgentContext, context)
    identity = context.identity
    try:
        digest = canonical_hash(context.model_dump(mode="json"))
    except (ValueError, TypeError, RecursionError):
        raise AgentContractError("invalid_agent_metadata") from None
    return AgentBinding(
        case_id=identity.case_id,
        task_id=identity.task_id,
        run_id=identity.run_id,
        attempt_id=identity.attempt_id,
        conditions_sha256=digest,
    )


def validate_run_snapshot(run: PVAgentRun) -> PVAgentRun:
    run = _validated(PVAgentRun, run)
    binding = context_binding(run.context)
    if run.terminal is not None and run.terminal.binding != binding:
        raise AgentContractError("agent_binding_mismatch")
    return run


def _claims_handles(claims: tuple[GuidelineClaim, ...], context: AgentContext) -> set[UUID]:
    allowed = {r.requirement_id for r in context.requirements if r.kind == "guideline"}
    if any(c.requirement_id not in allowed for c in claims):
        raise AgentContractError("invalid_agent_payload")
    return {h for c in claims for h in c.evidence_handles}


def _draft_handles(draft: ReviewDraft, context: AgentContext) -> set[UUID]:
    kinds = {r.requirement_id: r.kind for r in context.requirements}
    if not set(draft.missing_requirement_ids) <= kinds.keys():
        raise AgentContractError("invalid_agent_payload")
    for fact in draft.narrative_facts:
        if (
            kinds.get(fact.requirement_id) != "narrative"
            or context.narrative[fact.char_start : fact.char_end] != fact.quote
        ):
            raise AgentContractError("invalid_agent_payload")
    return _claims_handles(draft.guideline_claims, context)


def admit_action(
    body: str | bytes,
    *,
    run: PVAgentRun,
    action_id: UUID,
    evidence_registry: tuple[EvidenceHandle, ...],
    now: datetime,
) -> BoundAction:
    """Validate using the number of PRIOR attempts; caller must charge this attempt even on failure.

    This function does NOT increment the decision counter, authenticate the caller,
    check cancellation/lease or reserve provider usage. AGENT-02/03/04 must do so.
    """
    run = validate_run_snapshot(run)
    try:
        now = utc_time(now)
    except (ValueError, TypeError, AttributeError):
        raise AgentContractError("invalid_agent_metadata") from None
    if not isinstance(action_id, UUID):
        raise AgentContractError("invalid_agent_metadata")
    if run.status != "running":
        raise AgentContractError("agent_not_running")
    if now < run.started_at or now >= run.expires_at:
        raise AgentContractError("agent_deadline")
    if run.decisions_consumed >= run.context.profile.max_decision_steps:
        raise AgentContractError("agent_step_limit")
    budget, profile = run.budget, run.context.profile
    remaining_tokens = profile.token_cap - budget.accounted_tokens - budget.reserved_tokens
    remaining_cost = profile.cost_cap_microusd - budget.accounted_cost_microusd - budget.reserved_cost_microusd
    if remaining_tokens <= 0 or remaining_cost <= 0:
        raise AgentContractError("agent_budget_exhausted")
    try:
        if not isinstance(body, (str, bytes)):
            raise AgentContractError("invalid_agent_payload")
        if len(body) > MAX_PLANNER_BYTES:
            raise AgentContractError("agent_payload_limit")
        raw = body.encode("utf-8") if isinstance(body, str) else body
        if len(raw) > MAX_PLANNER_BYTES:
            raise AgentContractError("agent_payload_limit")
        action = PlannerProposal.model_validate(strict_json(raw)).proposal
        # Ensure private unpaired surrogates cannot leak from later canonical encoding.
        action.model_dump_json().encode("utf-8")
    except AgentContractError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise AgentContractError("invalid_agent_payload") from None
    if not isinstance(action, (FinishAction, ClarifyAction, EscalateAction)) and (
        remaining_tokens <= profile.final_reserve_tokens or remaining_cost <= profile.final_reserve_cost_microusd
    ):
        raise AgentContractError("agent_final_reserve")
    context = run.context
    needed: set[UUID] = set()
    if isinstance(action, ExtractAEAction) and action.source_type != context.source_type:
        raise AgentContractError("invalid_agent_payload")
    if isinstance(action, ReadEvidenceAction):
        needed.add(action.handle)
    elif isinstance(action, VerifyCitationsAction):
        needed = _claims_handles(action.claims, context)
    elif isinstance(action, (FinishAction, EscalateAction)):
        needed = _draft_handles(action.draft, context)
    elif isinstance(action, ClarifyAction):
        if not {q.field for q in action.questions} <= set(context.clarifiable_fields):
            raise AgentContractError("invalid_agent_payload")
    binding = context_binding(context)
    if len(evidence_registry) > 64:
        raise AgentContractError("invalid_agent_metadata")
    registry = tuple(_validated(EvidenceHandle, h) for h in evidence_registry)
    by_handle = {h.handle: h for h in registry}
    if len(by_handle) != len(registry):
        raise AgentContractError("invalid_agent_metadata")
    allowed_sources = {(s.doc_id, s.version, s.source_sha256) for s in context.source_scope.allowed_sources}
    for handle in needed:
        record = by_handle.get(handle)
        if record is None or record.binding != binding or record.expires_at <= now:
            raise AgentContractError("agent_handle_unavailable")
        evidence = record.evidence
        if (evidence.citation.doc_id, evidence.citation.version, record.source_sha256) not in allowed_sources:
            raise AgentContractError("agent_handle_unavailable")
        if evidence.citation.effective_date > context.query_context.as_of or (
            evidence.historical and not context.query_context.historical_requested
        ):
            raise AgentContractError("agent_handle_unavailable")
    return BoundAction(action_id=action_id, binding=binding, decision_index=run.decisions_consumed + 1, proposal=action)


def validate_observation(action: BoundAction, observation: AgentObservation) -> AgentObservation:
    action = _validated(BoundAction, action)
    observation = _validated(AgentObservation, observation)
    if (
        action.action_id != observation.action_id
        or action.binding != observation.binding
        or action.proposal.action != observation.action
    ):
        raise AgentContractError("agent_binding_mismatch")
    return observation
