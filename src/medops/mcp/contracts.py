"""Read-only MCP tool contracts (baseline 5.7, INV-AUTH-04, M0-08).

Exactly four tools, all read-only. Identity comes from the verified bearer token of the Streamable
HTTP transport; no tool input may carry `dept` or `scopes`. Visibility is always relative to the
calling identity: a document the caller may not read does not "exist" for these tools. Draft
and withdrawn documents are never exposed; archived documents only under an explicit historical request.

`MCP_TOOLS` is a local descriptor list. It is not the MCP `tools/list` response: the server maps it
to the protocol's `inputSchema`/`outputSchema` fields in M3-06, and `read_only` is documentation,
not an authorization control (database roles enforce read-only access).
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.config import JsonDict

from medops.domain.common import DocStatus, DocType
from medops.domain.evidence import Citation

NonEmptyStr = Annotated[str, Field(min_length=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MAX_K: Final = 20  # baseline 4.4: reranker input at most 20 candidates

_VISIBLE_STATUS_SCHEMA: Final[JsonDict] = {
    "allOf": [
        {"properties": {"status": {"enum": ["active", "archived"]}}},
        {
            "if": {"properties": {"status": {"const": "archived"}}},
            "then": {"required": ["historical"], "properties": {"historical": {"const": True}}},
        },
        {
            "if": {"properties": {"status": {"const": "active"}}},
            "then": {"properties": {"historical": {"const": False}}},
        },
    ]
}


class McpModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


def _visible(status: DocStatus, historical: bool) -> None:
    if status in (DocStatus.draft, DocStatus.withdrawn):
        raise ValueError(f"{status.value} documents are never exposed")
    if (status is DocStatus.archived) != historical:
        raise ValueError("archived results must be flagged historical and vice versa")


# --- search_documents -----------------------------------------------------------------------
class SearchDocumentsInput(McpModel):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    k: Annotated[int, Field(ge=1, le=MAX_K)] = 8
    historical_version: NonEmptyStr | None = None


class SearchHit(McpModel):
    model_config = ConfigDict(json_schema_extra=_VISIBLE_STATUS_SCHEMA)

    citation: Citation
    snippet: Annotated[str, Field(min_length=1, max_length=1000)]
    status: DocStatus
    historical: bool = False

    @model_validator(mode="after")
    def _visible_status(self) -> SearchHit:
        _visible(self.status, self.historical)
        return self


class SearchDocumentsOutput(McpModel):
    """`candidate_exhausted` follows the hit count; that relation needs server state and is not in the schema."""

    hits: tuple[SearchHit, ...]
    requested_k: Annotated[int, Field(ge=1, le=MAX_K)]
    candidate_exhausted: bool

    @model_validator(mode="after")
    def _consistent(self) -> SearchDocumentsOutput:
        ids = [h.citation.chunk_id for h in self.hits]
        if len(set(ids)) != len(ids):
            raise ValueError("hits must not repeat a chunk")
        if len(self.hits) > self.requested_k:
            raise ValueError("more hits than requested")
        if self.candidate_exhausted != (len(self.hits) < self.requested_k):
            raise ValueError("candidate_exhausted must be True exactly when fewer than requested_k hits were returned")
        return self


# --- get_chunk -------------------------------------------------------------------------------
class GetChunkInput(McpModel):
    chunk_id: NonEmptyStr
    historical_version: NonEmptyStr | None = None


class ChunkView(McpModel):
    """`content_hash` is the SHA-256 of the full UTF-8 content and is recomputed here; that only
    proves the view is self-consistent, the trusted hash still comes from the fact plane."""

    model_config = ConfigDict(json_schema_extra=_VISIBLE_STATUS_SCHEMA)

    citation: Citation
    content: NonEmptyStr
    content_hash: Sha256
    status: DocStatus
    historical: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> ChunkView:
        _visible(self.status, self.historical)
        if hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.content_hash:
            raise ValueError("content_hash does not match content")
        return self


# --- verify_citation ---------------------------------------------------------------------------
class VerifyCitationInput(McpModel):
    citation: Citation


class VerifyCitationOutput(McpModel):
    """`exists` means visible to the calling identity, not present anywhere in the database. Drafts
    are never visible, archived versions only under an explicit historical request. `fields_match`
    means every Citation field (doc_id, version, effective_date, page, section, chunk_id) agrees with
    the fact plane; it does not mean the citation is currently citable."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"exists": {"const": False}}},
                    "then": {"properties": {"status": {"type": "null"}, "fields_match": {"const": False}}},
                },
                {
                    "if": {"properties": {"exists": {"const": True}}},
                    "then": {"required": ["status"], "properties": {"status": {"enum": ["active", "archived"]}}},
                },
            ]
        }
    )

    exists: bool
    status: DocStatus | None = None
    fields_match: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> VerifyCitationOutput:
        if not self.exists and (self.status is not None or self.fields_match):
            raise ValueError("a citation that does not exist has no status and cannot match")
        if self.exists and self.status is None:
            raise ValueError("an existing citation reports its status")
        if self.status is DocStatus.draft:
            raise ValueError("draft documents are never visible")
        return self


# --- list_active_versions ------------------------------------------------------------------------
class ListActiveVersionsInput(McpModel):
    family_id: NonEmptyStr


class DocumentVersionView(McpModel):
    doc_id: NonEmptyStr
    family_id: NonEmptyStr
    title: NonEmptyStr
    doc_type: DocType
    version: NonEmptyStr
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _window(self) -> DocumentVersionView:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class ListActiveVersionsOutput(McpModel):
    family_id: NonEmptyStr
    active: DocumentVersionView | None  # at most one active per family (INV-DATA-02)

    @model_validator(mode="after")
    def _same_family(self) -> ListActiveVersionsOutput:
        if self.active is not None and self.active.family_id != self.family_id:
            raise ValueError("active document must belong to the requested family")
        return self


class ToolSpec(McpModel):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z_]+$")]
    description: NonEmptyStr
    input_model: str
    output_model: str
    read_only: bool = True


MCP_TOOLS: Final[tuple[ToolSpec, ...]] = (
    ToolSpec(
        name="search_documents",
        description="Authorized hybrid search over documents visible to the caller; returns verified citations with snippets.",
        input_model="SearchDocumentsInput",
        output_model="SearchDocumentsOutput",
    ),
    ToolSpec(
        name="get_chunk",
        description="Fetch one visible chunk with its citation and content hash, subject to ACL and status.",
        input_model="GetChunkInput",
        output_model="ChunkView",
    ),
    ToolSpec(
        name="verify_citation",
        description="Check that a citation is visible to the caller and that all of its fields match the fact plane.",
        input_model="VerifyCitationInput",
        output_model="VerifyCitationOutput",
    ),
    ToolSpec(
        name="list_active_versions",
        description="Return the single active version of a document family visible to the caller, if any.",
        input_model="ListActiveVersionsInput",
        output_model="ListActiveVersionsOutput",
    ),
)
