"""Shared duplicate-key rejection. Callers own size limits, schemas and safe errors."""

import json


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate_json_key")
    return value


def strict_json(data: str | bytes) -> object:
    """Reject duplicate keys at every depth, before schema validation."""
    return json.loads(data, object_pairs_hook=_unique_pairs)
