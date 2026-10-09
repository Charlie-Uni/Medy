"""Bind a measured main/safety run to its actual inputs, fact snapshot and execution conditions.

The guard prevents accidental mixing on resume. It is not a signature, a database lock for the duration of
the run, or a promise of deterministic external model weights. Old unbound runs remain readable as history.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

import psycopg

from medops.application.policy_loader import ReleasedPolicySet
from medops.core.canonical import canonical_hash, canonical_json
from medops.evals.datasets import sha256_file
from medops.retrieval.integrity import has_global_view

FORMAT = "eval-run-conditions-v1"
FACT_RECHECK_INTERVAL_S = 300.0
PACKAGES = (
    "psycopg",
    "pgvector",
    "pydantic",
    "openai",
    "langgraph",
    "jieba",
    "numpy",
    "torch",
    "transformers",
    "sentence-transformers",
)
FACT_TABLES = {
    "source_objects": "source_object_id",
    "documents": "doc_id",
    "chunks": "chunk_id",
    "chunk_spans": "chunk_id,ordinal",
    "document_acl": "doc_id,dept,permission",
    "lexical_index_meta": "index_name",
    "embedding_index_meta": "embedding_version",
}


def policy_snapshot(released: ReleasedPolicySet) -> list[dict[str, str]]:
    return [
        {
            "policy_id": policy.policy_id,
            "kind": policy.kind,
            "name": policy.name,
            "version": policy.version,
            "diff_sha256": canonical_hash(policy.diff),
        }
        for policy in sorted(released.policies, key=lambda item: (item.kind, item.name, item.policy_id))
    ]


def fact_snapshot(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    """Stream ordered rows under an existing read-only REPEATABLE READ snapshot; only hashes leave here.

    Includes document windows, source identity, actual chunk text/anchors, ACL and semantic index metadata.
    Build bookkeeping is excluded so harmless outbox confirmations do not change the identity. Index vector
    bytes are not rehashed: index construction and query-time integrity still need their own checks.
    """
    if not conn.read_only or conn.isolation_level != psycopg.IsolationLevel.REPEATABLE_READ:
        raise ValueError("fact snapshot requires a read-only repeatable-read connection")
    if not has_global_view(conn):
        raise ValueError("fact snapshot requires global administrative visibility")
    tables = {}
    for table, order in FACT_TABLES.items():
        expression = "to_jsonb(t)"
        if table.endswith("_meta"):
            expression += " - 'built_at' - 'built_by' - 'chunk_count' - 'framework'"
        digest, count = hashlib.sha256(), 0
        with conn.cursor(name="snapshot_" + uuid.uuid4().hex) as cursor:
            cursor.execute(f"select {expression} from {table} t order by {order}")
            for row in cursor:
                digest.update((canonical_json(row[0]) + "\n").encode())
                count += 1
        tables[table] = {"rows": count, "sha256": digest.hexdigest()}
    return {"tables": tables, "sha256": canonical_hash(tables)}


def fact_snapshot_from_dsn(dsn: str, *, connect_timeout: int = 5, statement_timeout_ms: int = 5000) -> dict[str, Any]:
    """Capture a fresh global snapshot without reusing the runner's long-lived request connection."""
    with psycopg.connect(
        dsn,
        connect_timeout=connect_timeout,
        options=f"-c statement_timeout={statement_timeout_ms}",
    ) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        return fact_snapshot(conn)


class FactDriftError(RuntimeError):
    """The measured fact plane changed after this run was bound."""


@dataclass
class FactGuard:
    """Periodically re-hash fact planes and fail the whole measurement if one changes.

    A drifted directory cannot be resumed because its newly captured run conditions also differ. The interval limits
    database scan overhead; a forced check immediately before the report closes the final unchecked window.
    """

    expected: Mapping[str, Mapping[str, Any]]
    capture: Mapping[str, Callable[[], Mapping[str, Any]]]
    interval_s: float = FACT_RECHECK_INTERVAL_S
    clock: Callable[[], float] = time.monotonic
    _last_check: float | None = field(default=None, init=False)
    checks: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.interval_s <= 0 or set(self.expected) != set(self.capture):
            raise ValueError("fact guard needs the same nonempty planes and a positive interval")
        if not self.expected:
            raise ValueError("fact guard needs the same nonempty planes and a positive interval")

    def check(self, *, force: bool = False) -> None:
        now = self.clock()
        if not force and self._last_check is not None and now - self._last_check < self.interval_s:
            return
        changed = []
        for name in sorted(self.expected):
            observed = self.capture[name]()
            if observed.get("sha256") != self.expected[name].get("sha256"):
                changed.append(name)
        self._last_check = now
        self.checks += 1
        if changed:
            raise FactDriftError(
                f"fact plane changed during the run ({', '.join(changed)}); discard this measurement and use a new output directory"
            )


def source_snapshot(root: Path, runner: Path) -> dict[str, Any]:
    """Hash runtime sources/resources, schemas, dependency locks and this runner, including uncommitted code."""
    root = root.resolve()
    paths = {
        path
        for path in (root / "src/medops").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".json", ".yaml", ".yml", ".txt", ".stop"}
    }
    paths.update(root.glob("requirements*.lock"))
    paths.update((root / "schemas").glob("*.json"))
    paths.update((root / "pyproject.toml", runner.resolve()))
    files = {str(path.resolve().relative_to(root)): sha256_file(path) for path in sorted(paths)}
    return {"files": files, "sha256": canonical_hash(files)}


