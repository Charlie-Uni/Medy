"""M1-18 fact re-check: the pure decision over one fact-plane row, in the documented order, and the
Evidence it produces. Database visibility (RLS) is covered by tests/integration/test_fact_recheck.py."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from datetime import date

import pytest

from medops.domain import DocStatus
from medops.retrieval.recheck import FactRow, RejectReason, evidence_from, judge

AS_OF = date(2026, 6, 1)
TEXT = "每次 0.5 g，每日 2 次。"
HASH = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()


def good(**overrides) -> FactRow:
    row = FactRow(
        chunk_id=str(uuid.uuid4()),
        doc_id=str(uuid.uuid4()),
        page=3,
        section="用法用量",
        content=TEXT,
        chunk_content_hash=HASH,
        version="2026-01",
        status="active",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        parse_quality="trusted",
        integrity_status="verified",
        has_offsets=True,
    )
    return replace(row, **overrides)


def test_a_sound_active_row_is_accepted_and_becomes_evidence_with_its_citation():
    row = good()
    reason, observed = judge(row, as_of=AS_OF, allow_historical=False)
    assert reason is None and observed == HASH
    ev = evidence_from(row, observed)
    assert ev.citation.model_dump() == {
        "doc_id": row.doc_id,
        "version": "2026-01",
        "effective_date": date(2026, 1, 1),
        "page": 3,
        "section": "用法用量",
        "chunk_id": row.chunk_id,
    }
    assert ev.text == TEXT and ev.evidence_text_hash == HASH and ev.chunk_content_hash == HASH
    assert ev.status is DocStatus.active and ev.historical is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"status": "archived"}, RejectReason.status_not_active),
        ({"status": "withdrawn"}, RejectReason.status_not_active),
        ({"status": "draft"}, RejectReason.status_not_active),
        ({"effective_from": date(2026, 6, 2)}, RejectReason.not_yet_effective),
        ({"effective_from": None}, RejectReason.not_yet_effective),
        ({"effective_to": date(2026, 6, 1)}, RejectReason.expired),
        ({"integrity_status": "pending"}, RejectReason.source_integrity_not_verified),
        ({"integrity_status": "failed"}, RejectReason.source_integrity_not_verified),
        ({"integrity_status": None}, RejectReason.source_integrity_not_verified),
        ({"parse_quality": "low_trust"}, RejectReason.parse_quality_not_trusted),
        ({"chunk_content_hash": "0" * 64}, RejectReason.content_hash_mismatch),
        ({"content": TEXT + " "}, RejectReason.content_hash_mismatch),
        ({"has_offsets": False}, RejectReason.no_source_offsets),
    ],
)
def test_each_rule_rejects_with_its_reason(overrides, reason):
    got, observed = judge(good(**overrides), as_of=AS_OF, allow_historical=False)
    assert got is reason
    assert observed == hashlib.sha256(good(**overrides).content.encode("utf-8")).hexdigest()


def test_window_boundaries_follow_baseline_3_4():
    assert judge(good(effective_from=AS_OF), as_of=AS_OF, allow_historical=False)[0] is None  # from <= as_of
    assert judge(good(effective_to=AS_OF), as_of=AS_OF, allow_historical=False)[0] is RejectReason.expired  # to > as_of
    assert judge(good(effective_to=date(2026, 6, 2)), as_of=AS_OF, allow_historical=False)[0] is None


def test_first_failing_reason_wins_in_the_documented_order():
    row = good(status="archived", integrity_status="failed", chunk_content_hash="0" * 64, has_offsets=False)
    assert judge(row, as_of=AS_OF, allow_historical=False)[0] is RejectReason.status_not_active
    row = good(integrity_status="failed", chunk_content_hash="0" * 64, has_offsets=False)
    assert judge(row, as_of=AS_OF, allow_historical=False)[0] is RejectReason.source_integrity_not_verified
    row = good(chunk_content_hash="0" * 64, has_offsets=False)
    assert judge(row, as_of=AS_OF, allow_historical=False)[0] is RejectReason.content_hash_mismatch


def test_archived_rows_are_historical_evidence_only_when_explicitly_allowed_and_inside_their_window():
    archived = good(status="archived", effective_from=date(2025, 1, 1), effective_to=date(2026, 1, 1))
    assert judge(archived, as_of=date(2025, 6, 1), allow_historical=False)[0] is RejectReason.status_not_active
    reason, observed = judge(archived, as_of=date(2025, 6, 1), allow_historical=True)
    assert reason is None
    ev = evidence_from(archived, observed)
    assert ev.status is DocStatus.archived and ev.historical is True
    assert judge(archived, as_of=date(2026, 6, 1), allow_historical=True)[0] is RejectReason.expired
    assert judge(archived, as_of=date(2024, 6, 1), allow_historical=True)[0] is RejectReason.not_yet_effective
    # historical mode never widens anything else
    for status in ("draft", "withdrawn"):
        assert judge(good(status=status), as_of=AS_OF, allow_historical=True)[0] is RejectReason.status_not_active


def test_evidence_model_refuses_what_judge_would_never_pass():
    # evidence_from is only called after judge; the domain model is the second line of defence
    with pytest.raises(ValueError, match="draft"):
        evidence_from(good(status="draft"), HASH)
