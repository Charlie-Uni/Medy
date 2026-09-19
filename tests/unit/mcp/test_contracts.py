import hashlib
import re
from datetime import date

import pytest
from pydantic import ValidationError

from medops.domain import Citation, DocStatus, DocType
from medops.mcp.contracts import (
    MAX_K,
    MCP_TOOLS,
    ChunkView,
    DocumentVersionView,
    ListActiveVersionsOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SearchHit,
    VerifyCitationOutput,
)

CIT = Citation(
    doc_id="d1", version="2026-01", effective_date=date(2026, 1, 1), page=3, section="用法用量", chunk_id="c1"
)
CIT2 = CIT.model_copy(update={"chunk_id": "c2"})
CONTENT = "对本品过敏者禁用；孕妇禁用。"
HASH = hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()


def test_exactly_four_read_only_tools_with_stable_names():
    assert [t.name for t in MCP_TOOLS] == ["search_documents", "get_chunk", "verify_citation", "list_active_versions"]
    assert all(t.read_only for t in MCP_TOOLS)
    assert not any(re.search(r"create|update|delete|write|upload|publish", t.name) for t in MCP_TOOLS)


def test_tool_inputs_never_accept_identity_fields():
    with pytest.raises(ValidationError):
        SearchDocumentsInput(query="q", dept="MA")
    with pytest.raises(ValidationError):
        SearchDocumentsInput(query="q", scopes=["MA:read"])
    with pytest.raises(ValidationError):
        SearchDocumentsInput(query="q", k=MAX_K + 1)


def test_search_output_exhaustion_uniqueness_and_visibility():
    hit = SearchHit(citation=CIT, snippet="每次 0.5 g", status=DocStatus.active)
    assert SearchDocumentsOutput(hits=(hit,), requested_k=8, candidate_exhausted=True).candidate_exhausted
    with pytest.raises(ValidationError, match="candidate_exhausted"):
        SearchDocumentsOutput(hits=(hit,), requested_k=8, candidate_exhausted=False)
    with pytest.raises(ValidationError, match="repeat"):  # duplicates cannot fill K
        SearchDocumentsOutput(hits=(hit, hit), requested_k=2, candidate_exhausted=False)
    SearchDocumentsOutput(
        hits=(hit, SearchHit(citation=CIT2, snippet="x", status=DocStatus.active)),
        requested_k=2,
        candidate_exhausted=False,
    )
    with pytest.raises(ValidationError, match="never exposed"):
        SearchHit(citation=CIT, snippet="x", status=DocStatus.draft)
    with pytest.raises(ValidationError, match="withdrawn"):
        SearchHit(citation=CIT, snippet="x", status=DocStatus.withdrawn)
    with pytest.raises(ValidationError, match="historical"):
        SearchHit(citation=CIT, snippet="x", status=DocStatus.archived, historical=False)


def test_chunk_view_content_hash_is_recomputed():
    ok = ChunkView(citation=CIT, content=CONTENT, content_hash=HASH, status=DocStatus.active)
    assert ok.content_hash == HASH
    with pytest.raises(ValidationError, match="content_hash"):
        ChunkView(citation=CIT, content=CONTENT + "篡改", content_hash=HASH, status=DocStatus.active)
    with pytest.raises(ValidationError, match="content_hash"):
        ChunkView(citation=CIT, content=CONTENT, content_hash="a" * 64, status=DocStatus.active)
    with pytest.raises(ValidationError, match="never exposed"):
        ChunkView(citation=CIT, content=CONTENT, content_hash=HASH, status=DocStatus.draft)


def test_verify_citation_visibility_contract():
    VerifyCitationOutput(exists=False)
    with pytest.raises(ValidationError):
        VerifyCitationOutput(exists=False, status=DocStatus.active)
    with pytest.raises(ValidationError):
        VerifyCitationOutput(exists=True)
    with pytest.raises(ValidationError, match="never visible"):
        VerifyCitationOutput(exists=True, status=DocStatus.draft, fields_match=True)
    assert VerifyCitationOutput(exists=True, status=DocStatus.archived, fields_match=True).fields_match


def test_list_active_versions_family_and_window_consistency():
    view = DocumentVersionView(
        doc_id="d1", family_id="f1", title="t", doc_type=DocType.label, version="v1", effective_from=date(2026, 1, 1)
    )
    assert ListActiveVersionsOutput(family_id="f1", active=None).active is None
    assert ListActiveVersionsOutput(family_id="f1", active=view).active is view
    with pytest.raises(ValidationError, match="requested family"):
        ListActiveVersionsOutput(family_id="f2", active=view)
    with pytest.raises(ValidationError, match="effective_to"):
        DocumentVersionView(
            doc_id="d1",
            family_id="f1",
            title="t",
            doc_type=DocType.label,
            version="v1",
            effective_from=date(2026, 1, 1),
            effective_to=date(2025, 12, 31),
        )
