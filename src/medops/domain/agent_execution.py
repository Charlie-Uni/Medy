"""Server-owned PV run metadata and structural invariants, not a controller.

These DTOs are private. Hashes/receipt IDs bind content but do not authenticate
an issuer, prove a tool ran or replace live ACL, safety, billing or final checks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator

from medops.domain.agent_actions import ActionName, AgentModel, Brief, Key, PVAction, SourceType
from medops.domain.common import Sha256
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.domain.state import VersionSet

AgentStatus = Literal["running", "awaiting_clarification", "completed", "escalated", "failed", "cancelled"]
ObservationKind = Literal[
    "ok",
    "empty",
    "ambiguous",
    "unsupported",
    "denied_or_unavailable",
    "invalid_action",
    "dependency_error",
    "budget_exceeded",
    "timeout",
    "cancelled",
    "lease_lost",
]
StopReason = Literal[
    "completed",
    "clarification_required",
    "insufficient_evidence",
    "source_ambiguous",
    "version_conflict",
    "unsupported_requirement",
    "safety_boundary",
    "no_progress",
    "step_limit",
    "dependency_error",
    "budget_exceeded",
    "timeout",
    "cancelled",
    "lease_lost",
    "audit_failure",
    "unsupported_recovery",
]
Counter = Annotated[int, Field(ge=0, strict=True)]


def utc_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid_agent_metadata")
    return value.astimezone(UTC)


class AgentProfile(AgentModel):
    profile_id: Literal["pv-agent-dev-v1"] = "pv-agent-dev-v1"
    max_decision_steps: int = Field(default=8, ge=8, le=8, strict=True)
    token_cap: int = Field(default=12000, ge=12000, le=12000, strict=True)
    cost_cap_microusd: int = Field(default=600000, ge=600000, le=600000, strict=True)
    timeout_ms: int = Field(default=125000, ge=125000, le=125000, strict=True)
    same_no_progress_limit: int = Field(default=2, ge=2, le=2, strict=True)
    # Required engineering inputs, not new approved numeric defaults.
    final_reserve_tokens: int = Field(gt=0, le=12000, strict=True)
    final_reserve_cost_microusd: int = Field(gt=0, le=600000, strict=True)


class AgentBudget(AgentModel):
    # Preserve unexpected overspend for failure auditing; never clamp usage.
    accounted_tokens: Counter
    reserved_tokens: Counter
    accounted_cost_microusd: Counter
    reserved_cost_microusd: Counter


class AgentIdentity(AgentModel):
    case_id: UUID
    task_id: UUID
    run_id: UUID
    attempt_id: UUID
    trace_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class AgentRequirement(AgentModel):
    requirement_id: Key
    description: Brief
    kind: Literal["narrative", "guideline"]
    required: Annotated[bool, Field(strict=True)] = True


class AllowedSource(AgentModel):
    doc_id: Annotated[str, Field(min_length=1, max_length=128)]
    version: Annotated[str, Field(min_length=1, max_length=80)]
    source_sha256: Sha256


class AgentSourceScope(AgentModel):
    model_config = ConfigDict(
        json_schema_extra={
            "if": {"properties": {"resolution": {"const": "resolved"}}},
            "then": {"properties": {"allowed_sources": {"minItems": 1}}},
            "else": {"properties": {"allowed_sources": {"maxItems": 0}}},
        }
    )
    requested_document: Annotated[str, Field(min_length=1, max_length=200)] | None
    requested_version: Annotated[str, Field(min_length=1, max_length=80)] | None
    resolution: Literal["resolved", "ambiguous", "denied_or_unavailable"]
    allowed_sources: tuple[AllowedSource, ...] = Field(max_length=32)

    @model_validator(mode="after")
    def consistent_resolution(self) -> AgentSourceScope:
        if (self.resolution == "resolved") != bool(self.allowed_sources):
            raise ValueError("invalid_agent_metadata")
        if len({(s.doc_id, s.version) for s in self.allowed_sources}) != len(self.allowed_sources):
            raise ValueError("invalid_agent_metadata")
        return self


class AgentVersions(AgentModel):
    versions: VersionSet
    planning_prompt_sha256: Sha256
    tool_contract_sha256: Sha256
    verification_policy_sha256: Sha256
    rubric_sha256: Sha256
    fact_database_id: UUID
    fact_conditions_sha256: Sha256


class AgentContext(AgentModel):
    identity: AgentIdentity
    principal: UserContext
    query_context: QueryContext
    narrative: Annotated[str, Field(min_length=20, max_length=4000, pattern=r"\S")]
    synthetic: Literal[True]
    source_type: SourceType
    source_scope: AgentSourceScope
    requirements: tuple[AgentRequirement, ...] = Field(min_length=1, max_length=32)
    clarifiable_fields: tuple[Key, ...] = Field(default=(), max_length=32)
    versions: AgentVersions
    profile: AgentProfile

    @field_validator("synthetic", mode="before")
    @classmethod
    def explicitly_synthetic(cls, value: object) -> object:
        if value is not True:
            raise ValueError("invalid_agent_metadata")
        return value

    @model_validator(mode="after")
    def unique_requirements(self) -> AgentContext:
        ids = {r.requirement_id for r in self.requirements}
        if len(ids) != len(self.requirements) or len(set(self.clarifiable_fields)) != len(self.clarifiable_fields):
            raise ValueError("invalid_agent_metadata")
        if not set(self.clarifiable_fields) <= ids | {"source_document", "source_version", "requirements"}:
            raise ValueError("invalid_agent_metadata")
        return self


class AgentBinding(AgentModel):
    case_id: UUID
    task_id: UUID
    run_id: UUID
    attempt_id: UUID
    conditions_sha256: Sha256


class EvidenceHandle(AgentModel):
    handle: UUID
    binding: AgentBinding
    source_sha256: Sha256
    evidence: Evidence
    expires_at: datetime

    _utc = field_validator("expires_at")(utc_time)


class BoundAction(AgentModel):
    action_id: UUID
    binding: AgentBinding
    decision_index: int = Field(ge=1, le=8, strict=True)
    proposal: PVAction


TERMINAL_REASONS: dict[str, set[str]] = {
    "completed": {"completed"},
    "awaiting_clarification": {"clarification_required"},
    "cancelled": {"cancelled"},
    "escalated": {
        "insufficient_evidence",
        "source_ambiguous",
        "version_conflict",
        "unsupported_requirement",
        "safety_boundary",
        "no_progress",
        "step_limit",
    },
    "failed": {
        "dependency_error",
        "budget_exceeded",
        "timeout",
        "lease_lost",
        "audit_failure",
        "unsupported_recovery",
    },
}


TERMINAL_SCHEMA_RULES: list[JsonValue] = []
for terminal_status, terminal_reasons in TERMINAL_REASONS.items():
    reason_values: list[JsonValue] = [reason for reason in sorted(terminal_reasons)]
    TERMINAL_SCHEMA_RULES.append(
        {
            "if": {"properties": {"status": {"const": terminal_status}}},
            "then": {"properties": {"reason": {"enum": reason_values}}},
        }
    )
TERMINAL_SCHEMA_RULES.append(
    {
        "if": {"properties": {"status": {"const": "completed"}}},
        "then": {
            "required": ["verification_ref"],
            "properties": {"verification_ref": {"type": "string", "format": "uuid"}},
        },
    }
)


class TerminalRecord(AgentModel):
    model_config = ConfigDict(json_schema_extra={"allOf": TERMINAL_SCHEMA_RULES})
    binding: AgentBinding
    status: Literal["awaiting_clarification", "completed", "escalated", "failed", "cancelled"]
    reason: StopReason
    material_ref: UUID
    material_sha256: Sha256
    audit_ref: UUID
    verification_ref: UUID | None = None

    @model_validator(mode="after")
    def matching_terminal(self) -> TerminalRecord:
        if self.reason not in TERMINAL_REASONS[self.status] or (
            self.status == "completed" and self.verification_ref is None
        ):
            raise ValueError("invalid_agent_metadata")
        return self


RUN_SCHEMA_RULES: list[JsonValue] = [
    {
        "if": {"properties": {"status": {"const": "running"}}},
        "then": {"properties": {"stopped_at": {"type": "null"}, "terminal": {"type": "null"}}},
        "else": {
            "required": ["stopped_at", "terminal"],
            "properties": {"stopped_at": {"type": "string", "format": "date-time"}, "terminal": {"type": "object"}},
        },
    }
]
for terminal_status in TERMINAL_REASONS:
    RUN_SCHEMA_RULES.append(
        {
            "if": {"properties": {"status": {"const": terminal_status}}},
            "then": {"properties": {"terminal": {"properties": {"status": {"const": terminal_status}}}}},
        }
    )


class PVAgentRun(AgentModel):
    model_config = ConfigDict(json_schema_extra={"allOf": RUN_SCHEMA_RULES})
    context: AgentContext
    status: AgentStatus
    decisions_consumed: int = Field(ge=0, le=8, strict=True)
    budget: AgentBudget
    started_at: datetime
    expires_at: datetime
    stopped_at: datetime | None = None
    terminal: TerminalRecord | None = None

    _utc = field_validator("started_at", "expires_at")(utc_time)

    @field_validator("stopped_at")
    @classmethod
    def stopped_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc_time(value)

    @model_validator(mode="after")
    def consistent_state(self) -> PVAgentRun:
        if self.expires_at != self.started_at + timedelta(milliseconds=self.context.profile.timeout_ms):
            raise ValueError("invalid_agent_metadata")
        if self.status == "running":
            if self.stopped_at is not None or self.terminal is not None:
                raise ValueError("invalid_agent_metadata")
        elif self.stopped_at is None or self.terminal is None or self.terminal.status != self.status:
            raise ValueError("invalid_agent_metadata")
        if self.stopped_at is not None and self.stopped_at < self.started_at:
            raise ValueError("invalid_agent_metadata")
        if self.terminal is not None:
            i, terminal_binding = self.context.identity, self.terminal.binding
            if (i.case_id, i.task_id, i.run_id, i.attempt_id) != (
                terminal_binding.case_id,
                terminal_binding.task_id,
                terminal_binding.run_id,
                terminal_binding.attempt_id,
            ):
                raise ValueError("invalid_agent_metadata")
        if self.status == "completed":
            p, b = self.context.profile, self.budget
            if (
                self.stopped_at is None
                or self.stopped_at > self.expires_at
                or b.reserved_tokens
                or b.reserved_cost_microusd
            ):
                raise ValueError("invalid_agent_metadata")
            if b.accounted_tokens > p.token_cap or b.accounted_cost_microusd > p.cost_cap_microusd:
                raise ValueError("invalid_agent_metadata")
        return self


class AgentObservation(AgentModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "ok"}}},
                    "then": {
                        "required": ["result_ref", "result_sha256"],
                        "properties": {"result_ref": {"type": "string"}, "result_sha256": {"type": "string"}},
                    },
                    "else": {
                        "properties": {"evidence_handles": {"maxItems": 0}, "new_legal_information": {"const": False}}
                    },
                },
                {
                    "if": {"properties": {"retryable": {"const": True}}},
                    "then": {"properties": {"kind": {"const": "dependency_error"}}},
                },
                {
                    "if": {"required": ["result_ref"], "properties": {"result_ref": {"type": "string"}}},
                    "then": {"required": ["result_sha256"], "properties": {"result_sha256": {"type": "string"}}},
                    "else": {"properties": {"result_sha256": {"type": "null"}}},
                },
            ],
        }
    )
    action_id: UUID
    binding: AgentBinding
    action: ActionName
    kind: ObservationKind
    result_ref: UUID | None = None
    result_sha256: Sha256 | None = None
    evidence_handles: tuple[UUID, ...] = Field(default=(), max_length=64, json_schema_extra={"uniqueItems": True})
    new_legal_information: Annotated[bool, Field(strict=True)]
    retryable: Annotated[bool, Field(strict=True)]
    call_receipt_ids: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def consistent_result(self) -> AgentObservation:
        if (self.result_ref is None) != (self.result_sha256 is None):
            raise ValueError("invalid_agent_metadata")
        if self.kind == "ok" and self.result_ref is None:
            raise ValueError("invalid_agent_metadata")
        if self.kind != "ok" and (self.evidence_handles or self.new_legal_information):
            raise ValueError("invalid_agent_metadata")
        if self.retryable and self.kind != "dependency_error":
            raise ValueError("invalid_agent_metadata")
        if len(set(self.evidence_handles)) != len(self.evidence_handles) or len(set(self.call_receipt_ids)) != len(
            self.call_receipt_ids
        ):
            raise ValueError("invalid_agent_metadata")
        return self
