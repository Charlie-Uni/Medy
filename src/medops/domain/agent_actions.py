"""Planner-owned PV action proposals. Nothing here executes or approves an answer."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from medops.domain.common import DomainModel

Key = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]
Brief = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]
Text = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
SourceType = Literal["call_note", "email", "literature", "other"]
ActionName = Literal[
    "extract_ae", "search_documents", "read_evidence", "verify_citations", "clarify", "finish", "escalate"
]


class AgentModel(DomainModel):
    model_config = ConfigDict(revalidate_instances="always", hide_input_in_errors=True, allow_inf_nan=False)


class NarrativeFact(AgentModel):
    requirement_id: Key
    value: Text
    quote: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    char_start: int = Field(ge=0, strict=True)
    char_end: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def valid_span(self) -> NarrativeFact:
        if self.char_end - self.char_start != len(self.quote):
            raise ValueError("invalid_agent_payload")
        return self


class GuidelineClaim(AgentModel):
    requirement_id: Key
    text: Text
    evidence_handles: tuple[UUID, ...] = Field(min_length=1, max_length=8, json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def unique_handles(self) -> GuidelineClaim:
        if len(set(self.evidence_handles)) != len(self.evidence_handles):
            raise ValueError("invalid_agent_payload")
        return self


class ReviewDraft(AgentModel):
    narrative_facts: tuple[NarrativeFact, ...] = Field(max_length=64, json_schema_extra={"uniqueItems": True})
    guideline_claims: tuple[GuidelineClaim, ...] = Field(max_length=32, json_schema_extra={"uniqueItems": True})
    missing_requirement_ids: tuple[Key, ...] = Field(max_length=32, json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def no_duplicate_rows(self) -> ReviewDraft:
        for values in (self.narrative_facts, self.guideline_claims, self.missing_requirement_ids):
            if len(set(values)) != len(values):
                raise ValueError("invalid_agent_payload")
        return self


class ActionRequest(AgentModel):
    rationale: Brief  # brief, checkable purpose; never requested hidden chain of thought


class ExtractAEAction(ActionRequest):
    action: Literal["extract_ae"]
    narrative_ref: Literal["task_narrative"]
    source_type: SourceType


class SearchDocumentsAction(ActionRequest):
    action: Literal["search_documents"]
    query: Text


class ReadEvidenceAction(ActionRequest):
    action: Literal["read_evidence"]
    handle: UUID
    region: Literal["current", "previous", "next"]


class VerifyCitationsAction(ActionRequest):
    action: Literal["verify_citations"]
    claims: tuple[GuidelineClaim, ...] = Field(min_length=1, max_length=32)


class ClarificationQuestion(AgentModel):
    field: Key
    question: Brief
    reason: Brief


class ClarifyAction(ActionRequest):
    action: Literal["clarify"]
    questions: tuple[ClarificationQuestion, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_fields(self) -> ClarifyAction:
        if len({q.field for q in self.questions}) != len(self.questions):
            raise ValueError("invalid_agent_payload")
        return self


class FinishAction(ActionRequest):
    action: Literal["finish"]
    draft: ReviewDraft


class EscalateAction(ActionRequest):
    action: Literal["escalate"]
    reason: Literal[
        "insufficient_evidence",
        "source_ambiguous",
        "version_conflict",
        "unsupported_requirement",
        "safety_boundary",
        "no_progress",
        "step_limit",
    ]
    draft: ReviewDraft


PVAction = Annotated[
    ExtractAEAction
    | SearchDocumentsAction
    | ReadEvidenceAction
    | VerifyCitationsAction
    | ClarifyAction
    | FinishAction
    | EscalateAction,
    Field(discriminator="action"),
]


class PlannerProposal(AgentModel):
    proposal: PVAction
