"""Read-only MCP tool implementations (M3-06, baseline 5.7, INV-AUTH-04), framework-free.

Every method runs on the caller's read-only connection with the department already injected (RLS), so a
document the caller may not read simply does not exist here. Draft and withdrawn documents are never exposed;
archived documents only when the call names that version explicitly (`historical_version`). The search tool
delegates candidate retrieval to a `Searcher` (production: the same hybrid retrieval + fact-plane re-check as
the harness) and applies the same visibility rules to what comes back."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import DocStatus, DocType
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.mcp.contracts import (
    ChunkView,
    DocumentVersionView,
    GetChunkInput,
    ListActiveVersionsInput,
    ListActiveVersionsOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SearchHit,
    VerifyCitationInput,
    VerifyCitationOutput,
)

VISIBLE = ("active", "archived")
_CHUNK_SQL = """
select c.chunk_id::text, c.doc_id::text, d.version, d.status::text, d.effective_from, d.effective_to, c.page,
       coalesce(c.section, ''), c.content, c.chunk_content_hash, d.family_id::text, d.title, d.doc_type::text
  from chunks c join documents d on d.doc_id = c.doc_id
 where c.chunk_id = %s and d.status in ('active', 'archived')
"""


@dataclass(frozen=True)
class SearchExecution:
    evidence: Sequence[Evidence]
    model_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    retrieval_version: str | None = None
    policy_version: str | None = None
    cache_hit: bool = False


class Searcher(Protocol):
    def __call__(
        self, query: str, k: int, *, as_of: date | None, allow_historical: bool
    ) -> Sequence[Evidence] | SearchExecution: ...


@dataclass(frozen=True)
class _ChunkRow:
    chunk_id: str
    doc_id: str
    version: str
    status: DocStatus
    effective_from: date
    effective_to: date | None
    page: int
    section: str
    content: str
    content_hash: str
    family_id: str
    title: str
    doc_type: DocType

    def citation(self) -> Citation:
        return Citation(
            doc_id=self.doc_id,
            version=self.version,
            effective_date=self.effective_from,
            page=self.page,
            section=self.section,
            chunk_id=self.chunk_id,
        )


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


class McpService:
    def __init__(self, conn: Any, user: UserContext, searcher: Searcher | None = None) -> None:
        self._conn = conn
        self.user = user
        self._searcher = searcher
        self.audit_stats = SearchExecution(())

    # ------------------------------------------------------------------ helpers
    def _chunk(self, chunk_id: str) -> _ChunkRow | None:
        cid = _uuid(chunk_id)
        if cid is None:
            return None
        row = self._conn.execute(_CHUNK_SQL, (cid,)).fetchone()
        if row is None:
            return None
        return _ChunkRow(
            chunk_id=row[0],
            doc_id=row[1],
            version=row[2],
            status=DocStatus(row[3]),
            effective_from=row[4],
            effective_to=row[5],
            page=row[6],
            section=row[7],
            content=row[8],
            content_hash=row[9],
            family_id=row[10],
            title=row[11],
            doc_type=DocType(row[12]),
        )

    def _historical_as_of(self, version: str | None) -> date | None:
        """The effective date of a visible archived document carrying that version label, if any."""
        if version is None:
            return None
        row = self._conn.execute(
            "select min(effective_from) from documents where version = %s and status = 'archived'", (version,)
        ).fetchone()
        return row[0] if row and row[0] else None

    @staticmethod
    def _exposable(status: DocStatus, version: str, historical_version: str | None) -> bool:
        if status is DocStatus.active:
            return True
        return status is DocStatus.archived and historical_version is not None and version == historical_version

    # ------------------------------------------------------------------ tools
    def search_documents(self, inp: SearchDocumentsInput) -> SearchDocumentsOutput:
        if self._searcher is None:
            raise BusinessError(ErrorCode.invalid_request, "search is not available on this server")
        as_of = self._historical_as_of(inp.historical_version)
        try:
            searched = self._searcher(inp.query, inp.k, as_of=as_of, allow_historical=as_of is not None)
        finally:
            latest = getattr(self._searcher, "audit_stats", None)
            if isinstance(latest, SearchExecution):
                self.audit_stats = latest
        if isinstance(searched, SearchExecution):
            self.audit_stats = searched
            evidence = searched.evidence
        else:
            evidence = searched
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for ev in evidence:
            if ev.citation.chunk_id in seen or not self._exposable(
                ev.status, ev.citation.version, inp.historical_version
            ):
                continue
            seen.add(ev.citation.chunk_id)
            hits.append(
                SearchHit(
                    citation=ev.citation,
                    snippet=ev.text[:1000],
                    status=ev.status,
                    historical=ev.status is DocStatus.archived,
                )
            )
            if len(hits) == inp.k:
                break
        return SearchDocumentsOutput(hits=tuple(hits), requested_k=inp.k, candidate_exhausted=len(hits) < inp.k)

    def get_chunk(self, inp: GetChunkInput) -> ChunkView:
        row = self._chunk(inp.chunk_id)
        if row is None or not self._exposable(row.status, row.version, inp.historical_version):
            raise BusinessError(ErrorCode.not_found, "chunk not found")  # invisible == nonexistent (INV-AUTH-04)
        content_hash = hashlib.sha256(row.content.encode("utf-8")).hexdigest()
        if content_hash != row.content_hash:
            raise BusinessError(ErrorCode.evidence_integrity_failed, "stored chunk hash does not match its content")
        return ChunkView(
            citation=row.citation(),
            content=row.content,
            content_hash=content_hash,
            status=row.status,
            historical=row.status is DocStatus.archived,
        )

    def verify_citation(self, inp: VerifyCitationInput) -> VerifyCitationOutput:
        row = self._chunk(inp.citation.chunk_id)
        if row is None:
            return VerifyCitationOutput(exists=False)
        return VerifyCitationOutput(exists=True, status=row.status, fields_match=row.citation() == inp.citation)

    def list_active_versions(self, inp: ListActiveVersionsInput) -> ListActiveVersionsOutput:
        fid = _uuid(inp.family_id)
        if fid is None:
            return ListActiveVersionsOutput(family_id=inp.family_id, active=None)
        row = self._conn.execute(
            "select doc_id::text, family_id::text, title, doc_type::text, version, effective_from, effective_to from documents where family_id = %s and status = 'active'",
            (fid,),
        ).fetchone()
        if row is None:
            return ListActiveVersionsOutput(family_id=inp.family_id, active=None)
        view = DocumentVersionView(
            doc_id=row[0],
            family_id=row[1],
            title=row[2],
            doc_type=DocType(row[3]),
            version=row[4],
            effective_from=row[5],
            effective_to=row[6],
        )
        return ListActiveVersionsOutput(family_id=inp.family_id, active=view)
