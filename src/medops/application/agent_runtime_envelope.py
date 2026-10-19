"""Stable AAD format shared by runtime writers and restricted historical readers.

No key, identity, database connection or execution authority is carried here.
Keep the pv-agent-runtime-v1 bytes compatible with already stored envelopes.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from medops.core.canonical import canonical_hash, canonical_json


def runtime_aad(run_id: UUID, conditions_sha256: str, kind: str, *parts: object) -> bytes:
    return canonical_json(["pv-agent-runtime-v1", str(run_id), conditions_sha256, kind, *map(str, parts)]).encode()


def head_aad(
    run_id: UUID,
    conditions_sha256: str,
    revision: int,
    lease_id: UUID,
    generation: int,
    budget: dict[str, Any],
    deadline: datetime,
    retained_until: datetime,
) -> bytes:
    return runtime_aad(
        run_id,
        conditions_sha256,
        "head",
        revision,
        lease_id,
        generation,
        canonical_hash(budget),
        deadline.astimezone(UTC).isoformat(timespec="microseconds"),
        retained_until.astimezone(UTC).isoformat(timespec="microseconds"),
    )
