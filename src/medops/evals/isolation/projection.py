"""Reject unauthorized reads before loading; explicitly project runtime inputs.

Grants/locks must come from a trusted runner. The module does not authenticate
callers or prevent a filesystem administrator from reading the backing store.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from medops.core.canonical import canonical_hash, sha256_hex
from medops.evals.isolation.contracts import (
    DevelopmentInput,
    EvaluationLock,
    IsolationError,
    PrivateCase,
    PrivateInventory,
    PublicManifest,
    ReadGrant,
    RuntimeInput,
    validated_copy,
)
from medops.evals.isolation.manifests import bind_inventory, manifest_digest


class CaseStore(Protocol):
    """Separate input and review methods allow separate storage credentials later."""

    def load_input(self, item_id: UUID) -> RuntimeInput: ...

    def load_review(self, item_id: UUID) -> PrivateCase: ...


def project_input(
    store: CaseStore,
    *,
    manifest: PublicManifest,
    inventory: PrivateInventory,
    grant: ReadGrant,
    lock: EvaluationLock | None = None,
) -> RuntimeInput | DevelopmentInput | PrivateCase:
    grant = validated_copy(ReadGrant, grant, code="access_denied")
    bind_inventory(manifest, inventory)
    digest = manifest_digest(manifest)
    if grant.collection_id != manifest.collection_id or grant.manifest_sha256 != digest:
        raise IsolationError("binding_mismatch")
    item = next((item for item in inventory.items if item.item_id == grant.item_id), None)
    if item is None:
        raise IsolationError("access_denied")
    if grant.role in {"developer", "generator"} and manifest.split != "development":
        raise IsolationError("access_denied")
    if grant.role == "validator" and manifest.split == "holdout":
        raise IsolationError("access_denied")
    if grant.role == "holdout_evaluator" and manifest.split != "holdout":
        raise IsolationError("access_denied")
    if manifest.split == "holdout" and grant.role != "custodian":
        if lock is None:
            raise IsolationError("lock_required")
        lock = validated_copy(EvaluationLock, lock, code="binding_mismatch")
        if lock.manifest_sha256 != digest:
            raise IsolationError("binding_mismatch")
    if grant.role == "runtime":
        value = store.load_input(grant.item_id)
        if value.item_id != item.item_id or sha256_hex(value.query) != item.query_sha256:
            raise IsolationError("binding_mismatch")
        # Never serialize the store's object wholesale: a subclass can contain gold.
        try:
            return RuntimeInput(item_id=value.item_id, query=value.query)
        except ValidationError:
            raise IsolationError("invalid_payload") from None
    case = validated_copy(PrivateCase, store.load_review(grant.item_id), code="invalid_payload")
    if case.item_id != item.item_id or canonical_hash(case.model_dump(mode="json")) != item.payload_sha256:
        raise IsolationError("binding_mismatch")
    if grant.role in {"developer", "generator"}:
        return DevelopmentInput(item_id=case.item_id, query=case.query, observed_output=case.observed_output)
    return case
