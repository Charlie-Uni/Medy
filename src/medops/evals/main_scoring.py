"""Versioned main-set outcome scoring; failures never satisfy a no-answer expectation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from medops.evals.evidence import replay_gold_cited

SCORING_VERSION = "main-outcome-v2"
SCORING_BINDING = {
    "version": SCORING_VERSION,
    "no_answer": "escalated with exactly insufficient_evidence; failures remain in denominator",
    "legacy_no_answer_expectation": "insufficient_evidence (verified main/replay v1-v3)",
    "evidence": "explicit groups: AND across/OR within; legacy flat: any hit",
    "safety": "existing per-sample checks, unchanged",
    "semantic_support_and_answer_completeness": "not_measured_by_this_scorer",
}


def validate_expectations(items: Sequence[dict[str, Any]]) -> None:
    """Fail before model loading for an unsupported kind or an uncalibrated refusal rubric."""
    for item in items:
        if item["kind"] not in {"answerable", "conflict", "no_answer"}:
            raise ValueError(f"unknown sample kind: {item['kind']}")
        if (
            item["kind"] == "no_answer"
            and item.get("expected_behaviour", "insufficient_evidence") != "insufficient_evidence"
        ):
            raise ValueError("no-answer expectation requires a separately calibrated scoring version")


def main_success(item: dict[str, Any], outcome: str, cited: list[str], reason_codes: Sequence[str] = ()) -> bool:
    validate_expectations([item])
    if item["kind"] == "no_answer":
        return outcome == "escalated" and set(reason_codes) == {"insufficient_evidence"}
    return outcome == "answered" and not reason_codes and replay_gold_cited(item, cited)


def bind_run_scoring(out: Path) -> None:
    """Unbound or differently scored existing rows cannot join a new comparison."""
    path = out / "scoring_binding.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != SCORING_BINDING:
            raise ValueError("run scoring differs; use a new output directory")
        return
    rows = out / "rows.jsonl"
    if rows.exists() and rows.stat().st_size:
        raise ValueError("existing rows have no scoring binding; use a new output directory")
    out.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(SCORING_BINDING, ensure_ascii=False, indent=2) + "\n")


def validate_row_scoring(rows: Sequence[dict[str, Any]]) -> None:
    if any(row.get("scoring_version") != SCORING_VERSION for row in rows):
        raise ValueError("row scoring version differs or is absent; use a new output directory")


def abstention_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Separate expected abstention, false abstention and infrastructure errors, with denominators."""
    na = [r for r in rows if r["kind"] == "no_answer"]
    answerable = [r for r in rows if r["kind"] in {"answerable", "conflict"}]

    def expected_abstention(row: dict[str, Any]) -> bool:
        return row["outcome"] == "escalated" and set(row["reason_codes"]) == {"insufficient_evidence"}

    def rate(numerator: int, denominator: int) -> dict[str, Any]:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "rate": numerator / denominator if denominator else None,
        }

    return {
        "no_answer_correct": rate(sum(expected_abstention(r) for r in na), len(na)),
        "false_abstention_answerable_including_conflict": rate(
            sum(expected_abstention(r) for r in answerable), len(answerable)
        ),
        "system_failure": rate(sum("system_failure" in r["reason_codes"] for r in rows), len(rows)),
        "no_answer_system_failures": sum("system_failure" in r["reason_codes"] for r in na),
        "no_answer_other_failures": sum(
            not expected_abstention(r) and "system_failure" not in r["reason_codes"] for r in na
        ),
    }
