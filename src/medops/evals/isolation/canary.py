"""A public synthetic exercise: no hosted models, sealed tasks or medical gold."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from medops.evals.isolation.aggregate import (
    ExportPolicy,
    PrivateBatch,
    PrivateObservation,
    PublicSummary,
    ReleasedMetric,
    ReleaseGrant,
    SuppressedMetric,
    batch_digest,
    lock_digest,
    policy_digest,
    project_summary,
)
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


def export_self_check() -> dict[str, object]:
    """Exposed synthetic export example; numbers are not formal benchmark limits."""
    cases = tuple(
        PrivateCase(item_id=UUID(int=i), query=f"PUBLIC SYNTHETIC QUERY {i}", gold="PUBLIC SYNTHETIC GOLD")
        for i in range(1, 21)
    )
    inventory = PrivateInventory(
        collection_id=UUID(int=100),
        split="holdout",
        items=tuple(inventory_item(case, family_ids=(UUID(int=1000 + i),)) for i, case in enumerate(cases)),
    )
    manifest = public_manifest(inventory)
    digest = manifest_digest(manifest)
    lock = EvaluationLock(
        manifest_sha256=digest,
        baseline_sha256="a" * 64,
        candidate_sha256="b" * 64,
        rubric_sha256="c" * 64,
        protocol_sha256="d" * 64,
    )
    policy = ExportPolicy(
        policy_id=UUID(int=200),
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        metric_ids=(UUID(int=300),),
        rounds=3,
        min_tasks=20,
        min_families=2,
        min_cell_tasks=5,
    )
    batch = PrivateBatch(
        batch_id=UUID(int=400),
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        state="complete",
        observations=tuple(
            PrivateObservation(
                item_id=case.item_id,
                metric_id=policy.metric_ids[0],
                arm=arm,
                round=round_,
                result="passed" if i < (10 if arm == "baseline" else 15) else "failed",
            )
            for arm in ("baseline", "candidate")
            for round_ in range(1, 4)
            for i, case in enumerate(cases)
        ),
    )
    grant = ReleaseGrant(
        release_id=UUID(int=500),
        actor_id=UUID(int=600),
        role="holdout_evaluator",
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        policy_sha256=policy_digest(policy),
        batch_sha256=batch_digest(batch),
    )

    def summarize(value: PrivateBatch, permit: ReleaseGrant) -> PublicSummary:
        return project_summary(
            manifest=manifest, inventory=inventory, lock=lock, policy=policy, batch=value, grant=permit
        )

    result = summarize(batch, grant)
    metric = result.metrics[0]
    incomplete = batch.model_copy(update={"state": "running"})
    rare = batch.model_copy(
        update={
            "observations": tuple(
                row.model_copy(update={"result": "unknown"}) if row.item_id == cases[-1].item_id else row
                for row in batch.observations
            )
        }
    )
    suppressed = summarize(rare, grant.model_copy(update={"batch_sha256": batch_digest(rare)})).metrics[0]
    payload = result.model_dump_json()
    checks = {
        "whole_paired_batch": isinstance(metric, ReleasedMetric)
        and metric.baseline.executions == metric.candidate.executions == 60
        and result.unique_tasks == 20,
        "body_free_export": all(case.query not in payload and case.gold not in payload for case in cases)
        and "item_id" not in payload
        and "batch_sha256" not in payload,
        "partial_batch_denied": _refused(
            lambda: summarize(incomplete, grant.model_copy(update={"batch_sha256": batch_digest(incomplete)})),
            "batch_incomplete",
        ),
        "rare_metric_both_arms_suppressed": isinstance(suppressed, SuppressedMetric)
        and set(suppressed.model_dump()) == {"metric_id", "status"},
        "changed_rows_existing_grant_denied": _refused(lambda: summarize(rare, grant), "binding_mismatch"),
        "developer_grant_denied": _refused(
            lambda: summarize(batch, grant.model_copy(update={"role": "developer"})), "release_denied"
        ),
    }
    if not all(checks.values()):
        raise IsolationError("invalid_payload")
    return {
        "format": "eval-export-canary-v1",
        "checks": checks,
        "model_calls": 0,
        "qualification": "unknown",
        "deployment_isolation_verified": False,
        "independent_human_review_verified": False,
    }
