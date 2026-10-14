"""Bounded private sample-file reader, called after trusted custody authorization.

This layer accepts an already opened descriptor, never a model-supplied path.
It validates the complete pinned file before returning any private projection.
It does not authenticate a custodian, issue grants or establish unseen status.
"""

from __future__ import annotations

import hashlib
import math
import os
import stat
import time
from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from jsonschema import Draft202012Validator
from pydantic import Field

from medops.core.canonical import canonical_hash
from medops.domain.common import DomainModel, Sha256
from medops.evals.isolation.contracts import IsolationError, strict_json, validated_copy
from medops.evals.isolation.history import HistoryPlan, HistoryReceipt, history_plan_digest

# Exact existing schemas; schema changes require an explicit new reader version.
SUPPORTED_SAMPLE_SCHEMAS = frozenset(
    {
        "431f8cffef4b664fe4b1dcd8aeb23c8608bf00bd51e446c20988e11deb6c32be",
        "3bc57fb18442ea3f4a35296332187a65c6fa8547531894b9e6a1da46e535e04f",
    }
)


class HistoryReadLimits(DomainModel):
    max_file_bytes: int = Field(gt=0, le=33554432, strict=True)
    max_line_bytes: int = Field(gt=0, le=262144, strict=True)
    max_records: int = Field(gt=0, le=10000, strict=True)
    max_projected_chars: int = Field(gt=0, le=20000000, strict=True)


class PrivateHistoryGold(DomainModel):
    gold_id: str
    source_hash: Sha256
    version_label: str
    page: int
    printed_page_label: str | None
    section: str
    key_text: str
    text: str
    char_start: int
    char_end: int


class PrivateHistorySample(DomainModel):
    sample_id: str
    query: str
    derived_from: str | None
    gold: tuple[PrivateHistoryGold, ...]
    # Explicitly selected absence/conflict source metadata; not inferred family IDs.
    absence_document_key: str | None
    absence_topic: str | None
    absence_check: str | None
    absence_pages: tuple[int, ...]
    conflict_document_keys: tuple[str, ...]
    conflict_current_document_key: str | None
    conflict_topic: str | None
    conflict_synthetic: bool | None


class PrivateHistoryScan(DomainModel):
    format: Literal["eval-private-sample-scan-v1"] = "eval-private-sample-scan-v1"
    reader: Literal["main-probe-samples-v1"] = "main-probe-samples-v1"
    schema_sha256: Sha256
    limits_sha256: Sha256
    receipt: HistoryReceipt
    samples: tuple[PrivateHistorySample, ...]
    qualification: Literal["unknown"] = "unknown"
    historical_scope_exhaustive_verified: Literal[False] = False


def history_limits_digest(limits: HistoryReadLimits) -> str:
    return canonical_hash(validated_copy(HistoryReadLimits, limits, code="invalid_metadata").model_dump(mode="json"))


def _checkpoint(cancelled: Callable[[], bool], deadline: float) -> None:
    try:
        stop = cancelled()
    except Exception:  # noqa: BLE001 -- cancellation hook failure must not disclose its exception
        raise IsolationError("history_interrupted") from None
    if type(stop) is not bool or stop or time.monotonic() >= deadline:
        raise IsolationError("history_interrupted")


def _file_state(fd: int) -> tuple[int, int, int, int, int]:
    state = os.fstat(fd)
    if not stat.S_ISREG(state.st_mode) or state.st_mode & 0o077 or state.st_uid != os.getuid():
        raise IsolationError("history_io")
    return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns


def _capture(fd: int, limits: HistoryReadLimits, cancelled: Callable[[], bool], deadline: float) -> bytes:
    state = _file_state(fd)
    if state[2] > limits.max_file_bytes:
        raise IsolationError("history_limit")
    parts: list[bytes] = []
    size = 0
    while True:
        _checkpoint(cancelled, deadline)
        part = os.pread(fd, min(65536, limits.max_file_bytes + 1 - size), size)
        if not part:
            break
        parts.append(part)
        size += len(part)
        if size > limits.max_file_bytes:
            raise IsolationError("history_limit")
    if _file_state(fd) != state or size != state[2]:
        raise IsolationError("binding_mismatch")
    return b"".join(parts)


def _sample(row: dict[str, Any]) -> PrivateHistorySample:
    # Schema is fixed and validated first. Do not gather arbitrary nested strings.
    absence = row.get("abstention", {})
    conflict = row.get("conflict", {})
    return PrivateHistorySample(
        sample_id=row["sample_id"],
        query=row["query"],
        derived_from=row.get("derived_from"),
        gold=tuple(
            PrivateHistoryGold(
                gold_id=g["gold_id"],
                source_hash=g["source_hash"],
                version_label=g["version_label"],
                page=g["page"],
                printed_page_label=g["printed_page_label"],
                section=g["section"],
                key_text=g["key_text"],
                text=g["evidence_span"]["text"],
                char_start=g["evidence_span"]["char_start"],
                char_end=g["evidence_span"]["char_end"],
            )
            for g in row["required_gold_evidence"]
        ),
        absence_document_key=absence.get("scope_document_key"),
        absence_topic=absence.get("topic"),
        absence_check=absence.get("absence_check"),
        absence_pages=tuple(absence.get("document_pages", ())),
        conflict_document_keys=tuple(conflict.get("family_document_keys", ())),
        conflict_current_document_key=conflict.get("current_document_key"),
        conflict_topic=conflict.get("clause_topic"),
        conflict_synthetic=conflict.get("synthetic"),
    )


