"""Verified evidence that may enter the model context (INV-DATA-03, INV-DATA-06, INV-DATA-07)."""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import Field, model_validator

from medops.domain.common import DocStatus, DomainModel, NonEmptyStr, Sha256


class Citation(DomainModel):
    doc_id: NonEmptyStr
    version: NonEmptyStr
    effective_date: date
    page: int = Field(ge=1)
    section: str
    chunk_id: NonEmptyStr


class Evidence(DomainModel):
    """Evidence exists only after the fact-plane recheck; drafts can never become evidence."""

    citation: Citation
    text: NonEmptyStr
    evidence_text_hash: Sha256
    chunk_content_hash: Sha256
    status: DocStatus
    historical: bool = False

    @model_validator(mode="after")
    def _rules(self) -> Evidence:
        if self.status in (DocStatus.draft, DocStatus.withdrawn):
            raise ValueError(f"{self.status.value} documents cannot be evidence")
        if self.status is DocStatus.archived and not self.historical:
            raise ValueError("archived evidence must be marked historical (INV-DATA-03)")
        if self.status is DocStatus.active and self.historical:
            raise ValueError("active evidence cannot be marked historical")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.evidence_text_hash:
            raise ValueError("evidence_text_hash does not match text (baseline 3.3)")
        return self
