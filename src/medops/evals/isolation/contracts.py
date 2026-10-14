"""Content-free manifests, private inventory and safe isolation error vocabulary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal, TypeVar
from uuid import UUID

from pydantic import Field, ValidationError, field_validator, model_validator

from medops.domain.common import DomainModel, Sha256

Split = Literal["development", "validation", "holdout"]
Role = Literal["developer", "generator", "validator", "holdout_evaluator", "runtime", "custodian"]
Level = Literal["source", "query", "gold", "output", "verdict", "aggregate"]
Purpose = Literal["development", "candidate_generation", "validation", "holdout", "runtime_execution", "review"]
Failure = Literal[
    "invalid_metadata",
    "invalid_payload",
    "access_denied",
    "lock_required",
    "binding_mismatch",
    "split_overlap",
    "ledger_corrupt",
    "ledger_head_changed",
    "duplicate_event",
    "ledger_limit",
    "ledger_io",
    "aggregate_too_small",
    "batch_incomplete",
    "release_denied",
    "release_limit",
    "screening_limit",
]


class IsolationError(ValueError):
    """Fixed messages: neither validation input nor protected payload is printed."""

    def __init__(self, code: Failure):
        self.code = code
        super().__init__(code)


class PrivateCase(DomainModel):
    """Preparatory transport, not Agent runtime DTOs or medical annotations."""

    item_id: UUID
    query: str = Field(min_length=1, max_length=4000)
    gold: str = Field(min_length=1, max_length=16000)
    observed_output: str | None = Field(default=None, max_length=16000)


class InventoryItem(DomainModel):
    item_id: UUID
    family_ids: tuple[UUID, ...] = Field(min_length=1, max_length=32)
    related_group_ids: tuple[UUID, ...] = Field(default=(), max_length=32)
    query_sha256: Sha256
    normalized_query_sha256: Sha256
    payload_sha256: Sha256

    @model_validator(mode="after")
    def unique_groups(self) -> InventoryItem:
        if len(set(self.family_ids)) != len(self.family_ids) or len(set(self.related_group_ids)) != len(
            self.related_group_ids
        ):
            raise ValueError("invalid_metadata")
        return self


class PrivateInventory(DomainModel):
    format: Literal["eval-private-inventory-v1"] = "eval-private-inventory-v1"
    collection_id: UUID
    split: Split
    items: tuple[InventoryItem, ...] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_items(self) -> PrivateInventory:
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("invalid_metadata")
        return self


class PublicManifest(DomainModel):
    """Only opaque IDs, counts and digests; no free-text labels or per-item data."""

    format: Literal["eval-public-manifest-v1"] = "eval-public-manifest-v1"
    collection_id: UUID
    split: Split
    item_count: int = Field(gt=0, strict=True)
    family_count: int = Field(gt=0, strict=True)
    inventory_sha256: Sha256
    qualification: Literal["unknown"] = "unknown"
    deployment_isolation_verified: Literal[False] = False
    independent_human_review_verified: Literal[False] = False


class EvaluationLock(DomainModel):
    """A trusted runner's binding; authenticating its issuer is a deployment gate."""

    manifest_sha256: Sha256
    baseline_sha256: Sha256
    candidate_sha256: Sha256
    rubric_sha256: Sha256
    protocol_sha256: Sha256


class ReadGrant(DomainModel):
    """Supplied by the trusted runner, never accepted from model action parameters."""

    actor_id: UUID
    role: Role
    collection_id: UUID
    manifest_sha256: Sha256
    item_id: UUID


class RuntimeInput(DomainModel):
    item_id: UUID
    query: str = Field(min_length=1, max_length=4000)


class DevelopmentInput(RuntimeInput):
    observed_output: str | None = None


class ExposureEvent(DomainModel):
    event_id: UUID
    occurred_at: datetime
    actor_id: UUID
    role: Role
    collection_id: UUID
    item_id: UUID | None = None
    family_ids: tuple[UUID, ...] = Field(default=(), max_length=32)
    levels: tuple[Level, ...] = Field(min_length=1, max_length=6)
    purpose: Purpose
    candidate_sha256: Sha256 | None = None
    receipt_sha256: Sha256

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("invalid_metadata")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def unique_values(self) -> ExposureEvent:
        if len(set(self.levels)) != len(self.levels) or len(set(self.family_ids)) != len(self.family_ids):
            raise ValueError("invalid_metadata")
        return self


class LedgerHead(DomainModel):
    sequence: int = Field(ge=0, strict=True)
    sha256: Sha256 | None = None

    @model_validator(mode="after")
    def consistent_head(self) -> LedgerHead:
        if (self.sequence == 0) != (self.sha256 is None):
            raise ValueError("invalid_metadata")
        return self


class LedgerEntry(DomainModel):
    sequence: int = Field(gt=0, strict=True)
    previous_sha256: Sha256 | None
    event: ExposureEvent
    sha256: Sha256


ModelT = TypeVar("ModelT", bound=DomainModel)


def validated_copy(model: type[ModelT], value: DomainModel, *, code: Failure) -> ModelT:
    """Revalidate copies/subclasses; report only fixed failure codes."""
    try:
        # Python mode preserves native bool/int distinctions before validation;
        # JSON serialization can coerce a copied bool in an integer field to 1.
        return model.model_validate(value.model_dump(mode="python", warnings=False))
    except ValueError:
        raise IsolationError(code) from None


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate_json_key")
    return value


def strict_json(data: str | bytes) -> object:
    """Reject duplicate keys at every depth, before schema validation."""
    return json.loads(data, object_pairs_hook=_unique_pairs)


def parse_public_manifest(data: str | bytes) -> PublicManifest:
    try:
        return PublicManifest.model_validate(strict_json(data))
    except (ValidationError, ValueError, UnicodeError, RecursionError):
        raise IsolationError("invalid_metadata") from None
