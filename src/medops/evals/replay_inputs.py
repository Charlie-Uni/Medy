"""Self-contained safety inputs and source-run checks for newly built replay sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash
from medops.evals.safety_data import PRODUCTION_DB

SAFETY_INPUT_FORMAT = "embedded-safety-sample-v1"


def validate_source_run(directory: Path, manifest: dict, results: dict) -> None:
    """Require evidence of execution against the exact frozen dataset, not just a version name."""
    expected = {key: manifest[key] for key in ("dataset_id", "dataset_version", "dataset_hash")}
    binding = directory / "dataset_binding.json"
    if not binding.exists() or json.loads(binding.read_text()) != expected:
        raise ValueError(f"{directory.name}: source run needs the exact frozen dataset binding")
    dataset = results.get("dataset") or {}
    if dataset.get("version") != manifest["dataset_version"] or dataset.get("dataset_hash") != manifest["dataset_hash"]:
        raise ValueError(f"{directory.name}: results dataset identity differs from its binding")


def validate_complete_source_rows(
    samples: dict[str, dict], rows: dict[str, dict], *, versions: dict, safety: bool = False
) -> None:
    if not samples or set(samples) != set(rows):
        raise ValueError("source run must cover exactly the frozen samples; partial or extra rows cannot be frozen")
    for sid, sample in samples.items():
        row = rows[sid]
        if row.get("versions") != versions:
            raise ValueError(f"{sid}: source row runtime versions differ from its results")
        if row.get("sample_input_sha256") != canonical_hash(sample):
            raise ValueError(f"{sid}: source row lacks a matching full sample hash")
        for key in ("query", "dept", "language", "slices"):
            if row.get(key) != sample.get(key):
                raise ValueError(f"{sid}: source row {key} differs from frozen sample")
        if safety:
            for key in ("category", "expected"):
                if row.get(key) != sample.get(key):
                    raise ValueError(f"{sid}: source row {key} differs from frozen sample")
            checks = row.get("checks")
            if not isinstance(checks, list) or not checks or any(type(c.get("ok")) is not bool for c in checks):
                raise ValueError(f"{sid}: source safety checks are missing or invalid")
            failures = [c["check"] for c in checks if not c["ok"]]
            if row.get("passed") is not (not failures) or row.get("failed_checks") != failures:
                raise ValueError(f"{sid}: source safety verdict differs from its checks")
        else:
            kind = (
                "no_answer"
                if sample.get("answerable", True) is False
                else ("conflict" if sample.get("conflict") else "answerable")
            )
            if row.get("kind") != kind or row.get("expected_behaviour") != sample.get("expected_behaviour"):
                raise ValueError(f"{sid}: source main expectation differs from frozen sample")
            groups = row.get("required_gold_groups")
            if not isinstance(groups, list) or len(groups) != len(sample.get("required_gold_evidence", [])):
                raise ValueError(f"{sid}: source main gold groups are incomplete")
            if any(not isinstance(g, list) or any(not isinstance(c, str) for c in g) for g in groups):
                raise ValueError(f"{sid}: source main gold groups are invalid")
            if sorted(set(row.get("gold_chunks") or [])) != sorted({c for g in groups for c in g}):
                raise ValueError(f"{sid}: source main flat gold differs from its required groups")


def safety_samples_for_replay(manifest: dict, items: list[dict]) -> dict[str, dict[str, Any]]:
    """Load complete execution inputs from the replay itself, before any GPU/model/DB work.

    Historical replay files stay readable for reports, but their omitted ACL/attack/skill inputs
    cannot be recovered safely from today's mutable drafts. New safety execution requires a new set.
    """
    if not items:
        return {}
    if manifest.get("safety_input_format") != SAFETY_INPUT_FORMAT:
        raise ValueError("legacy replay safety inputs are not self-contained; use a new replay set or --skip-safety")
    version = manifest["sources"]["safety"]["dataset_version"]
    result = {}
    for item in items:
        sample = item.get("sample")
        sid = item["source"]["sample_id"]
        if not isinstance(sample, dict) or item.get("sample_sha256") != canonical_hash(sample):
            raise ValueError(f"{sid}: embedded safety sample hash mismatch")
        if sid in result or sample.get("sample_id") != sid:
            raise ValueError(f"{sid}: duplicate or mismatched safety sample id")
        if sample.get("dataset_version") != version or item["source"].get("dataset") != version:
            raise ValueError(f"{sid}: embedded safety dataset version mismatch")
        for key in ("query", "dept", "category", "language", "expected", "slices"):
            if sample.get(key) != item.get(key):
                raise ValueError(f"{sid}: embedded safety {key} differs from replay item")
        if (sample.get("historical") or None) != (item.get("historical") or None):
            raise ValueError(f"{sid}: embedded historical request differs from replay item")
        if (sample.get("database") or PRODUCTION_DB) != (item.get("database") or PRODUCTION_DB):
            raise ValueError(f"{sid}: embedded safety database differs from replay item")
        result[sid] = sample
    return result
