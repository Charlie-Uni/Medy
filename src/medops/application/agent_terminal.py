"""Closed delivery contracts. A DTO is not permission to publish or resume a run."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from medops.application.agent_contracts import context_binding, validate_run_snapshot
from medops.application.agent_review import PreparedReview, RequirementReview
from medops.application.agent_runtime_state import run_with_budget
from medops.application.agent_stop_gate import StopVerdict
from medops.application.agent_tool_results import ExtractedElement
from medops.core.canonical import canonical_hash
from medops.domain.agent_actions import ActionName, AgentModel, ClarificationQuestion, Key
from medops.domain.agent_execution import (
    TERMINAL_REASONS,
    AgentBinding,
    EvidenceHandle,
    ObservationKind,
    PVAgentRun,
    StopReason,
)
from medops.domain.common import DISCLAIMER
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState

TerminalStatus = Literal["completed", "awaiting_clarification", "escalated", "failed", "cancelled"]


class CommittedActionReceipt(AgentModel):
    action_id: UUID
    action: ActionName
    decision_index: Annotated[int, Field(ge=1, le=8, strict=True)]
    outcome: ObservationKind


class EscalationReceipt(AgentModel):
    receipt_id: UUID
    state: Literal["pending_review"] = "pending_review"
    assigned_to: None = None
    externally_reported: Literal[False] = False


class AgentTerminalMaterial(AgentModel):
    version: Literal["pv-agent-material-v1"] = "pv-agent-material-v1"
    binding: AgentBinding
    status: TerminalStatus
    reason: StopReason
    continuation_mode: Literal["new_execution_required", "not_applicable"]
    same_run_resumable: Literal[False] = False
    requirements: tuple[RequirementReview, ...] = Field(min_length=1, max_length=32)
    missing_requirement_ids: tuple[Key, ...] = Field(max_length=32)
    review: PreparedReview | None
    questions: tuple[ClarificationQuestion, ...] = Field(max_length=8)
    extracted_elements: tuple[ExtractedElement, ...] = Field(max_length=64)
    stop_check: StopVerdict | None
    escalation: EscalationReceipt | None
    committed_actions: tuple[CommittedActionReceipt, ...] = Field(max_length=8)
    call_receipt_ids: tuple[str, ...] = Field(max_length=128)
    pending_call_ids: tuple[str, ...] = Field(max_length=128)
    disclaimer: Literal["基于文档检索，仅供专业人员参考"] = DISCLAIMER

    @model_validator(mode="after")
    def consistent(self) -> AgentTerminalMaterial:
        if self.reason not in TERMINAL_REASONS[self.status]:
            raise ValueError("invalid_agent_terminal")
        missing = tuple(r.requirement_id for r in self.requirements if r.required and r.state != "verified")
        if self.missing_requirement_ids != missing or len({r.requirement_id for r in self.requirements}) != len(
            self.requirements
        ):
            raise ValueError("invalid_agent_terminal")
        if (
            len(set(self.call_receipt_ids)) != len(self.call_receipt_ids)
            or len(set(self.pending_call_ids)) != len(self.pending_call_ids)
            or set(self.pending_call_ids) & set(self.call_receipt_ids)
        ):
            raise ValueError("invalid_agent_terminal")
        if self.review is not None and (
            self.review.binding != self.binding or self.review.requirements != self.requirements
        ):
            raise ValueError("invalid_agent_terminal")
        if self.status == "completed" and (
            self.review is None or not self.review.completion_eligible or missing or self.pending_call_ids
        ):
            raise ValueError("invalid_agent_terminal")
        if (self.status == "awaiting_clarification") != (self.continuation_mode == "new_execution_required"):
            raise ValueError("invalid_agent_terminal")
        if (self.status == "awaiting_clarification") != bool(self.questions):
            raise ValueError("invalid_agent_terminal")
        if self.questions and (
            self.stop_check is None
            or not self.stop_check.decision_supported
            or not self.stop_check.scope_safe
            or any(not q.necessary or not q.grounded for q in self.stop_check.questions)
        ):
            raise ValueError("invalid_agent_terminal")
        if (self.status == "escalated") != (self.escalation is not None):
            raise ValueError("invalid_agent_terminal")
        if self.status in {"failed", "cancelled"} and (
            self.review is not None or self.questions or self.extracted_elements
        ):
            raise ValueError("invalid_agent_terminal")
        return self


class AgentDelivery(AgentModel):
    version: Literal["pv-agent-delivery-v1"] = "pv-agent-delivery-v1"
    run: PVAgentRun
    material: AgentTerminalMaterial

    @model_validator(mode="after")
    def consistent(self) -> AgentDelivery:
        run = validate_run_snapshot(self.run)
        terminal = run.terminal
        if (
            terminal is None
            or terminal.binding != self.material.binding
            or context_binding(run.context) != self.material.binding
            or (run.status, terminal.reason) != (self.material.status, self.material.reason)
            or terminal.material_sha256 != canonical_hash(self.material.model_dump(mode="json"))
        ):
            raise ValueError("invalid_agent_delivery")
        return self


class TerminalEnvelope(AgentModel):
    version: Literal["pv-agent-terminal-envelope-v1"] = "pv-agent-terminal-envelope-v1"
    delivery: AgentDelivery
    registry: tuple[EvidenceHandle, ...] = Field(max_length=64)
    budget: FrozenBudgetState
    # References are actual immutable runtime event IDs, not model-authored labels.
    verification_event: UUID | None
    stopped_at: datetime
    accounted_complete: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def bound_snapshot(self) -> TerminalEnvelope:
        run = self.delivery.run
        terminal = run.terminal
        if (
            terminal is None
            or self.stopped_at != run.stopped_at
            or self.verification_event != terminal.verification_ref
            or run_with_budget(run, self.budget.snapshot) != run
            or self.accounted_complete != (not self.budget.pending)
        ):
            raise ValueError("invalid_agent_terminal_envelope")
        if set(self.delivery.material.call_receipt_ids) != set(self.budget.settled) or set(
            self.delivery.material.pending_call_ids
        ) != {p.call_id for p in self.budget.pending}:
            raise ValueError("invalid_agent_terminal_envelope")
        if [(r.requirement_id, r.kind, r.required) for r in self.delivery.material.requirements] != [
            (r.requirement_id, r.kind, r.required) for r in run.context.requirements
        ] or any(h.binding != context_binding(run.context) for h in self.registry):
            raise ValueError("invalid_agent_terminal_envelope")
        return self
