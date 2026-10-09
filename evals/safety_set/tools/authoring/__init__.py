"""Authoring helpers for the safety-set drafts (spec-s1 v0.2 §6 step 1). The per-class modules are the drafting
"templates": the drafter (claude-fable-5-1, Claude Code) wrote every query and expectation directly into them, so
the module file hashes are the provenance recorded in the manifest."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medops.evals.safety_data import DATASET_VERSION, DRAFTER, canary_for  # noqa: E402

__all__ = ["sample", "expect", "canary_for", "DRAFTER", "DATASET_VERSION"]


def expect(
    outcome: list[str],
    reason_codes: list[str] | None = None,
    *,
    escalation_required: bool = False,
    must_not_contain: list[str] | None = None,
    **flags: object,
) -> dict:
    exp: dict = {
        "outcome": outcome,
        "reason_codes": reason_codes or [],
        "escalation_required": escalation_required,
        "must_not_contain": must_not_contain or [],
    }
    exp.update({k: v for k, v in flags.items() if v not in (None, False, [], {})})
    return exp


def sample(
    sample_id: str,
    category: str,
    dept: str,
    language: str,
    query: str,
    expected: dict,
    *,
    slices: list[str] | None = None,
    notes: str = "",
    **extra: object,
) -> dict:
    row: dict = {
        "sample_id": sample_id,
        "category": category,
        "dept": dept,
        "language": language,
        "query": query,
        "expected": expected,
        "slices": slices or [],
        "drafted_by": dict(DRAFTER),
        "review": {"status": "pending"},
        "notes": notes,
        "dataset_version": DATASET_VERSION,
    }
    row.update({k: v for k, v in extra.items() if v is not None})
    return row
