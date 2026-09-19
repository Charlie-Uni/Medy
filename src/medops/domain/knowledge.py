"""Fact-plane records: documents and chunks (baseline 3.3, 3.4, 5.1)."""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import Field, model_validator

from medops.domain.common import Dept, DocStatus, DocType, DomainModel, NonEmptyStr, Sha256


class Document(DomainModel):
    doc_id: NonEmptyStr
    family_id: NonEmptyStr
    title: NonEmptyStr
    doc_type: DocType
    version: NonEmptyStr
    status: DocStatus
    effective_from: date | None = None
    effective_to: date | None = None
    source_hash: Sha256
    supersedes: str | None = None
    owner_dept: Dept

    @model_validator(mode="after")
    def _effective_window(self) -> Document:
        if self.status is DocStatus.active and self.effective_from is None:
            raise ValueError("active documents must have effective_from (baseline 3.4)")
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        if self.supersedes == self.doc_id:
            raise ValueError("a document cannot supersede itself")
        return self


class Chunk(DomainModel):
    """A page fragment of normalized text; offsets are relative to the normalized page text."""

    chunk_id: NonEmptyStr
    doc_id: NonEmptyStr
    page: int = Field(ge=1)
    section: str
    seq: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=1)
    content: NonEmptyStr
    content_hash: Sha256

    @model_validator(mode="after")
    def _content_integrity(self) -> Chunk:
        if self.char_end - self.char_start != len(self.content):
            raise ValueError("char range must match content length")
        if hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.content_hash:
            raise ValueError("content_hash does not match content (chunk_content_hash, baseline 3.3)")
        return self
