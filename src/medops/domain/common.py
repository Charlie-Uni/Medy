"""Shared domain vocabulary. Every domain model is frozen, forbids extra fields and is JSON-serializable
(INV-HAR-01, INV-HAR-02). Untyped dictionaries and `Any` are not used anywhere in this package."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER: Final = "基于文档检索，仅供专业人员参考"  # INV-SAF-04
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Dept(StrEnum):
    MA = "MA"
    PV = "PV"
    CO = "CO"


class DocType(StrEnum):
    label = "label"
    protocol = "protocol"
    sop = "sop"
    guideline = "guideline"


class DocStatus(StrEnum):
    """draft -> active -> archived; a draft may instead end as withdrawn (terminal, never evidence, never exposed)."""

    draft = "draft"
    active = "active"
    archived = "archived"
    withdrawn = "withdrawn"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ReasonCode(StrEnum):
    """Stable refusal/escalation reason codes (baseline 5.5, F4.1)."""

    insufficient_evidence = "insufficient_evidence"
    version_conflict = "version_conflict"
    acl_denied = "acl_denied"
    prompt_injection = "prompt_injection"
    high_risk_medical = "high_risk_medical"
    unsupported_conclusion = "unsupported_conclusion"
    budget_exceeded = "budget_exceeded"
    intent_unclear = "intent_unclear"
    system_failure = "system_failure"
