"""Exposed synthetic transport examples, never Agent rubric or holdout gold."""

from medops.evals.isolation.aggregate import (
    ExportPolicy,
    PrivateBatch,
    PrivateObservation,
    ReleaseGrant,
    batch_digest,
    lock_digest,
    policy_digest,
)
from medops.evals.isolation.contracts import EvaluationLock, PrivateInventory
from medops.evals.isolation.manifests import inventory_item, manifest_digest, public_manifest
from tests.support.eval_isolation import case, uid


def material(*, count=20, rounds=3, metrics=1, split="holdout", shared_family=False):
    inventory = PrivateInventory(
        collection_id=uid(100),
        split=split,
        items=tuple(
            inventory_item(
                case(i, query=f"SYNTHETIC QUERY {i}"), family_ids=(uid(1000 if shared_family else 1000 + i),)
            )
            for i in range(1, count + 1)
        ),
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
        policy_id=uid(200),
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        metric_ids=tuple(uid(300 + i) for i in range(metrics)),
        rounds=rounds,
        min_tasks=20,
        min_families=2,
        min_cell_tasks=5,
    )
    batch = PrivateBatch(
        batch_id=uid(400),
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        state="complete",
        observations=tuple(
            PrivateObservation(
                item_id=item.item_id,
                metric_id=metric,
                arm=arm,
                round=round_,
                result="passed" if i < (10 if arm == "baseline" else 15) else "failed",
            )
            for metric in policy.metric_ids
            for arm in ("baseline", "candidate")
            for round_ in range(1, rounds + 1)
            for i, item in enumerate(inventory.items)
        ),
    )
    grant = ReleaseGrant(
        release_id=uid(500),
        actor_id=uid(600),
        role="holdout_evaluator" if split == "holdout" else "validator",
        manifest_sha256=digest,
        lock_sha256=lock_digest(lock),
        policy_sha256=policy_digest(policy),
        batch_sha256=batch_digest(batch),
    )
    return dict(manifest=manifest, inventory=inventory, lock=lock, policy=policy, batch=batch, grant=grant)


def pin(value):
    """Simulate trusted issuer freezing synthetic artifacts, never authenticate a caller."""
    return {
        **value,
        "grant": value["grant"].model_copy(
            update={"batch_sha256": batch_digest(value["batch"]), "policy_sha256": policy_digest(value["policy"])}
        ),
    }
