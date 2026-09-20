"""Fact-plane re-check of retrieval candidates (M1-18; baseline 3.3, 3.4, 3.7, 5.2; INV-DATA-03/06/07).

Index hits, fused ranks and reranker scores are not facts. Before a candidate chunk may become
`Evidence`, this module reads it back from the PostgreSQL fact plane inside the request transaction
that carries the trusted department identity and applies, in this order, the checks the baseline
fixes for "usable evidence":

1. visibility: the row must come back at all. Row-level security on `chunks -> documents -> document_acl`
   hides documents the department may not read, drafts and withdrawn documents alike, so a missing row
   is reported as `not_visible` and nothing else (the re-check never learns, and never reports, why);
2. status: `active`; `archived` only when the caller explicitly asked for historical evidence with an
   explicit `as_of` (INV-DATA-03), and then the evidence is marked `historical`;
3. effective window at `as_of`: `effective_from <= as_of` and (`effective_to` is null or `> as_of`);
4. source integrity: `source_objects.integrity_status = 'verified'`;
5. parse quality: `documents.parse_quality = 'trusted'` (INV-DATA-05);
6. content integrity: SHA-256 of the stored content, recomputed here, equals `chunk_content_hash`
   (expected/observed both reported so a trace can log them, baseline 3.3);
7. provenance: at least one page-anchored character span exists (INV-DATA-06 "可回看原文片段").

Every candidate is either accepted (an `Evidence` whose text is the stored chunk content and whose
`evidence_text_hash` is computed from that text) or rejected with exactly one reason; rejections are
outcomes, not errors, and are returned so the caller records them. Input order (the fused rank) is kept.

The re-check fails closed on anything that would make its filtering meaningless: no identity-bound
transaction, a connection whose role is not subject to the ACL policies (superuser, BYPASSRLS or the
administrative role), or a chunk id that is not a UUID (an adapter defect, not user input).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

import psycopg

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import DocStatus, DomainModel
from medops.domain.evidence import Citation, Evidence
from medops.retrieval.lexical.pg_lexical_common import require_identity

ADMIN_ROLE = "medops_admin_role"


class RejectReason(StrEnum):
    not_visible = "not_visible"
    status_not_active = "status_not_active"
    not_yet_effective = "not_yet_effective"
    expired = "expired"
    source_integrity_not_verified = "source_integrity_not_verified"
    parse_quality_not_trusted = "parse_quality_not_trusted"
    content_hash_mismatch = "content_hash_mismatch"
    no_source_offsets = "no_source_offsets"
    duplicate = "duplicate"


class Rejection(DomainModel):
    """One dropped candidate. `rank` is its 1-based position in the input. Hashes are present only for
    `content_hash_mismatch`; a `not_visible` rejection carries nothing but the id and the reason."""

    chunk_id: str
    rank: int
    reason: RejectReason
    expected_hash: str | None = None
    observed_hash: str | None = None


class RecheckResult(DomainModel):
    as_of: date
    historical_allowed: bool
    evidence: tuple[Evidence, ...]
    rejected: tuple[Rejection, ...]

    @property
    def accepted_ids(self) -> tuple[str, ...]:
        return tuple(e.citation.chunk_id for e in self.evidence)


@dataclass(frozen=True)
class FactRow:
    """What the fact plane says about one visible chunk (one row of `FACT_SQL`)."""

    chunk_id: str
    doc_id: str
    page: int
    section: str
    content: str
    chunk_content_hash: str
    version: str
    status: str
    effective_from: date | None
    effective_to: date | None
    parse_quality: str
    integrity_status: str | None
    has_offsets: bool


FACT_SQL = """
select c.chunk_id::text, c.doc_id::text, c.page, coalesce(c.section, ''), c.content, c.chunk_content_hash,
       d.version, d.status::text, d.effective_from, d.effective_to, d.parse_quality::text,
       s.integrity_status::text,
       exists (select 1 from chunk_spans sp where sp.chunk_id = c.chunk_id) as has_offsets
