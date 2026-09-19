"""Final answer as claim-citation structure (baseline 5.3, INV-SAF-04) and escalation ticket (F4.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from medops.domain.common import DISCLAIMER, DomainModel, NonEmptyStr, ReasonCode
from medops.domain.evidence import Citation
from medops.domain.safety import SafetyResult
from medops.domain.verification import VerifyResult


class Claim(DomainModel):
    text: NonEmptyStr
    citation_chunk_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class Answer(DomainModel):
    claims: tuple[Claim, ...] = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
    disclaimer: Literal["基于文档检索，仅供专业人员参考"] = DISCLAIMER
    historical_notice: bool = False

    @model_validator(mode="after")
    def _claims_cite_listed_citations(self) -> Answer:
        listed = {c.chunk_id for c in self.citations}
        for claim in self.claims:
            missing = set(claim.citation_chunk_ids) - listed
            if missing:
                raise ValueError(f"claim cites chunks not listed in citations: {sorted(missing)}")
        return self


class Escalation(DomainModel):
    reason_codes: tuple[ReasonCode, ...] = Field(min_length=1)
    query: NonEmptyStr
    evidence_chunk_ids: tuple[str, ...] = ()
    verify_result: VerifyResult | None = None
    safety_result: SafetyResult | None = None
    policy_version: NonEmptyStr
    detail: str = ""
