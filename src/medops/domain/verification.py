"""Verifier output: structural citation check plus element-level support (baseline 3.5, 5.4)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from medops.domain.common import DomainModel, NonEmptyStr


class ElementKind(StrEnum):
    dose = "dose"
    unit = "unit"
    frequency = "frequency"
    indication = "indication"
    population = "population"
    time_window = "time_window"
    identifier = "identifier"


class Verdict(StrEnum):
    supported = "supported"
    not_supported = "not_supported"
    contradicted = "contradicted"


class ElementSupport(DomainModel):
    kind: ElementKind
    text: NonEmptyStr
    verdict: Verdict
    evidence_chunk_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""

    @model_validator(mode="after")
    def _supported_needs_evidence(self) -> ElementSupport:
        if self.verdict is Verdict.supported and not self.evidence_chunk_id:
            raise ValueError("a supported element must name the evidence chunk that supports it")
        return self


class VerifyResult(DomainModel):
    structural_ok: bool
    hallucinated_citations: tuple[str, ...] = ()
    elements: tuple[ElementSupport, ...] = ()
    verifier_version: NonEmptyStr

    @model_validator(mode="after")
    def _structural(self) -> VerifyResult:
        if self.hallucinated_citations and self.structural_ok:
            raise ValueError("structural_ok cannot be True when hallucinated citations exist")
        return self

    @property
    def contradicted(self) -> bool:
        return any(e.verdict is Verdict.contradicted for e in self.elements)

    @property
    def unsupported(self) -> tuple[ElementSupport, ...]:
        return tuple(e for e in self.elements if e.verdict is Verdict.not_supported)
