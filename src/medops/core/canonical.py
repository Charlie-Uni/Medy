"""Canonical JSON, hashing and the stable operation key (baseline section 3.2).

Rules (baseline 3.2): canonical_json is UTF-8, object keys sorted, stable number and
null representation, no insignificant whitespace, no NaN/Infinity. Plain string
concatenation is forbidden for keys; fields are joined with the ASCII unit separator
(U+001F) so that ("ab", "c") and ("a", "bc") can never collide.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

FIELD_SEPARATOR = "\x1f"


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical_json does not allow NaN or Infinity")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical_json requires string object keys")
            _reject_non_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_non_finite(item)
    elif isinstance(value, (set, frozenset)):
        raise TypeError("canonical_json does not accept sets; use a sorted list")


def canonical_json(value: Any) -> str:
    """Serialize `value` deterministically. Raises on non-JSON or non-finite input."""
    _reject_non_finite(value)
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    """SHA-256 of the UTF-8 canonical JSON of `value`."""
    return sha256_hex(canonical_json(value))


def operation_key(
    operation_scope: str,
    run_id: str,
    node_name: str,
    input_and_versions: Mapping[str, Any],
) -> str:
    """Stable idempotency key defined in baseline 3.2.

    operation_key = SHA-256(scope U+001F run_id U+001F node_name U+001F canonical_json(input_and_versions))

    `run_id` is the trace_id for production runs and a separate replay_run_id for replays.
    `input_and_versions` must include the node input plus policy_version, retrieval_version,
    skill_version_set and the model configuration version; callers are responsible for that.
    """
    for label, part in (("operation_scope", operation_scope), ("run_id", run_id), ("node_name", node_name)):
        if not part:
            raise ValueError(f"{label} must be a non-empty string")
        if FIELD_SEPARATOR in part:
            raise ValueError(f"{label} must not contain the field separator U+001F")
    payload = FIELD_SEPARATOR.join((operation_scope, run_id, node_name, canonical_json(dict(input_and_versions))))
    return sha256_hex(payload)