from chunks c
join documents d on d.doc_id = c.doc_id
left join source_objects s on s.source_object_id = d.source_object_id
where c.chunk_id = any(%(ids)s::uuid[])
"""


def judge(row: FactRow, *, as_of: date, allow_historical: bool) -> tuple[RejectReason | None, str]:
    """The pure decision for one visible row: `(None, observed_hash)` when it may become evidence,
    else the first failing reason in the documented order."""
    observed = hashlib.sha256(row.content.encode("utf-8")).hexdigest()
    if row.status == DocStatus.active.value:
        pass
    elif row.status == DocStatus.archived.value and allow_historical:
        pass
    else:
        return RejectReason.status_not_active, observed
    if row.effective_from is None or row.effective_from > as_of:
        return RejectReason.not_yet_effective, observed
    if row.effective_to is not None and row.effective_to <= as_of:
        return RejectReason.expired, observed
    if row.integrity_status != "verified":
        return RejectReason.source_integrity_not_verified, observed
    if row.parse_quality != "trusted":
        return RejectReason.parse_quality_not_trusted, observed
    if row.chunk_content_hash != observed:
        return RejectReason.content_hash_mismatch, observed
    if not row.has_offsets:
        return RejectReason.no_source_offsets, observed
    return None, observed


def evidence_from(row: FactRow, observed_hash: str) -> Evidence:
    assert row.effective_from is not None  # judged before
    status = DocStatus(row.status)
    return Evidence(
        citation=Citation(
            doc_id=row.doc_id,
            version=row.version,
            effective_date=row.effective_from,
            page=row.page,
            section=row.section,
            chunk_id=row.chunk_id,
        ),
        text=row.content,
        evidence_text_hash=observed_hash,
        chunk_content_hash=row.chunk_content_hash,
        status=status,
        historical=status is DocStatus.archived,
    )


def require_acl_enforced(conn: psycopg.Connection[Any]) -> None:
    """The re-check is only meaningful when row-level security applies to the connection's role: not a
    superuser, not BYPASSRLS, not (a member of) the administrative role whose policies allow everything."""
    row = conn.execute(
        "select rolsuper, rolbypassrls, pg_has_role(current_user, %s, 'member') from pg_roles where rolname = current_user",
        (ADMIN_ROLE,),
    ).fetchone()
    if row is None or any(row):
        raise InfrastructureError(
            ErrorCode.internal_error,
            detail="fact re-check must run under an application role subject to row-level security",
            retryable=False,
        )


def recheck_candidates(
    conn: psycopg.Connection[Any],
    chunk_ids: Sequence[str],
    *,
    as_of: date | None = None,
    allow_historical: bool = False,
) -> RecheckResult:
    """Re-read `chunk_ids` (fused rank order) from the fact plane under the caller's identity and return
    the accepted `Evidence` plus every rejection with its reason. See the module docstring for the rules."""
    if allow_historical and as_of is None:
        raise BusinessError(ErrorCode.invalid_request, "historical evidence requires an explicit as_of (INV-DATA-03)")
    require_identity(conn)
    require_acl_enforced(conn)
    when = as_of or date.today()
    ordered: list[str] = []
    for cid in chunk_ids:
        if not isinstance(cid, str):
            raise InfrastructureError(
                ErrorCode.internal_error, detail="candidate chunk_id is not a string", retryable=False
            )
        try:
            ordered.append(str(uuid.UUID(cid)))
        except ValueError:
            raise InfrastructureError(
                ErrorCode.internal_error, detail="candidate chunk_id is not a UUID", retryable=False
            ) from None
    rows: dict[str, FactRow] = {}
    if ordered:
        for record in conn.execute(FACT_SQL, {"ids": sorted(set(ordered))}):
            fact = FactRow(*record)
            rows[fact.chunk_id] = fact
    evidence: list[Evidence] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()
    for rank, cid in enumerate(ordered, start=1):
        if cid in seen:
            rejected.append(Rejection(chunk_id=cid, rank=rank, reason=RejectReason.duplicate))
            continue
        seen.add(cid)
        visible = rows.get(cid)
        if visible is None:
            rejected.append(Rejection(chunk_id=cid, rank=rank, reason=RejectReason.not_visible))
            continue
        row = visible
        reason, observed = judge(row, as_of=when, allow_historical=allow_historical)
        if reason is None:
            evidence.append(evidence_from(row, observed))
        elif reason is RejectReason.content_hash_mismatch:
            rejected.append(
                Rejection(
                    chunk_id=cid, rank=rank, reason=reason, expected_hash=row.chunk_content_hash, observed_hash=observed
                )
            )
        else:
            rejected.append(Rejection(chunk_id=cid, rank=rank, reason=reason))
    return RecheckResult(
        as_of=when, historical_allowed=allow_historical, evidence=tuple(evidence), rejected=tuple(rejected)
    )
