"""Safety-set drafting is append-only (record 114): regenerating the drafts keeps the independent reviewer's verdicts
on unchanged rows, withdrawn samples move verbatim to drafts/withdrawn/ and stay loadable for frozen replay sets."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/safety_set/tools"))
_SPEC = importlib.util.spec_from_file_location("author_drafts_test", REPO / "evals/safety_set/tools/author_drafts.py")
ad = importlib.util.module_from_spec(_SPEC)
sys.modules["author_drafts_test"] = ad
_SPEC.loader.exec_module(ad)
import common  # noqa: E402

REVIEW = {"status": "agreed", "reviewer_verdict": "unique_and_decidable", "reviewer_note": "ok"}


def row(sid: str, query: str, *, version: str = "safety-v1-provisional", review: dict | None = None) -> dict:
    return {
        "sample_id": sid,
        "category": "ungrounded",
        "query": query,
        "expected": {"outcome": ["insufficient_evidence"]},
        "review": review or {"status": "pending"},
        "dataset_version": version,
    }


def test_unchanged_rows_keep_their_review_and_changed_or_new_rows_start_pending():
    existing = [row("ss-1", "q1", review=REVIEW), row("ss-2", "q2", review=REVIEW)]
    new = [
        row("ss-1", "q1", version="safety-v2-provisional"),
        row("ss-2", "q2 changed", version="safety-v2-provisional"),
        row("ss-3", "q3"),
    ]
    merged = ad.merge_reviews(new, existing)
    assert merged[0]["review"] == REVIEW and merged[0]["dataset_version"] == "safety-v2-provisional"
    assert merged[1]["review"] == {"status": "pending"}  # content changed: the old verdict no longer applies
    assert merged[2]["review"] == {"status": "pending"}


def test_withdrawn_rows_move_verbatim_and_accumulate():
    existing = [row("ss-1", "q1", review=REVIEW), row("ss-2", "q2")]
    already = [row("ss-0", "q0", review=REVIEW)]
    out = ad.split_withdrawn(existing, {"ss-1": ("ss-9", "why")}, already)
    assert [r["sample_id"] for r in out] == ["ss-0", "ss-1"]
    assert out[1] == existing[0]  # review and version untouched


def test_active_drafts_exclude_withdrawn_ids_but_frozen_sets_can_still_resolve_them():
    active = {r["sample_id"] for r in common.load_drafts()}
    everything = {r["sample_id"]: r for r in common.load_drafts(include_withdrawn=True)}
    withdrawn = set(everything) - active
    assert {"ss-0116", "ss-0121", "ss-0128"} <= withdrawn  # record 112: replaced in safety-v2
    assert {"ss-0171", "ss-0172", "ss-0173"} <= active
    assert all(everything[k]["dataset_version"] == "safety-v1-provisional" for k in withdrawn)
    assert all(r["dataset_version"] == common.DATASET_VERSION for r in common.load_drafts())
    assert len(active) == common.TOTAL_MIN
