"""Restricted, reconstructible loop images; serialization never grants execution.

Only committed observations are replayed, without tools/providers. Pending work
and every handoff remain closed. A durable driver must authenticate storage and
bind this image to its lease, original budget handoff and actual call journal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from medops.application.agent_contracts import Failure, admit_action, context_binding, validate_run_snapshot
from medops.application.agent_loop_ports import LoopPhase
from medops.application.agent_loop_validation import validate_tool_commit
from medops.application.agent_planning import PlannerConfig, PlanningBoard, planning_prompt_sha256
from medops.application.agent_progress import AgentProgress
from medops.application.agent_tool_results import AgentToolOutcome
from medops.application.agent_tools import tool_contract_sha256
from medops.core.canonical import canonical_json
from medops.core.strict_json import strict_json
from medops.domain.agent_actions import AgentModel, ClarifyAction, EscalateAction, FinishAction
from medops.domain.agent_execution import AgentBudget, BoundAction, EvidenceHandle, PVAgentRun, StopReason, utc_time

LOOP_STATE_VERSION: Final = "pv-loop-state-v2+terminal-admission-budget"
MAX_LOOP_STATE_BYTES = 2 * 1024 * 1024
FATAL_OUTCOMES: dict[str, StopReason] = {
    "dependency_error": "dependency_error",
    "timeout": "timeout",
    "budget_exceeded": "budget_exceeded",
    "cancelled": "cancelled",
    "lease_lost": "lease_lost",
}


class CommittedDecision(AgentModel):
    """One counted decision, not a provider receipt or proof of a database commit."""

    decision_id: UUID
    decision_index: int = Field(ge=1, le=8, strict=True)
    admitted_at: datetime
    observed_at: datetime
    admission_budget: AgentBudget
    action: BoundAction | None
    outcome: AgentToolOutcome | None
    rejected: Failure | None

    _utc = field_validator("admitted_at", "observed_at")(utc_time)

    @model_validator(mode="after")
    def shape(self) -> CommittedDecision:
        if (
            self.admitted_at > self.observed_at
            or self.rejected in {"agent_budget_exhausted", "agent_final_reserve"}
            or ((self.rejected is None) != (self.action is not None and self.outcome is not None))
            or (self.rejected is not None and (self.action is not None or self.outcome is not None))
        ):
            raise ValueError("invalid_agent_loop_state")
        return self


class LoopState(AgentModel):
    # All fields required: missing history/cursor/stop markers must not default to a fresh run.
    version: Literal["pv-loop-state-v2+terminal-admission-budget"]
    run: PVAgentRun
    config: PlannerConfig
    phase: LoopPhase
    captured_at: datetime
    decision_id: UUID | None
    history: tuple[CommittedDecision, ...] = Field(max_length=8)
    stop_reason: StopReason | None
    terminal_request: BoundAction | None
    terminal_admitted_at: datetime | None
    terminal_admission_budget: AgentBudget | None

    _utc = field_validator("captured_at", "terminal_admitted_at")(
        lambda value: utc_time(value) if value is not None else None
    )

    @model_validator(mode="after")
    def shape(self) -> LoopState:
        run = validate_run_snapshot(self.run)
        if (
            run.status != "running"
            or self.captured_at < run.started_at
            or len({h.decision_id for h in self.history}) != len(self.history)
        ):
            raise ValueError("invalid_agent_loop_state")
        if [h.decision_index for h in self.history] != list(range(1, len(self.history) + 1)):
            raise ValueError("invalid_agent_loop_state")
        pending = run.decisions_consumed - len(self.history)
        if pending not in {0, 1}:
            raise ValueError("invalid_agent_loop_state")
        if self.phase in {"decision_started", "planning_returned"}:
            if pending != 1 or self.decision_id is None or self.decision_id in {h.decision_id for h in self.history}:
                raise ValueError("invalid_agent_loop_state")
        elif self.phase in {"tool_committed", "proposal_rejected"}:
            if pending or not self.history or self.decision_id != self.history[-1].decision_id:
                raise ValueError("invalid_agent_loop_state")
            if (self.phase == "proposal_rejected") != (self.history[-1].rejected is not None):
                raise ValueError("invalid_agent_loop_state")
        elif self.decision_id is not None:
            raise ValueError("invalid_agent_loop_state")
        if (self.phase == "handoff") != (self.stop_reason is not None):
            raise ValueError("invalid_agent_loop_state")
        terminal = self.terminal_request
        if (terminal is None) != (self.terminal_admitted_at is None):
            raise ValueError("invalid_agent_loop_state")
        if (terminal is None) != (self.terminal_admission_budget is None):
            raise ValueError("invalid_agent_loop_state")
        if terminal is not None:
            proposal = terminal.proposal
            reason = (
                "completed"
                if isinstance(proposal, FinishAction)
                else "clarification_required"
                if isinstance(proposal, ClarifyAction)
                else proposal.reason
                if isinstance(proposal, EscalateAction)
                else None
            )
            if (
                self.phase != "handoff"
                or pending != 1
                or reason != self.stop_reason
                or terminal.decision_index != run.decisions_consumed
                or terminal.binding != context_binding(run.context)
                or terminal.action_id in {h.decision_id for h in self.history}
            ):
                raise ValueError("invalid_agent_loop_state")
        elif self.stop_reason in {"completed", "clarification_required"}:
            raise ValueError("invalid_agent_loop_state")
        return self


@dataclass(frozen=True)
class RebuiltLoopState:
    board: PlanningBoard
    evidence_registry: tuple[EvidenceHandle, ...]
    outcomes: tuple[AgentToolOutcome, ...]
    progress: AgentProgress
    # None means structurally quiescent, NOT authorized to resume.
    blocked_reason: StopReason | None


def rebuild_loop_state(state: LoopState, *, expected_run: PVAgentRun, config: PlannerConfig) -> RebuiltLoopState:
    """Reconstruct planner input and repetition state, with no tools or model calls.

    expected_run/config must come from trusted storage/configuration. Equality and
    hashes do not authenticate an arbitrary caller-supplied image. Current facts,
    permissions, lease, deadline, receipt reconciliation and budget still need the
    production driver; this function deliberately returns no live execution root.
    """
    state = LoopState.model_validate(state.model_dump(mode="json"))
    expected_run = validate_run_snapshot(expected_run)
    if (
        state.run != expected_run
        or state.config != config
        or state.run.context.versions.planning_prompt_sha256 != planning_prompt_sha256()
        or state.run.context.versions.tool_contract_sha256 != tool_contract_sha256()
    ):
        raise ValueError("invalid_agent_loop_state")
    board, progress = PlanningBoard(), AgentProgress()
    registry: tuple[EvidenceHandle, ...] = ()
    outcomes: tuple[AgentToolOutcome, ...] = ()
    receipts: set[str] = set()
    previous_time = state.run.started_at
    previous_budget = AgentBudget(
        accounted_tokens=0, reserved_tokens=0, accounted_cost_microusd=0, reserved_cost_microusd=0
    )
    blocked: StopReason | None = None
    for record in state.history:
        if (
            blocked is not None
            or not previous_time <= record.admitted_at <= record.observed_at < state.run.expires_at
            or record.observed_at > state.captured_at
        ):
            raise ValueError("invalid_agent_loop_state")
        if any(
            getattr(record.admission_budget, k) < getattr(previous_budget, k)
            for k in ("accounted_tokens", "accounted_cost_microusd")
        ):
            raise ValueError("invalid_agent_loop_state")
        previous_time, previous_budget = record.observed_at, record.admission_budget
        if record.rejected is not None:
            board.observe(None, None)
            progress.reset()
            continue
        action, outcome = record.action, record.outcome
        if action is None or outcome is None:  # narrowed after revalidated closed shape
            raise ValueError("invalid_agent_loop_state")
        prior = state.run.model_copy(
            update={"decisions_consumed": record.decision_index - 1, "budget": record.admission_budget}
        )
        checked = admit_action(
            canonical_json({"proposal": action.proposal.model_dump(mode="json")}),
            run=prior,
            action_id=record.decision_id,
            evidence_registry=registry,
            now=record.admitted_at,
        )
        if checked != action or isinstance(action.proposal, (FinishAction, ClarifyAction, EscalateAction)):
            raise ValueError("invalid_agent_loop_state")
        _, registry = validate_tool_commit(action, outcome, state.run, registry, now=record.observed_at)
        if receipts.intersection(outcome.call_receipt_ids):
            raise ValueError("invalid_agent_loop_state")
        receipts.update(outcome.call_receipt_ids)
        outcomes += (outcome,)
        progress.observe(action, outcome, registry)
        board.observe(action, outcome)
        blocked = FATAL_OUTCOMES.get(outcome.kind)
        if blocked is None and progress.snapshot().consecutive >= state.run.context.profile.same_no_progress_limit:
            blocked = "no_progress"
    if any(
        getattr(state.run.budget, k) < getattr(previous_budget, k)
        for k in ("accounted_tokens", "accounted_cost_microusd")
    ):
        raise ValueError("invalid_agent_loop_state")
    if blocked is not None and state.run.decisions_consumed != len(state.history):
        raise ValueError("invalid_agent_loop_state")
    if state.terminal_request is not None:
        terminal = state.terminal_request
        when = state.terminal_admitted_at
        if when is None or not previous_time <= when <= state.captured_at:
            raise ValueError("invalid_agent_loop_state")
        admitted = admit_action(
            canonical_json({"proposal": terminal.proposal.model_dump(mode="json")}),
            run=state.run.model_copy(
                update={
                    "decisions_consumed": state.run.decisions_consumed - 1,
                    "budget": state.terminal_admission_budget,
                }
            ),
            action_id=terminal.action_id,
            evidence_registry=registry,
            now=when,
        )
        if terminal != admitted:
            raise ValueError("invalid_agent_loop_state")
    if state.phase == "handoff":
        blocked = state.stop_reason
    elif state.phase in {"decision_started", "planning_returned"}:
        blocked = "unsupported_recovery"  # never replay an uncertain planning/tool call
    elif blocked is None and state.run.decisions_consumed >= state.run.context.profile.max_decision_steps:
        blocked = "step_limit"
    return RebuiltLoopState(board, registry, outcomes, progress, blocked)


def encode_loop_state(state: LoopState) -> bytes:
    """Restricted plaintext; driver must encrypt before durable storage, never telemetry."""
    rebuild_loop_state(state, expected_run=state.run, config=state.config)
    body = canonical_json(state.model_dump(mode="json")).encode("utf-8")
    if len(body) > MAX_LOOP_STATE_BYTES:
        raise ValueError("invalid_agent_loop_state")
    return body


def decode_loop_state(body: bytes) -> LoopState:
    """Strict bounded decoding; hide validation input and provider/body exceptions."""
    try:
        if not isinstance(body, bytes) or not 0 < len(body) <= MAX_LOOP_STATE_BYTES:
            raise ValueError("invalid_agent_loop_state")
        state = LoopState.model_validate(strict_json(body))
        rebuild_loop_state(state, expected_run=state.run, config=state.config)
        return state
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise ValueError("invalid_agent_loop_state") from None
