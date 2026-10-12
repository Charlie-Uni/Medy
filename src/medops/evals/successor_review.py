"""Shared review mechanics; main/probe eligibility and adjudication stay separate."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from medops.evals.datasets import read_rows


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verdicts(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_rows(path)
    result = {row["sample_id"]: row for row in rows}
    require(len(result) == len(rows), f"duplicate verdict sample_id: {path}")
    return result


def latest_verdicts(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for sid, binding in run["latest"].items():
        chunk = run["chunks"][binding["chunk_index"]]
        matches = [row for row in chunk["verdicts"] if row["sample_id"] == sid]
        require(len(matches) == 1, f"{sid}: latest invocation does not contain one verdict")
        result[sid] = matches[0]
    return result


def annotate_prompt(run: dict[str, Any]) -> dict[str, Any]:
    run = copy.deepcopy(run)
    prompt_hash = run["review_prompt_sha256"]
    for chunk in run["chunks"]:
        observed = chunk.setdefault("review_prompt_sha256", prompt_hash)
        require(
            isinstance(observed, str) and len(observed) == 64 and set(observed) <= set("0123456789abcdef"),
            "source run contains an invalid per-invocation prompt hash",
        )
    return run


def append_review_run(merged: dict[str, Any], run: dict[str, Any], ids: set[str], prompt_hash: str) -> None:
    offset = len(merged["chunks"])
    merged["chunks"].extend(copy.deepcopy(run["chunks"]))
    merged["sample_input_sha256"].update({sid: run["sample_input_sha256"][sid] for sid in ids})
    for sid, binding in run["latest"].items():
        updated = copy.deepcopy(binding)
        updated["chunk_index"] += offset
        merged["latest"][sid] = updated
    merged["review_prompt_sha256"] = prompt_hash
