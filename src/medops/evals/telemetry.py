"""Export only version-bound rule scores. Missing/unexercised values never become zero scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash
from medops.evals.main_scoring import SCORING_VERSION, main_success
from medops.evals.run_conditions import FORMAT, validate_attempts
from medops.infrastructure.observability import score_event


def events_from_run(out: Path) -> list[dict[str, Any]]:
    binding = json.loads((out / "run_conditions.json").read_text(encoding="utf-8"))
    conditions = binding["conditions"]
    if conditions.get("format") != FORMAT or binding.get("sha256") != canonical_hash(conditions):
        raise ValueError("score export requires an intact run condition binding")
    dataset = json.loads((out / "dataset_binding.json").read_text(encoding="utf-8"))
    if (
        not dataset.get("dataset_version")
        or dataset.get("dataset_version") != conditions["inputs"].get("dataset_version")
        or not dataset.get("dataset_hash")
        or dataset.get("dataset_hash") != conditions["inputs"].get("dataset_hash")
    ):
        raise ValueError("score export requires the bound frozen dataset, not unversioned drafts")
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_attempts(rows, conditions)
    events = []
    for row in rows:
        if "kind" in row:
            if row.get("scoring_version") != SCORING_VERSION:
                raise ValueError("unsupported main score version")
            score = main_success(row, row["outcome"], row["cited_chunks"], row["reason_codes"])
            if row.get("success") is not score:
                raise ValueError("main score differs from its recorded rule")
            name, version = "main_outcome", SCORING_VERSION
        elif "category" in row:
            version = "safety-checks-code-bound-v1"
            if conditions["inputs"].get("scoring") != version:
                raise ValueError("unsupported safety score version")
            checks = row.get("checks")
            if not checks or any(type(c.get("ok")) is not bool for c in checks):
                raise ValueError("safety score requires actual boolean checks")
            score = all(c["ok"] for c in checks)
            if row.get("passed") is not score:
                raise ValueError("safety score differs from its recorded checks")
            name = "safety_checks"
        else:
            raise ValueError("unrecognized evaluation row")
        metadata = {
            "source": "rule",
            "evaluator": name,
            "rubric_version": version,
            "scoring_version": version,
            "dataset_version": dataset["dataset_version"],
            "dataset_hash": dataset["dataset_hash"],
            "sample_id": row["sample_id"],
            "sample_input_sha256": row["sample_input_sha256"],
            "run_conditions_sha256": binding["sha256"],
            "attempt_id": row["attempt_id"],
            "formal_gate": False,
            **{k: row["versions"][k] for k in ("policy_version", "retrieval_version", "model_config_version")},
        }
        # A run can be partial or contain retries. Export each attempt with its own identity, never
        # label these as a final dataset average or semantic answer quality.
        events.append(
            score_event(
                identity=f"eval:{binding['sha256']}:{row['attempt_id']}",
                trace_id=row["trace_id"],
                name="evaluation_status" if row.get("not_exercised") else name,
                value="not_exercised" if row.get("not_exercised") else score,
                timestamp=row["observed_at"],
                metadata=metadata,
            )
        )
    return events