def scan_sample_file(
    fd: int,
    *,
    plan: HistoryPlan,
    artifact_id: UUID,
    expected_plan_sha256: str,
    schema_bytes: bytes,
    expected_schema_sha256: str,
    limits: HistoryReadLimits,
    expected_limits_sha256: str,
    cancelled: Callable[[], bool],
    deadline: float,
) -> PrivateHistoryScan:
    """All-or-nothing private projection. Caller must authorize/audit BEFORE opening.

    Deadline is an absolute monotonic deadline supplied by the trusted caller.
    Checkpoints are cooperative; a blocking filesystem syscall is not force-killed.
    No callback receives records, and no receipt is returned on any failure.
    """
    plan = validated_copy(HistoryPlan, plan, code="invalid_metadata")
    limits = validated_copy(HistoryReadLimits, limits, code="invalid_metadata")
    digest = history_plan_digest(plan)
    if digest != expected_plan_sha256 or history_limits_digest(limits) != expected_limits_sha256:
        raise IsolationError("binding_mismatch")
    requirement = next((r for r in plan.requirements if r.artifact_id == artifact_id), None)
    if requirement is None:
        raise IsolationError("binding_mismatch")
    if requirement.adapter != "dataset-fields-v1" or set(requirement.required_levels) != {"query", "gold", "source"}:
        raise IsolationError("history_unsupported")
    if type(fd) is not int or type(deadline) is not float or not math.isfinite(deadline):
        raise IsolationError("invalid_metadata")
    if type(schema_bytes) is not bytes or len(schema_bytes) > 65536:
        raise IsolationError("history_limit")
    schema_sha = hashlib.sha256(schema_bytes).hexdigest()
    if schema_sha != expected_schema_sha256:
        raise IsolationError("binding_mismatch")
    if schema_sha not in SUPPORTED_SAMPLE_SCHEMAS:
        raise IsolationError("history_unsupported")
    try:
        _checkpoint(cancelled, deadline)
        validator = Draft202012Validator(strict_json(schema_bytes))
        initial = _file_state(fd)
        raw = _capture(fd, limits, cancelled, deadline)
        if hashlib.sha256(raw).hexdigest() != requirement.artifact_sha256:
            raise IsolationError("binding_mismatch")
        samples: list[PrivateHistorySample] = []
        ids: set[str] = set()
        projected_chars = 0
        # Only LF is a record separator; never split escaped Unicode line separators.
        cursor = 0
        while cursor < len(raw):
            _checkpoint(cancelled, deadline)
            end = raw.find(b"\n", cursor)
            if end < 0:
                end = len(raw)
            if end - cursor > limits.max_line_bytes:
                raise IsolationError("history_limit")
            line = raw[cursor:end]
            cursor = end + 1
            if not line.strip(b" \t\r"):
                continue
            if len(samples) >= limits.max_records:
                raise IsolationError("history_limit")
            row = strict_json(line.decode("utf-8", errors="strict"))
            if not isinstance(row, dict) or not validator.is_valid(row):
                raise IsolationError("invalid_payload")
            sample = _sample(row)
            if sample.sample_id in ids:
                raise IsolationError("invalid_payload")
            # These cross-field invariants are not enforced by the JSON Schema.
            for gold in sample.gold:
                if (
                    not gold.gold_id.startswith(sample.sample_id + "-g")
                    or gold.char_end <= gold.char_start
                    or gold.char_end - gold.char_start != len(gold.text)
                    or gold.key_text not in gold.text
                ):
                    raise IsolationError("invalid_payload")
            if len({g.gold_id for g in sample.gold}) != len(sample.gold):
                raise IsolationError("invalid_payload")
            serialized = sample.model_dump_json()
            projected_chars += len(serialized)
            if projected_chars > limits.max_projected_chars:
                raise IsolationError("history_limit")
            samples.append(sample)
            ids.add(sample.sample_id)
        _checkpoint(cancelled, deadline)
        if _file_state(fd) != initial:
            raise IsolationError("binding_mismatch")
        return PrivateHistoryScan(
            schema_sha256=schema_sha,
            limits_sha256=expected_limits_sha256,
            receipt=HistoryReceipt(
                artifact_id=requirement.artifact_id,
                plan_sha256=digest,
                adapter=requirement.adapter,
                artifact_sha256=requirement.artifact_sha256,
                state="checked",
                checked_levels=requirement.required_levels,
                record_count=len(samples),
            ),
            samples=tuple(samples),
        )
    except IsolationError:
        raise
    except OSError:
        raise IsolationError("history_io") from None
    except (ValueError, TypeError, RecursionError):
        # Re-raise our fixed codes; never expose parser/schema/validation inputs.
        raise IsolationError("invalid_payload") from None
