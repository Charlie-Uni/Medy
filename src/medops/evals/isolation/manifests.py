"""Bind private content without publishing it; check supplied separation metadata.

Exact/normalized query collisions and reviewed relationship groups are checked.
No fuzzy threshold, unseen certification or medical gold decision is inferred.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from medops.core.canonical import canonical_hash, sha256_hex
from medops.evals.isolation.contracts import (
    InventoryItem,
    IsolationError,
    PrivateCase,
    PrivateInventory,
    PublicManifest,
    validated_copy,
)
from medops.knowledge.normalization import normalize_text


def inventory_item(
    case: PrivateCase, *, family_ids: tuple[UUID, ...], related_group_ids: tuple[UUID, ...] = ()
) -> InventoryItem:
    case = validated_copy(PrivateCase, case, code="invalid_payload")
    return InventoryItem(
        item_id=case.item_id,
        family_ids=tuple(sorted(family_ids)),
        related_group_ids=tuple(sorted(related_group_ids)),
        query_sha256=sha256_hex(case.query),
        normalized_query_sha256=sha256_hex(normalize_text(case.query)),
        payload_sha256=canonical_hash(case.model_dump(mode="json")),
    )


def public_manifest(inventory: PrivateInventory) -> PublicManifest:
    inventory = validated_copy(PrivateInventory, inventory, code="invalid_metadata")
    payload = inventory.model_dump(mode="json")
    payload["items"] = sorted(payload["items"], key=lambda item: item["item_id"])
    return PublicManifest(
        collection_id=inventory.collection_id,
        split=inventory.split,
        item_count=len(inventory.items),
        family_count=len({family for item in inventory.items for family in item.family_ids}),
        inventory_sha256=canonical_hash(payload),
    )


def manifest_digest(manifest: PublicManifest) -> str:
    manifest = validated_copy(PublicManifest, manifest, code="invalid_metadata")
    return canonical_hash(manifest.model_dump(mode="json"))


def check_disjoint(inventories: Sequence[PrivateInventory]) -> None:
    """Fail on overlap across collections/splits; do not disclose which private item."""
    collections: set[UUID] = set()
    seen: dict[tuple[str, UUID | str], UUID] = {}
    for inventory in inventories:
        inventory = validated_copy(PrivateInventory, inventory, code="invalid_metadata")
        if inventory.collection_id in collections:
            raise IsolationError("split_overlap")
        collections.add(inventory.collection_id)
        for item in inventory.items:
            identities: list[tuple[str, UUID | str]] = [
                ("item", item.item_id),
                ("query", item.query_sha256),
                ("normalized_query", item.normalized_query_sha256),
                *(("family", group) for group in item.family_ids),
                *(("related", group) for group in item.related_group_ids),
            ]
            for identity in identities:
                owner = seen.setdefault(identity, inventory.collection_id)
                if owner != inventory.collection_id:
                    raise IsolationError("split_overlap")


def bind_inventory(manifest: PublicManifest, inventory: PrivateInventory) -> None:
    if public_manifest(inventory) != manifest:
        raise IsolationError("binding_mismatch")
