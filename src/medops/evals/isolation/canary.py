"""A public synthetic exercise: no hosted models, sealed tasks or medical gold."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from medops.evals.isolation.contracts import (
    EvaluationLock,
    ExposureEvent,
    Failure,
    IsolationError,
    LedgerHead,
    PrivateCase,
    PrivateInventory,
    ReadGrant,
    RuntimeInput,
)
from medops.evals.isolation.exposure import append_event, exposure_status, read_ledger
from medops.evals.isolation.manifests import check_disjoint, inventory_item, manifest_digest, public_manifest
from medops.evals.isolation.projection import project_input


def _refused(operation: Callable[[], object], code: Failure) -> bool:
    try:
        operation()
    except IsolationError as error:
        return error.code == code
    return False


class _SyntheticStore:
    def __init__(self, case: PrivateCase):
        self.case = case
        self.review_reads = 0

    def load_input(self, item_id: UUID) -> RuntimeInput:
        return RuntimeInput(item_id=self.case.item_id, query=self.case.query)

    def load_review(self, item_id: UUID) -> PrivateCase:
        self.review_reads += 1
        return self.case


def self_check() -> dict[str, object]:
    """Exercise real package/file operations using disposable, already exposed data."""
    case = PrivateCase(item_id=UUID(int=1), query="PUBLIC SYNTHETIC QUERY", gold="SYNTHETIC GOLD CANARY")
    item = inventory_item(case, family_ids=(UUID(int=2),))
    inventory = PrivateInventory(collection_id=UUID(int=3), split="holdout", items=(item,))
    manifest = public_manifest(inventory)
    digest = manifest_digest(manifest)
    grant = ReadGrant(
        actor_id=UUID(int=4),
        role="runtime",
        collection_id=inventory.collection_id,
        manifest_sha256=digest,
        item_id=case.item_id,
    )
    lock = EvaluationLock(
        manifest_sha256=digest,
        baseline_sha256="a" * 64,
        candidate_sha256="b" * 64,
        rubric_sha256="c" * 64,
        protocol_sha256="d" * 64,
    )
    store = _SyntheticStore(case)
    projected = project_input(store, manifest=manifest, inventory=inventory, grant=grant, lock=lock)
    checks = {
        "public_projection": case.query not in manifest.model_dump_json()
        and case.gold not in manifest.model_dump_json(),
        "runtime_projection": set(projected.model_dump()) == {"item_id", "query"} and store.review_reads == 0,
        "generator_holdout_denied": _refused(
            lambda: project_input(
                store,
                manifest=manifest,
                inventory=inventory,
                grant=grant.model_copy(update={"role": "generator"}),
                lock=lock,
            ),
            "access_denied",
        ),
        "missing_lock_denied": _refused(
            lambda: project_input(store, manifest=manifest, inventory=inventory, grant=grant), "lock_required"
        ),
        "cross_split_overlap_denied": _refused(
            lambda: check_disjoint(
                (inventory, inventory.model_copy(update={"collection_id": UUID(int=5), "split": "development"}))
            ),
            "split_overlap",
        ),
    }
    event = ExposureEvent(
        event_id=UUID(int=6),
        occurred_at=datetime(2026, 10, 12, tzinfo=UTC),
        actor_id=grant.actor_id,
        role="generator",
        collection_id=inventory.collection_id,
        family_ids=item.family_ids,
        levels=("query",),
        purpose="candidate_generation",
        candidate_sha256=lock.candidate_sha256,
        receipt_sha256="e" * 64,
    )
    with TemporaryDirectory(prefix="medy-isolation-canary-") as folder:
        path = Path(folder) / "exposure.jsonl"
        initial = LedgerHead(sequence=0)
        head = append_event(path, event, expected=initial)
        entries = read_ledger(path, expected=head)
        checks["ledger_round_trip"] = len(entries) == 1 and entries[0].event == event
        checks["exposure_recorded"] = exposure_status(entries, collection_id=inventory.collection_id) == "exposed"
        checks["stale_head_denied"] = _refused(
            lambda: append_event(path, event, expected=initial), "ledger_head_changed"
        )
        path.write_bytes(path.read_bytes().replace(b'"generator"', b'"custodian"', 1))
        checks["tamper_denied"] = _refused(lambda: read_ledger(path, expected=head), "ledger_corrupt")
    if not all(checks.values()):
        raise IsolationError("invalid_payload")
    return {
        "format": "eval-isolation-canary-v1",
        "checks": checks,
        "model_calls": 0,
        "qualification": "unknown",
        "deployment_isolation_verified": False,
        "independent_human_review_verified": False,
    }