def environment_snapshot() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": versions,
    }


def make_conditions(
    *,
    root: Path,
    runner: Path,
    samples: Sequence[Mapping[str, Any]],
    versions: Mapping[str, Any],
    facts: Mapping[str, Mapping[str, Any]],
    configuration: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    plan = [{"sample_id": sample["sample_id"], "sha256": canonical_hash(sample)} for sample in samples]
    if not plan or len({item["sample_id"] for item in plan}) != len(plan):
        raise ValueError("measurement requires a nonempty unique sample plan")
    return {
        "format": FORMAT,
        "source": source_snapshot(root, runner),
        "environment": environment_snapshot(),
        "sample_plan": plan,
        "versions": dict(versions),
        "facts": dict(facts),
        "configuration": dict(configuration),
        "inputs": dict(inputs),
    }


def bind_conditions(out: Path, conditions: Mapping[str, Any]) -> str:
    if conditions.get("format") != FORMAT:
        raise ValueError("unknown run condition format")
    path = out / "run_conditions.json"
    digest = canonical_hash(conditions)
    value = {"sha256": digest, "conditions": dict(conditions)}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("sha256") != canonical_hash(old.get("conditions")):
            raise ValueError("run conditions file hash mismatch")
        if old != value:
            changed = sorted(
                key
                for key in set(old["conditions"]) | set(conditions)
                if old["conditions"].get(key) != conditions.get(key)
            )
            raise ValueError(f"run conditions changed ({', '.join(changed)}); use a new output directory")
        return digest
    rows = out / "rows.jsonl"
    if rows.exists() and rows.stat().st_size:
        raise ValueError("existing rows have no runtime/fact binding; use a new output directory")
    out.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return digest


def validate_attempts(rows: Sequence[Mapping[str, Any]], conditions: Mapping[str, Any]) -> None:
    digest = canonical_hash(conditions)
    samples = {item["sample_id"]: item["sha256"] for item in conditions["sample_plan"]}
    attempts: set[str] = set()
    for row in rows:
        _validate_attempt_fields(row, attempts)
        if (
            row.get("run_conditions_sha256") != digest
            or row.get("versions") != conditions["versions"]
            or row.get("sample_input_sha256") != samples.get(row.get("sample_id"))
            or row.get("sample_id") not in samples
        ):
            raise ValueError("row runtime/sample identity differs from the bound run")


def validate_replay_attempts(rows: Sequence[Mapping[str, Any]], conditions: Mapping[str, Any]) -> None:
    """Replay rows bind to one sample plus the actual version set of their baseline/candidate arm.

    A key may repeat only after a recorded system failure: replay resume deliberately appends a new attempt instead
    of erasing the failed one, so the complete cost/failure history remains auditable.
    """
    digest = canonical_hash(conditions)
    samples = {item["sample_id"]: item["sha256"] for item in conditions["sample_plan"]}
    versions = conditions.get("versions")
    if not isinstance(versions, Mapping) or not versions:
        raise ValueError("replay conditions need arm versions")
    attempts: set[str] = set()
    last_by_key: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for row in rows:
        _validate_attempt_fields(row, attempts)
        arm, replay_id, run = row.get("arm"), row.get("replay_id"), row.get("run")
        if (
            not isinstance(arm, str)
            or arm not in versions
            or not isinstance(replay_id, str)
            or not replay_id
            or not isinstance(run, int)
            or isinstance(run, bool)
            or run < 1
        ):
            raise ValueError("invalid replay arm, run or item identity")
        key = (arm, run, replay_id)
        previous = last_by_key.get(key)
        if previous is not None and "system_failure" not in previous.get("reason_codes", []):
            raise ValueError("duplicate replay item after a completed attempt")
        last_by_key[key] = row
        if (
            row.get("run_conditions_sha256") != digest
            or row.get("versions") != versions[arm]
            or row.get("sample_input_sha256") != samples.get(replay_id)
            or replay_id not in samples
        ):
            raise ValueError("replay row runtime/sample identity differs from the bound run")


def _validate_attempt_fields(row: Mapping[str, Any], attempts: set[str]) -> None:
    attempt_id = row.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id or attempt_id in attempts:
        raise ValueError("missing/duplicate attempt identity; refuse ambiguous cost and outcome history")
    attempts.add(attempt_id)
    cost, calls = row.get("cost_usd"), row.get("model_calls")
    if (
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or not math.isfinite(cost)
        or cost < 0
        or not isinstance(calls, int)
        or isinstance(calls, bool)
        or calls < 0
    ):
        raise ValueError("invalid recorded attempt cost or model call count")


def attempt_accounting(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """All recorded attempts, including overwritten failures; unrecorded provider charges remain unknown."""
    reused = [row for row in rows if row.get("reused_from")]
    return {
        "recorded_attempts": len(rows),
        "system_failure_attempts": sum("system_failure" in row.get("reason_codes", []) for row in rows),
        "cost_usd": round(sum(float(row["cost_usd"]) for row in rows), 6),
        "model_calls": sum(int(row["model_calls"]) for row in rows),
        "reused_attempts": len(reused),
        "reused_cost_usd": round(sum(float(row["cost_usd"]) for row in reused), 6),
        "scope": (
            "all attempts recorded in this directory, including provenance-preserving reused attempts; "
            "excludes unknown charges from a crash before the attempt was saved"
        ),
    }
