"""Intent node output (design 3.2; Skill risk levels from F2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from medops.domain.common import DomainModel, NonEmptyStr, RiskLevel


class IntentType(StrEnum):
    label_query = "label_query"
    ae_extraction = "ae_extraction"
    off_label_check = "off_label_check"
    protocol_deviation = "protocol_deviation"
    citation_verification = "citation_verification"
    general_qa = "general_qa"
    unclear = "unclear"
    high_risk = "high_risk"  # diagnosis, prescription, individual dosing, emergency (INV-SAF-01)


_MIN_RISK = {
    IntentType.off_label_check: RiskLevel.high,
    IntentType.high_risk: RiskLevel.high,
    IntentType.ae_extraction: RiskLevel.medium,
    IntentType.protocol_deviation: RiskLevel.medium,
}
_ORDER = {RiskLevel.low: 0, RiskLevel.medium: 1, RiskLevel.high: 2}


class Entity(DomainModel):
    kind: Literal["drug", "protocol", "population", "indication", "other"]
    value: NonEmptyStr


class Intent(DomainModel):
    type: IntentType
    target_skill: str | None = None
    risk: RiskLevel
    entities: tuple[Entity, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _risk_floor(self) -> Intent:
        floor = _MIN_RISK.get(self.type)
        if floor is not None and _ORDER[self.risk] < _ORDER[floor]:
            raise ValueError(f"intent {self.type.value} requires risk >= {floor.value}")
        if self.type is IntentType.high_risk and self.target_skill is not None:
            raise ValueError("high-risk intents are refused and escalated, never routed to a skill")
        return self
