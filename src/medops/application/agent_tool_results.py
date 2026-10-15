"""Typed private tool payloads. Only payload may be projected to a planner after audit commit."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from medops.domain.ae import AeKind
from medops.domain.agent_actions import AgentModel, Key, Text
from medops.domain.agent_execution import AgentBinding, EvidenceHandle, ObservationKind
from medops.domain.common import Sha256
from medops.domain.evidence import Citation, Evidence
from medops.domain.skill import SkillStatus
from medops.domain.verification import Verdict


class AgentFact(AgentModel):
    evidence: Evidence
    source_sha256: Sha256


class ExtractedElement(AgentModel):
    kind: AeKind
    value: Text
    quote: Annotated[str, Field(min_length=1, max_length=4000)]
    char_start: int = Field(ge=0, strict=True)
    char_end: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def span(self) -> ExtractedElement:
        if self.char_end - self.char_start != len(self.quote):
            raise ValueError("invalid_agent_tool_result")
        return self


class ExtractionPayload(AgentModel):
    action: Literal["extract_ae"] = "extract_ae"
    skill_status: SkillStatus
    elements: tuple[ExtractedElement, ...] = Field(max_length=64)
    missing_kinds: tuple[AeKind, ...] = Field(max_length=9)
    unaligned_elements: int = Field(ge=0, strict=True)
    dropped_ungrounded: int = Field(ge=0, strict=True)
    dropped_causality: int = Field(ge=0, strict=True)


class EvidenceView(AgentModel):
    handle: UUID
    citation: Citation
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    char_start: Literal[0] = 0
    char_end: int = Field(gt=0, strict=True)
    truncated: Annotated[bool, Field(strict=True)]
    evidence_text_sha256: Sha256
    source_sha256: Sha256

    @model_validator(mode="after")
    def span(self) -> EvidenceView:
        if self.char_end != len(self.text):
            raise ValueError("invalid_agent_tool_result")
        return self


class SearchPayload(AgentModel):
    action: Literal["search_documents"] = "search_documents"
    matches: tuple[EvidenceView, ...] = Field(max_length=8)


class ReadPayload(AgentModel):
    action: Literal["read_evidence"] = "read_evidence"
    evidence: EvidenceView


class ClaimToolCheck(AgentModel):
    requirement_id: Key
    text: Text
    verdict: Verdict
    requested_handles: tuple[UUID, ...] = Field(min_length=1, max_length=8)
    supporting_handles: tuple[UUID, ...] = Field(max_length=8)
    unconfirmed_handles: tuple[UUID, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def handle_partition(self) -> ClaimToolCheck:
        wanted, supporting, unknown = map(
            set, (self.requested_handles, self.supporting_handles, self.unconfirmed_handles)
        )
        if supporting & unknown or supporting | unknown != wanted:
            raise ValueError("invalid_agent_tool_result")
        return self


class VerificationPayload(AgentModel):
    action: Literal["verify_citations"] = "verify_citations"
    checks: tuple[ClaimToolCheck, ...] = Field(min_length=1, max_length=20)
    verifier_version: str


ToolPayload = Annotated[
    ExtractionPayload | SearchPayload | ReadPayload | VerificationPayload, Field(discriminator="action")
]


class AgentToolOutcome(AgentModel):
    """Private envelope, not a durable AgentObservation or permission to complete a task.

    issued_handles are server-only. The caller must persist payload and audit under
    the fact fence, commit, then construct an observation referencing the stored result.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"kind": {"const": "ok"}}},
                    "then": {"required": ["payload"], "properties": {"payload": {"type": "object"}}},
                    "else": {"properties": {"issued_handles": {"maxItems": 0}, "new_handles_issued": {"const": False}}},
                },
                {
                    "if": {"required": ["new_handles_issued"], "properties": {"new_handles_issued": {"const": True}}},
                    "then": {"required": ["issued_handles"], "properties": {"issued_handles": {"minItems": 1}}},
                    "else": {"properties": {"issued_handles": {"maxItems": 0}}},
                },
                {
                    "if": {"required": ["retryable"], "properties": {"retryable": {"const": True}}},
                    "then": {"properties": {"kind": {"const": "dependency_error"}}},
                },
            ]
        }
    )
    action_id: UUID
    binding: AgentBinding
    kind: ObservationKind
    payload: ToolPayload | None = None
    issued_handles: tuple[EvidenceHandle, ...] = Field(default=(), max_length=8)
    call_receipt_ids: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...] = Field(
        default=(), max_length=64, json_schema_extra={"uniqueItems": True}
    )
    new_handles_issued: Annotated[bool, Field(strict=True)] = False
    retryable: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def consistent(self) -> AgentToolOutcome:
        if len(set(self.call_receipt_ids)) != len(self.call_receipt_ids):
            raise ValueError("invalid_agent_tool_result")
        if self.kind == "ok" and self.payload is None:
            raise ValueError("invalid_agent_tool_result")
        if self.kind != "ok" and (self.issued_handles or self.new_handles_issued):
            raise ValueError("invalid_agent_tool_result")
        if self.new_handles_issued != bool(self.issued_handles):
            raise ValueError("invalid_agent_tool_result")
        if self.retryable and self.kind != "dependency_error":
            raise ValueError("invalid_agent_tool_result")
        return self
