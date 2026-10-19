"""Explicit clarification commands; never a same-run recovery or payment approval."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid5

from pydantic import Field, field_validator, model_validator

from medops.application.agent_terminal import AgentDelivery
from medops.domain.agent_actions import AgentModel, Key
from medops.domain.agent_execution import AgentContext, AgentIdentity, AgentSourceScope, utc_time
from medops.domain.common import Sha256

Positive = Annotated[int, Field(gt=0, strict=True)]


class ClarificationPolicy(AgentModel):
    # Required server configuration. No approved product defaults exist yet.
    ttl_seconds: Positive
    max_continuations: Positive
    cost_limit_microusd: Positive


class ContinuationAuthorization(AgentModel):
    """Trusted admission input, supplied AFTER actual owner authorization, not by a model."""

    batch_id: UUID
    approval_sha256: Sha256
    case_ids: tuple[UUID, ...] = Field(min_length=1, max_length=256)
    expires_at: datetime
    max_executions: Positive
    cost_limit_microusd: Positive

    _utc = field_validator("expires_at")(utc_time)

    @model_validator(mode="after")
    def unique_scope(self) -> ContinuationAuthorization:
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("duplicate_continuation_scope")
        return self


class ClarificationAnswer(AgentModel):
    field: Key
    value: Annotated[str, Field(min_length=1, max_length=1000, strict=True)]

    @field_validator("value")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty_clarification_answer")
        return value


class ContinueAgent(AgentModel):
    command_id: UUID
    batch_id: UUID
    expected_revision: Annotated[int, Field(ge=1, strict=True)]
    answers: tuple[ClarificationAnswer, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_fields(self) -> ContinueAgent:
        if len({a.field for a in self.answers}) != len(self.answers):
            raise ValueError("duplicate_clarification_answer")
        return self


class ClarificationCase(AgentModel):
    case_id: UUID
    initial_run_id: UUID
    current_run_id: UUID
    revision: Annotated[int, Field(ge=1, strict=True)]
    expires_at: datetime
    deleted_at: datetime | None
    continuations: Annotated[int, Field(ge=0, strict=True)]
    accounted_cost_microusd: Annotated[int, Field(ge=0, strict=True)]
    known_cost_microusd: Annotated[int, Field(ge=0, strict=True)]
    held_cost_microusd: Annotated[int, Field(ge=0, strict=True)]


class ClarificationExecution(AgentModel):
    run_id: UUID
    source_run_id: UUID | None
    batch_id: UUID | None
    ordinal: Annotated[int, Field(ge=0, strict=True)]
    accounted_cost_microusd: Annotated[int, Field(ge=0, strict=True)]
    known_cost_microusd: Annotated[int, Field(ge=0, strict=True)]
    held_cost_microusd: Annotated[int, Field(ge=0, strict=True)]
    settled: Annotated[bool, Field(strict=True)]


class ContinuedAgent(AgentModel):
    case: ClarificationCase
    delivery: AgentDelivery


def continuation_identity(case_id: UUID, command_id: UUID) -> AgentIdentity:
    return AgentIdentity(
        case_id=case_id,
        task_id=uuid5(command_id, "clarification-task"),
        run_id=uuid5(command_id, "clarification-run"),
        attempt_id=uuid5(command_id, "clarification-attempt"),
        trace_id=uuid5(command_id, "clarification-trace").hex,
    )


def clarified_context(source: AgentDelivery, command: ContinueAgent) -> AgentContext:
    """Only answer actual saved questions. Re-evaluate evidence in a fresh execution."""
    old = source.run.context
    if source.run.status != "awaiting_clarification":
        raise ValueError("source_is_not_awaiting_clarification")
    asked = {q.field for q in source.material.questions}
    supplied = {a.field for a in command.answers}
    if not supplied <= asked or not supplied <= set(old.clarifiable_fields):
        raise ValueError("answer_does_not_match_saved_question")
    selector = old.source_scope
    narrative = old.narrative
    for answer in command.answers:
        if answer.field == "source_document":
            selector = selector.model_copy(update={"requested_document": answer.value})
        elif answer.field == "source_version":
            selector = selector.model_copy(update={"requested_version": answer.value})
        else:
            # This is labelled USER input, never verified factual evidence or a
            # system instruction. Preserve the original narrative exactly.
            narrative += f"\n[User clarification: {answer.field}]\n{answer.value}"
    selector = AgentSourceScope.model_validate(
        selector.model_copy(update={"resolution": "ambiguous", "allowed_sources": ()}).model_dump(mode="json")
    )
    return AgentContext.model_validate(
        old.model_copy(
            update={
                "identity": continuation_identity(old.identity.case_id, command.command_id),
                "source_scope": selector,
                "narrative": narrative,
            }
        ).model_dump(mode="json")
    )
