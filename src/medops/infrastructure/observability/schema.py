"""Allowlisted score wire schema and deterministic identity; no network or queue I/O."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from medops.core.canonical import canonical_hash
from medops.core.tracing import is_valid_trace_id

FORMAT = "medops-observation-score-v1"
_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_METADATA = frozenset(
    {
        "source",
        "evaluator",
        "rubric_version",
        "scoring_version",
        "dataset_version",
        "dataset_hash",
        "sample_id",
        "sample_input_sha256",
        "run_conditions_sha256",
        "attempt_id",
        "policy_version",
        "retrieval_version",
        "model_config_version",
        "feedback_id",
        "fact_plane",
        "formal_gate",
    }
)


def utc_timestamp(value: str | datetime) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("score timestamp must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def score_event(
    *,
    identity: str,
    trace_id: str,
    name: str,
    value: str | float | bool,
    timestamp: str | datetime,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not identity or not is_valid_trace_id(trace_id) or not int(trace_id, 16) or not _NAME.fullmatch(name):
        raise ValueError("score needs a stable identity, W3C trace id and bounded metric name")
    if set(metadata) - _METADATA or any(not isinstance(v, (str, bool)) for v in metadata.values()):
        raise ValueError("score metadata must contain only approved scalar identifiers")
    if any(isinstance(v, str) and len(v) > 300 for v in metadata.values()):
        raise ValueError("score metadata identifier too long")
    encoded: str | float | int
    if isinstance(value, bool):
        data_type, encoded = "BOOLEAN", int(value)
    elif isinstance(value, (int, float)) and math.isfinite(value):
        data_type, encoded = "NUMERIC", float(value)
    elif isinstance(value, str) and _NAME.fullmatch(value):
        data_type, encoded = "CATEGORICAL", value
    else:
        raise ValueError("score value must be finite numeric, bool or a controlled category")
    score_id = canonical_hash({"format": FORMAT, "identity": identity, "trace_id": trace_id, "name": name})
    return {
        "id": score_id,
        "type": "score-create",
        "timestamp": utc_timestamp(timestamp),
        "body": {
            "id": score_id,
            "traceId": trace_id,
            "name": name,
            "value": encoded,
            "dataType": data_type,
            "metadata": dict(metadata),
        },
    }


def validate_score_event(event: dict[str, Any]) -> None:
    try:
        body = event["body"]
        value = body["value"]
        if body["dataType"] == "BOOLEAN":
            if type(value) is not int or value not in (0, 1):
                raise ValueError("invalid boolean")
            value = bool(value)
        rebuilt = score_event(
            identity="validation",
            trace_id=body["traceId"],
            name=body["name"],
            value=value,
            timestamp=event["timestamp"],
            metadata=body["metadata"],
        )
        if not re.fullmatch(r"[0-9a-f]{64}", event["id"]):
            raise ValueError("invalid id")
        rebuilt["id"] = rebuilt["body"]["id"] = event["id"]
        if rebuilt != event:
            raise ValueError("score fields differ")
    except (TypeError, KeyError, AttributeError, ValueError):
        raise ValueError("invalid or non-allowlisted score event") from None


def feedback_event(row: Mapping[str, Any], *, fact_plane: str) -> dict[str, Any]:
    if row["signal"] not in {"up", "down", "correction"}:
        raise ValueError("unsupported feedback signal")
    return score_event(
        identity=f"feedback:{fact_plane}:{row['feedback_id']}",
        trace_id=row["trace_id"],
        name="user_feedback",
        value=row["signal"],
        timestamp=row["created_at"],
        metadata={
            "source": "authenticated_user_feedback",
            "feedback_id": str(row["feedback_id"]),
            "fact_plane": fact_plane,
            "formal_gate": False,
        },
    )
