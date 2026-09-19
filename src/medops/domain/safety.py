"""Safety node output (baseline 3.6, 5.5)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from medops.domain.common import DomainModel, NonEmptyStr, ReasonCode


class SafetyDecision(StrEnum):
    allow = "allow"
    refuse = "refuse"
    escalate = "escalate"


class SafetyResult(DomainModel):
    decision: SafetyDecision
    reason_codes: tuple[ReasonCode, ...] = ()
    detail: str = ""
    checker_version: NonEmptyStr

    @model_validator(mode="after")
    def _codes_match_decision(self) -> SafetyResult:
        if self.decision is SafetyDecision.allow and self.reason_codes:
            raise ValueError("an allow decision carries no reason codes")
        if self.decision is not SafetyDecision.allow and not self.reason_codes:
            raise ValueError("refuse/escalate decisions require at least one reason code")
        return self
