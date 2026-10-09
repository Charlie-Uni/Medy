"""Persist each successful preflight before any measured or paid query; resume adds a new snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash, canonical_json, sha256_hex


def save_preflight(out: Path, planes: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    if not planes or any(status.get("ready") is not True for status in planes.values()):
        raise ValueError("only successful nonempty plane preflights can start a measured run")
    value = {
        "format": "retrieval-preflight-v1",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "planes": dict(planes),
        "scope": "active production departmental-BM25/vector coverage and metadata; not a quality score or a long-lived guarantee",
    }
    data = (canonical_json(value) + "\n").encode()
    relative = Path("preflights") / f"{canonical_hash(value)}.json"
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(data)
    return {"path": relative.as_posix(), "sha256": sha256_hex(data)}
