"""Shared builders for harness / verification / safety unit tests (synthetic content only)."""

from __future__ import annotations

import hashlib
from datetime import date

from medops.domain.common import Dept, DocStatus
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence(
    chunk_id: str,
    text: str,
    *,
    doc_id: str = "doc-1",
    version: str = "v1",
    page: int = 1,
    section: str = "S1",
    status: DocStatus = DocStatus.active,
    historical: bool = False,
) -> Evidence:
    return Evidence(
        citation=Citation(
            doc_id=doc_id,
            version=version,
            effective_date=date(2026, 1, 1),
            page=page,
            section=section,
            chunk_id=chunk_id,
        ),
        text=text,
        evidence_text_hash=sha(text),
        chunk_content_hash=sha("chunk:" + text),
        status=status,
        historical=historical,
    )


def user(dept: Dept = Dept.PV) -> UserContext:
    return UserContext(
        user_id="u-" + sha("tester")[:12], dept=dept, roles=("analyst",), acl_scopes=frozenset({f"{dept.value}:read"})
    )


def versions() -> VersionSet:
    return VersionSet(
        policy_version="policy-test-1", retrieval_version="retrieval-test-1", model_config_version="models-test-1"
    )
