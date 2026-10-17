"""Trusted transaction/audit boundary required by the internal PV decision loop.

No permissive/default driver: deployment must supply authenticated short
transactions, durable checkpoints and committed tool results (AGENT-04/06).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID

from medops.application.agent_progress import ProgressCheckpoint
from medops.application.agent_tool_results import AgentToolOutcome
from medops.domain.agent_execution import AgentContext, BoundAction, EvidenceHandle, PVAgentRun, StopReason
from medops.infrastructure.llm.execution_budget import BudgetProtection, ExecutionBudget
from medops.infrastructure.llm.gateway import ModelRequest, ModelResponse

if TYPE_CHECKING:
    from medops.application.agent_loop_state import LoopState
    from medops.application.agent_runtime_state import PlanningFrame

LoopPhase = Literal["decision_started", "planning_returned", "proposal_rejected", "tool_committed", "handoff"]


class AgentLoopAbort(ValueError):
    def __init__(self, reason: StopReason):
        if reason in {"completed", "clarification_required"}:
            raise ValueError("invalid_agent_abort")
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class LoopCheckpoint:
    """Restricted bodies, never planner input or ordinary telemetry.

    ModelRequest is the preflight request; MeteredGateway.call_journal retains
    actual adjusted timeout/SDK attempts. Keep both, never call them wire bytes.
    """

    phase: LoopPhase
    run: PVAgentRun
    decision_id: UUID | None = None
    request: ModelRequest | None = None
    response: ModelResponse | None = None
    action: BoundAction | None = None
    outcome: AgentToolOutcome | None = None
    receipt_ids: tuple[str, ...] = ()
    reason: str | None = None  # fixed error/stop code, no raw exception message
    # None means unbound: storage MUST preserve previous progress, never erase it.
    progress: ProgressCheckpoint | None = None  # hash-only, not durable recovery by itself
    budget_protection: BudgetProtection | None = None  # None preserves unbound/old storage state
    # Restricted complete image, not telemetry; None MUST preserve old storage.
    # No permission to replay pending calls or resume a stopped handoff.
    state: LoopState | None = None


class AgentLoopDriver(Protocol):
    def validate_recovery(self, state: LoopState, budget: ExecutionBudget) -> PlanningFrame | None:
        """Attest the consumed encrypted head and exact root object, with current facts/lease.

        A frame without a receipt may be returned ONLY if there is no admitted
        call for it. A known response is reused without another model call.
        """
        ...

    def check_access(self, context: AgentContext, evidence_registry: tuple[EvidenceHandle, ...]) -> None:
        """Current identity/conditions/ownership AND all projected evidence; close transaction before return."""
        ...

    def checkpoint(self, event: LoopCheckpoint) -> None:
        """Synchronous, fail closed. decision_started must consume the step before a model call.

        Enforce identity, run/attempt and expected decision revision atomically.
        Do not hold a DB transaction/lock after returning. No-op implementations
        are test fixtures only, not production implementations of this contract.
        """
        ...

    def execute_tool(
        self,
        action: BoundAction,
        *,
        admission_run: PVAgentRun,
        admitted_at: datetime,
        evidence_registry: tuple[EvidenceHandle, ...],
    ) -> AgentToolOutcome:
        """Fresh AGENT-02 adapter; save restricted result/audit under its fence and COMMIT.

        Return only after commit; no model call in that transaction afterwards.
        admission_run carries PRIOR step count as required by admit_action; the
        checkpoint already consumed the new step. Never persist that prior count.
        """
        ...


@dataclass(frozen=True)
class AgentLoopResult:
    """A handoff, never a published terminal status or proof of business completion."""

    run: PVAgentRun  # still running until the trusted terminal owner persists the real terminal
    reason: StopReason
    terminal_request: BoundAction | None
    evidence_registry: tuple[EvidenceHandle, ...]
    outcomes: tuple[AgentToolOutcome, ...]
    audit_checkpoint_failed: bool = False
