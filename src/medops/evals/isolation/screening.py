"""Deterministic private query triage, never unseen certification or semantic grouping.

Trusted callers supply already authorized query projections and pinned inventories.
No file discovery, gold access, embedding/model calls or public pair export occurs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from medops.core.canonical import canonical_hash, sha256_hex
from medops.domain.common import DomainModel, Sha256
from medops.evals.isolation.contracts import IsolationError, PrivateInventory, RuntimeInput, validated_copy
from medops.evals.isolation.manifests import manifest_digest, public_manifest
from medops.knowledge.normalization import normalize_text


class ScreeningPolicy(DomainModel):
    format: Literal["eval-query-screening-policy-v1"] = "eval-query-screening-policy-v1"
    method_id: UUID
    algorithm: Literal["character-set-jaccard-v1"] = "character-set-jaccard-v1"
    normalization: Literal["norm-v1"] = "norm-v1"
    width: int = Field(ge=2, le=5, strict=True)
    min_normalized_chars: int = Field(ge=2, le=4000, strict=True)
    threshold_numerator: int = Field(ge=1, le=1000, strict=True)
    threshold_denominator: int = Field(ge=1, le=1000, strict=True)
    max_items_per_collection: int = Field(ge=1, le=10000, strict=True)
    max_comparisons: int = Field(ge=1, le=1000000, strict=True)
    max_total_query_chars: int = Field(ge=1, le=4000000, strict=True)

    @model_validator(mode="after")
    def consistent_limits(self) -> ScreeningPolicy:
        if self.threshold_numerator > self.threshold_denominator or self.min_normalized_chars < self.width:
            raise ValueError("invalid_metadata")
        return self


class PrivateQueryMatch(DomainModel):
    left_item_id: UUID
    right_item_id: UUID
    reason: Literal["query_exact", "query_normalized", "query_near"]
    numerator: int = Field(ge=1, strict=True)
    denominator: int = Field(ge=1, strict=True)
    disposition: Literal["review_required"] = "review_required"


class PrivateScreeningReport(DomainModel):
    format: Literal["eval-private-query-screening-v1"] = "eval-private-query-screening-v1"
    method_sha256: Sha256
    left_manifest_sha256: Sha256
    right_manifest_sha256: Sha256
    compared_pairs: int = Field(ge=1, strict=True)
    matches: tuple[PrivateQueryMatch, ...]
    qualification: Literal["unknown"] = "unknown"
    deployment_isolation_verified: Literal[False] = False
    independent_human_review_verified: Literal[False] = False


def screening_digest(policy: ScreeningPolicy) -> str:
    return canonical_hash(validated_copy(ScreeningPolicy, policy, code="invalid_metadata").model_dump(mode="json"))


def _bound_queries(inventory: PrivateInventory, values: Sequence[RuntimeInput]) -> dict[UUID, str]:
    by_id = {item.item_id: item.query for item in values}
    if len(by_id) != len(values) or set(by_id) != {item.item_id for item in inventory.items}:
        raise IsolationError("binding_mismatch")
    normalized = {}
    for item in inventory.items:
        raw = by_id[item.item_id]
        text = normalize_text(raw)
        if not text:
            raise IsolationError("invalid_payload")
        if sha256_hex(raw) != item.query_sha256 or sha256_hex(text) != item.normalized_query_sha256:
            raise IsolationError("binding_mismatch")
        normalized[item.item_id] = text
    return normalized


def screen_queries(
    *,
    left: PrivateInventory,
    left_inputs: Sequence[RuntimeInput],
    right: PrivateInventory,
    right_inputs: Sequence[RuntimeInput],
    policy: ScreeningPolicy,
    expected_method_sha256: str,
) -> PrivateScreeningReport:
    """Return private review pairs; run existing check_disjoint separately.

    All declared cross pairs are examined or the operation fails. Short unequal
    queries are not fuzzy scored; they remain unknown rather than being cleared.
    """
    policy = validated_copy(ScreeningPolicy, policy, code="invalid_metadata")
    if screening_digest(policy) != expected_method_sha256:
        raise IsolationError("binding_mismatch")
    if (
        len(left_inputs) > policy.max_items_per_collection
        or len(right_inputs) > policy.max_items_per_collection
        or len(left_inputs) * len(right_inputs) > policy.max_comparisons
    ):
        raise IsolationError("screening_limit")
    left = validated_copy(PrivateInventory, left, code="invalid_metadata")
    right = validated_copy(PrivateInventory, right, code="invalid_metadata")
    if left.collection_id == right.collection_id:
        raise IsolationError("invalid_metadata")
    if len(left.items) != len(left_inputs) or len(right.items) != len(right_inputs):
        raise IsolationError("binding_mismatch")
    left_values = tuple(validated_copy(RuntimeInput, item, code="invalid_payload") for item in left_inputs)
    right_values = tuple(validated_copy(RuntimeInput, item, code="invalid_payload") for item in right_inputs)
    if sum(len(item.query) for item in (*left_values, *right_values)) > policy.max_total_query_chars:
        raise IsolationError("screening_limit")
    lhs, rhs = _bound_queries(left, left_values), _bound_queries(right, right_values)

    def grams(text: str) -> frozenset[str]:
        if len(text) < policy.min_normalized_chars:
            return frozenset()
        return frozenset(text[index : index + policy.width] for index in range(len(text) - policy.width + 1))

    left_grams = {item: grams(text) for item, text in lhs.items()}
    right_grams = {item: grams(text) for item, text in rhs.items()}
    left_hashes = {item.item_id: item.query_sha256 for item in left.items}
    right_hashes = {item.item_id: item.query_sha256 for item in right.items}
    matches: list[PrivateQueryMatch] = []
    for a in sorted(lhs):
        for b in sorted(rhs):
            reason: Literal["query_exact", "query_normalized", "query_near"]
            if left_hashes[a] == right_hashes[b]:
                reason, numerator, denominator = "query_exact", 1, 1
            elif lhs[a] == rhs[b]:
                reason, numerator, denominator = "query_normalized", 1, 1
            elif left_grams[a] and right_grams[b]:
                numerator = len(left_grams[a] & right_grams[b])
                denominator = len(left_grams[a] | right_grams[b])
                if numerator * policy.threshold_denominator < denominator * policy.threshold_numerator:
                    continue
                reason = "query_near"
            else:
                continue
            matches.append(
                PrivateQueryMatch(
                    left_item_id=a, right_item_id=b, reason=reason, numerator=numerator, denominator=denominator
                )
            )
    return PrivateScreeningReport(
        method_sha256=expected_method_sha256,
        left_manifest_sha256=manifest_digest(public_manifest(left)),
        right_manifest_sha256=manifest_digest(public_manifest(right)),
        compared_pairs=len(lhs) * len(rhs),
        matches=tuple(matches),
    )
