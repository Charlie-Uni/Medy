"""Validate receipts for a pinned historical scan scope; no parser or unseen verdict.

The trusted custodian must enumerate sources and authenticate receipts. Completing
this declared plan does not prove that all real history has been discovered.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from medops.core.canonical import canonical_hash
from medops.domain.common import DomainModel, Sha256
from medops.evals.isolation.contracts import IsolationError, Level, validated_copy

HistoryAdapter = Literal["dataset-fields-v1", "retrieval-fields-v1", "execution-fields-v1", "conversation-fields-v1"]


class HistoryRequirement(DomainModel):
    artifact_id: UUID
    artifact_sha256: Sha256
    adapter: HistoryAdapter
    required_levels: tuple[Level, ...] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_levels(self) -> HistoryRequirement:
        if len(set(self.required_levels)) != len(self.required_levels):
            raise ValueError("invalid_metadata")
        return self


class HistoryPlan(DomainModel):
    format: Literal["eval-history-plan-v1"] = "eval-history-plan-v1"
    scope_id: UUID
    requirements: tuple[HistoryRequirement, ...] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_artifacts(self) -> HistoryPlan:
        if len({item.artifact_id for item in self.requirements}) != len(self.requirements):
            raise ValueError("invalid_metadata")
        return self


class HistoryReceipt(DomainModel):
    artifact_id: UUID
    plan_sha256: Sha256
    adapter: HistoryAdapter
    artifact_sha256: Sha256 | None = None
    state: Literal["checked", "missing", "unreadable", "unsupported", "not_selected"]
    checked_levels: tuple[Level, ...] = Field(default=(), max_length=6)
    record_count: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def consistent_receipt(self) -> HistoryReceipt:
        if len(set(self.checked_levels)) != len(self.checked_levels):
            raise ValueError("invalid_metadata")
        if self.state == "checked":
            if not self.artifact_sha256 or not self.checked_levels or self.record_count is None:
                raise ValueError("invalid_metadata")
        elif self.checked_levels or self.record_count is not None:
            raise ValueError("invalid_metadata")
        return self


class PrivateHistoryCoverage(DomainModel):
    format: Literal["eval-private-history-coverage-v1"] = "eval-private-history-coverage-v1"
    plan_sha256: Sha256
    declared_artifacts: int = Field(ge=1, strict=True)
    checked_artifacts: int = Field(ge=0, strict=True)
    unresolved_artifacts: tuple[UUID, ...]
    declared_scope_status: Literal["complete", "incomplete"]
    qualification: Literal["unknown"] = "unknown"
    historical_scope_exhaustive_verified: Literal[False] = False


def history_plan_digest(plan: HistoryPlan) -> str:
    return canonical_hash(validated_copy(HistoryPlan, plan, code="invalid_metadata").model_dump(mode="json"))


def check_history_coverage(
    plan: HistoryPlan, receipts: Sequence[HistoryReceipt], *, expected_plan_sha256: str
) -> PrivateHistoryCoverage:
    """Missing receipt is a gap; wrong, extra or repeated receipt is rejected."""
    plan = validated_copy(HistoryPlan, plan, code="invalid_metadata")
    digest = history_plan_digest(plan)
    if digest != expected_plan_sha256:
        raise IsolationError("binding_mismatch")
    if len(receipts) > len(plan.requirements):
        raise IsolationError("binding_mismatch")
    records = [validated_copy(HistoryReceipt, receipt, code="invalid_metadata") for receipt in receipts]
    by_id = {receipt.artifact_id: receipt for receipt in records}
    if len(by_id) != len(records) or not set(by_id) <= {item.artifact_id for item in plan.requirements}:
        raise IsolationError("binding_mismatch")
    for record in records:
        if record.plan_sha256 != digest:
            raise IsolationError("binding_mismatch")
    unresolved = []
    for requirement in plan.requirements:
        receipt = by_id.get(requirement.artifact_id)
        if receipt is not None and receipt.adapter != requirement.adapter:
            raise IsolationError("binding_mismatch")
        if receipt is None or receipt.state != "checked":
            unresolved.append(requirement.artifact_id)
            continue
        if receipt.artifact_sha256 != requirement.artifact_sha256 or set(receipt.checked_levels) != set(
            requirement.required_levels
        ):
            raise IsolationError("binding_mismatch")
    return PrivateHistoryCoverage(
        plan_sha256=digest,
        declared_artifacts=len(plan.requirements),
        checked_artifacts=len(plan.requirements) - len(unresolved),
        unresolved_artifacts=tuple(sorted(unresolved)),
        declared_scope_status="incomplete" if unresolved else "complete",
    )
