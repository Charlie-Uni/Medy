"""Closed, paired batch export; not a scorer, privacy proof or authenticated issuer.

Only whole-collection binary tallies are supported. Thresholds and metric IDs
come from a trusted pre-registered policy; no production/Agent defaults are set.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from medops.core.canonical import canonical_hash
from medops.domain.common import DomainModel, Sha256
from medops.evals.isolation.contracts import (
    EvaluationLock,
    IsolationError,
    PrivateInventory,
    PublicManifest,
    Role,
    validated_copy,
)
from medops.evals.isolation.manifests import bind_inventory, manifest_digest

Arm = Literal["baseline", "candidate"]
Result = Literal["passed", "failed", "unknown"]
ARMS: tuple[Arm, ...] = ("baseline", "candidate")
RESULTS: tuple[Result, ...] = ("passed", "failed", "unknown")
MAX_OBSERVATIONS = 100000


class ExportPolicy(DomainModel):
    """All limits explicit; authenticating pre-registration is a deployment gate."""

    policy_id: UUID
    manifest_sha256: Sha256
    lock_sha256: Sha256
    metric_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)
    rounds: int = Field(ge=1, le=3, strict=True)
    min_tasks: int = Field(ge=2, le=10000, strict=True)
    min_families: int = Field(ge=2, le=10000, strict=True)
    min_cell_tasks: int = Field(ge=2, le=10000, strict=True)

    @model_validator(mode="after")
    def unique_metrics(self) -> ExportPolicy:
        if len(set(self.metric_ids)) != len(self.metric_ids):
            raise ValueError("invalid_metadata")
        return self


class PrivateObservation(DomainModel):
    item_id: UUID
    metric_id: UUID
    arm: Arm
    round: int = Field(ge=1, le=3, strict=True)
    result: Result


class PrivateBatch(DomainModel):
    format: Literal["eval-private-batch-v1"] = "eval-private-batch-v1"
    batch_id: UUID
    manifest_sha256: Sha256
    lock_sha256: Sha256
    state: Literal["running", "complete", "failed", "cancelled"]
    observations: tuple[PrivateObservation, ...] = Field(min_length=1, max_length=MAX_OBSERVATIONS)


class ReleaseGrant(DomainModel):
    """Trusted issuer pins one complete result, not just a mutable batch ID."""

    release_id: UUID
    actor_id: UUID
    role: Role
    manifest_sha256: Sha256
    lock_sha256: Sha256
    policy_sha256: Sha256
    batch_sha256: Sha256


class ArmCounts(DomainModel):
    executions: int = Field(ge=1, le=MAX_OBSERVATIONS, strict=True)
    passed: int = Field(ge=0, le=MAX_OBSERVATIONS, strict=True)
    failed: int = Field(ge=0, le=MAX_OBSERVATIONS, strict=True)
    unknown: int = Field(ge=0, le=MAX_OBSERVATIONS, strict=True)

    @model_validator(mode="after")
    def consistent_counts(self) -> ArmCounts:
        if self.passed + self.failed + self.unknown != self.executions:
            raise ValueError("invalid_metadata")
        return self


class ReleasedMetric(DomainModel):
    metric_id: UUID
    status: Literal["released"] = "released"
    baseline: ArmCounts
    candidate: ArmCounts


class SuppressedMetric(DomainModel):
    metric_id: UUID
    status: Literal["suppressed"] = "suppressed"


class PublicSummary(DomainModel):
    format: Literal["eval-public-summary-v1"] = "eval-public-summary-v1"
    release_id: UUID
    batch_id: UUID
    collection_id: UUID
    manifest_sha256: Sha256
    lock_sha256: Sha256
    policy_sha256: Sha256
    unique_tasks: int = Field(ge=2, le=10000, strict=True)
    families: int = Field(ge=2, strict=True)
    rounds: int = Field(ge=1, le=3, strict=True)
    metrics: tuple[ReleasedMetric | SuppressedMetric, ...] = Field(min_length=1, max_length=32)
    qualification: Literal["unknown"] = "unknown"
    deployment_isolation_verified: Literal[False] = False
    independent_human_review_verified: Literal[False] = False


def lock_digest(lock: EvaluationLock) -> str:
    return canonical_hash(validated_copy(EvaluationLock, lock, code="invalid_metadata").model_dump(mode="json"))


def policy_digest(policy: ExportPolicy) -> str:
    return canonical_hash(validated_copy(ExportPolicy, policy, code="invalid_metadata").model_dump(mode="json"))


def batch_digest(batch: PrivateBatch) -> str:
    value = validated_copy(PrivateBatch, batch, code="invalid_metadata").model_dump(mode="json")
    value["observations"] = sorted(
        value["observations"], key=lambda row: (row["metric_id"], row["arm"], row["round"], row["item_id"])
    )
    return canonical_hash(value)


def project_summary(
    *,
    manifest: PublicManifest,
    inventory: PrivateInventory,
    lock: EvaluationLock,
    policy: ExportPolicy,
    batch: PrivateBatch,
    grant: ReleaseGrant,
) -> PublicSummary:
    """No item/cohort/round projections; do not accept grants from a model."""
    grant = validated_copy(ReleaseGrant, grant, code="release_denied")
    manifest = validated_copy(PublicManifest, manifest, code="invalid_metadata")
    permitted = {"custodian", "holdout_evaluator"} if manifest.split == "holdout" else {"custodian", "validator"}
    if grant.role not in permitted:
        raise IsolationError("release_denied")
    inventory = validated_copy(PrivateInventory, inventory, code="invalid_metadata")
    bind_inventory(manifest, inventory)
    lock = validated_copy(EvaluationLock, lock, code="invalid_metadata")
    policy = validated_copy(ExportPolicy, policy, code="invalid_metadata")
    batch = validated_copy(PrivateBatch, batch, code="invalid_metadata")
    manifest_sha, lock_sha, policy_sha = manifest_digest(manifest), lock_digest(lock), policy_digest(policy)
    if (
        lock.manifest_sha256 != manifest_sha
        or any(
            value != manifest_sha for value in (policy.manifest_sha256, batch.manifest_sha256, grant.manifest_sha256)
        )
        or any(value != lock_sha for value in (policy.lock_sha256, batch.lock_sha256, grant.lock_sha256))
        or grant.policy_sha256 != policy_sha
        or grant.batch_sha256 != batch_digest(batch)
    ):
        raise IsolationError("binding_mismatch")
    if batch.state != "complete":
        raise IsolationError("batch_incomplete")
    if manifest.item_count < policy.min_tasks or manifest.family_count < policy.min_families:
        raise IsolationError("aggregate_too_small")
    item_ids, metric_ids = {item.item_id for item in inventory.items}, set(policy.metric_ids)
    families_by_item = {item.item_id: set(item.family_ids) for item in inventory.items}
    expected_count = len(item_ids) * len(metric_ids) * policy.rounds * len(ARMS)
    if expected_count > MAX_OBSERVATIONS:
        raise IsolationError("release_limit")
    expected = {
        (item, metric, arm, round_)
        for item in item_ids
        for metric in metric_ids
        for arm in ARMS
        for round_ in range(1, policy.rounds + 1)
    }
    actual = {(row.item_id, row.metric_id, row.arm, row.round) for row in batch.observations}
    if len(actual) != len(batch.observations) or actual != expected:
        raise IsolationError("batch_incomplete")
    counts: dict[tuple[UUID, Arm], Counter[Result]] = defaultdict(Counter)
    cells: dict[tuple[UUID, Arm, Result], set[UUID]] = defaultdict(set)
    for row in batch.observations:
        counts[row.metric_id, row.arm][row.result] += 1
        cells[row.metric_id, row.arm, row.result].add(row.item_id)
    metrics: list[ReleasedMetric | SuppressedMetric] = []

    def small_cell(metric: UUID, arm: Arm, result: Result) -> bool:
        ids = cells[metric, arm, result]
        families = {family for item in ids for family in families_by_item[item]}
        return bool(ids) and (len(ids) < policy.min_cell_tasks or len(families) < policy.min_families)

    for metric in sorted(metric_ids):
        if any(small_cell(metric, arm, result) for arm in ARMS for result in RESULTS):
            # Suppress both arms, not only the rare/complementary cell.
            metrics.append(SuppressedMetric(metric_id=metric))
            continue
        tallies = {
            arm: ArmCounts(
                executions=len(item_ids) * policy.rounds,
                passed=counts[metric, arm]["passed"],
                failed=counts[metric, arm]["failed"],
                unknown=counts[metric, arm]["unknown"],
            )
            for arm in ARMS
        }
        metrics.append(ReleasedMetric(metric_id=metric, baseline=tallies["baseline"], candidate=tallies["candidate"]))
    return PublicSummary(
        release_id=grant.release_id,
        batch_id=batch.batch_id,
        collection_id=manifest.collection_id,
        manifest_sha256=manifest_sha,
        lock_sha256=lock_sha,
        policy_sha256=policy_sha,
        unique_tasks=manifest.item_count,
        families=manifest.family_count,
        rounds=policy.rounds,
        metrics=tuple(metrics),
    )
