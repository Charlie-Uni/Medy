"""Skill contract (baseline 5.6, INV-AUTH-03): every Skill declares its schema (input/output models), version,
required scopes, risk, timeout, idempotency and parallel safety. The Registry enforces them before and after
execution; nothing here knows about the harness or any adapter."""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from medops.domain.common import DomainModel, NonEmptyStr, ReasonCode, RiskLevel
from medops.domain.identity import UserContext

SkillName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]  # same pattern as the API contract
SkillVersion = Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
DEPT_PLACEHOLDER = "$dept"
# `$dept:<action>` resolves to the caller's own department at check time; explicit departments and ADMIN stay fixed.
ScopeRequirement = Annotated[str, Field(pattern=r"^(MA|PV|CO|ADMIN|\$dept):[a-z_]+$")]


class SkillSpec(DomainModel):
    name: SkillName
    version: SkillVersion
    description: NonEmptyStr
    risk: RiskLevel
    required_scopes: tuple[ScopeRequirement, ...] = Field(min_length=1)  # default deny: no scope, no skill
    timeout_s: float = Field(gt=0, le=120)
    parallel_safe: bool = False
    idempotent: bool = False  # only idempotent skills may be retried after a timeout

    @property
    def version_tag(self) -> str:
        """The entry recorded in `VersionSet.skill_version_set` (INV-HAR-05)."""
        return f"{self.name}@{self.version}"

    def resolve_scopes(self, user: UserContext) -> tuple[str, ...]:
        return tuple(scope.replace(DEPT_PLACEHOLDER, user.dept.value) for scope in self.required_scopes)


class SkillStatus(StrEnum):
    completed = "completed"
    insufficient_evidence = "insufficient_evidence"
    escalated = "escalated"


class SkillOutput(DomainModel):
    """Base of every Skill output. Subclasses add typed payload fields; the Registry runs safety layer 3 over
    `rendered_texts()` and replaces the payload with a bare escalation when it is refused."""

    status: SkillStatus
    reason_codes: tuple[ReasonCode, ...] = ()
    detail: str = ""

    @model_validator(mode="after")
    def _non_completion_has_a_reason(self) -> SkillOutput:
        if self.status is not SkillStatus.completed and not self.reason_codes:
            raise ValueError(f"skill status {self.status.value} needs at least one reason code")
        return self

    def rendered_texts(self) -> tuple[str, ...]:
        """Every human-readable string of the payload (not the envelope fields)."""
        payload = self.model_dump(mode="json", exclude={"status", "reason_codes", "detail"})
        return tuple(_strings(payload))


def _strings(obj: object) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _strings(value)
