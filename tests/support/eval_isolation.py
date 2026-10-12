"""Public synthetic canaries for evaluation separation tests; not unseen tasks."""

from datetime import UTC, datetime
from uuid import UUID

from medops.evals.isolation.contracts import (
    EvaluationLock,
    ExposureEvent,
    PrivateCase,
    PrivateInventory,
    ReadGrant,
    Role,
    RuntimeInput,
    Split,
)
from medops.evals.isolation.manifests import inventory_item, manifest_digest, public_manifest

QUERY_CANARY = "SYNTHETIC-QUERY-CANARY"
GOLD_CANARY = "PRIVATE-GOLD-CANARY"
OUTPUT_CANARY = "SYNTHETIC-OUTPUT-CANARY"
DIGEST = "a" * 64


def uid(value: int) -> UUID:
    return UUID(int=value)


def case(value: int = 1, *, query: str = QUERY_CANARY) -> PrivateCase:
    return PrivateCase(item_id=uid(value), query=query, gold=GOLD_CANARY, observed_output=OUTPUT_CANARY)


def inventory(split: Split = "development", value: int = 1, *, query: str = QUERY_CANARY) -> PrivateInventory:
    return PrivateInventory(
        collection_id=uid(100 + value),
        split=split,
        items=(inventory_item(case(value, query=query), family_ids=(uid(1000 + value),)),),
    )


def grant(items: PrivateInventory, role: Role = "runtime") -> ReadGrant:
    return ReadGrant(
        actor_id=uid(99),
        role=role,
        collection_id=items.collection_id,
        manifest_sha256=manifest_digest(public_manifest(items)),
        item_id=items.items[0].item_id,
    )


def lock(items: PrivateInventory) -> EvaluationLock:
    return EvaluationLock(
        manifest_sha256=manifest_digest(public_manifest(items)),
        baseline_sha256="b" * 64,
        candidate_sha256="c" * 64,
        rubric_sha256="d" * 64,
        protocol_sha256="e" * 64,
    )


class MemoryStore:
    def __init__(self, material: PrivateCase):
        self.material = material
        self.input_reads = 0
        self.review_reads = 0

    def load_input(self, item_id: UUID) -> RuntimeInput:
        self.input_reads += 1
        return RuntimeInput(item_id=self.material.item_id, query=self.material.query)

    def load_review(self, item_id: UUID) -> PrivateCase:
        self.review_reads += 1
        return self.material


def event(value: int = 1, *, role: Role = "generator") -> ExposureEvent:
    return ExposureEvent(
        event_id=uid(value),
        occurred_at=datetime(2026, 10, 12, tzinfo=UTC),
        actor_id=uid(99),
        role=role,
        collection_id=uid(101),
        family_ids=(uid(1001),),
        levels=("query",),
        purpose="runtime_execution" if role == "runtime" else "candidate_generation",
        candidate_sha256=DIGEST,
        receipt_sha256=DIGEST,
    )
