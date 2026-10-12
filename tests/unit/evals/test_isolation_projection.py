import pytest

from medops.evals.isolation.contracts import IsolationError, RuntimeInput
from medops.evals.isolation.manifests import public_manifest
from medops.evals.isolation.projection import project_input
from tests.support.eval_isolation import GOLD_CANARY, MemoryStore, case, grant, inventory, lock, uid


@pytest.mark.parametrize(
    "role,split",
    [
        ("generator", "validation"),
        ("generator", "holdout"),
        ("developer", "validation"),
        ("developer", "holdout"),
        ("validator", "holdout"),
        ("holdout_evaluator", "development"),
        ("holdout_evaluator", "validation"),
    ],
)
def test_forbidden_roles_stop_before_any_loader(role, split):
    items = inventory(split)
    store = MemoryStore(case())
    with pytest.raises(IsolationError, match="^access_denied$"):
        project_input(
            store, manifest=public_manifest(items), inventory=items, grant=grant(items, role), lock=lock(items)
        )
    assert store.input_reads == 0 and store.review_reads == 0


def test_generator_development_input_excludes_gold_and_review_metadata():
    items = inventory()
    store = MemoryStore(case())
    result = project_input(store, manifest=public_manifest(items), inventory=items, grant=grant(items, "generator"))
    assert set(result.model_dump()) == {"item_id", "query", "observed_output"}
    assert GOLD_CANARY not in result.model_dump_json()
    assert store.review_reads == 1


@pytest.mark.parametrize("split", ["development", "validation", "holdout"])
def test_runtime_only_reads_assigned_input_and_never_gold(split):
    items = inventory(split)
    store = MemoryStore(case())
    result = project_input(
        store, manifest=public_manifest(items), inventory=items, grant=grant(items), lock=lock(items)
    )
    assert type(result) is RuntimeInput
    assert set(result.model_dump()) == {"item_id", "query"}
    assert store.input_reads == 1 and store.review_reads == 0


def test_runtime_projection_does_not_serialize_leaky_store_subclass():
    class LeakyInput(RuntimeInput):
        gold: str

    class LeakyStore(MemoryStore):
        def load_input(self, item_id):
            return LeakyInput(item_id=self.material.item_id, query=self.material.query, gold=GOLD_CANARY)

    items = inventory()
    result = project_input(LeakyStore(case()), manifest=public_manifest(items), inventory=items, grant=grant(items))
    assert type(result) is RuntimeInput and GOLD_CANARY not in result.model_dump_json()


@pytest.mark.parametrize(
    "role,split", [("validator", "validation"), ("holdout_evaluator", "holdout"), ("custodian", "holdout")]
)
def test_allowed_reviewer_has_content_under_matching_binding(role, split):
    items = inventory(split)
    result = project_input(
        MemoryStore(case()),
        manifest=public_manifest(items),
        inventory=items,
        grant=grant(items, role),
        lock=lock(items),
    )
    assert result == case()


@pytest.mark.parametrize(
    "changed",
    ["no_lock", "wrong_lock", "incomplete_lock", "wrong_collection", "wrong_manifest", "unknown_item", "unknown_role"],
)
def test_bad_grant_or_lock_refuses_before_loading(changed):
    items = inventory("holdout")
    request = grant(items)
    frozen = lock(items)
    if changed == "no_lock":
        frozen = None
    elif changed == "wrong_lock":
        frozen = frozen.model_copy(update={"manifest_sha256": "f" * 64})
    elif changed == "incomplete_lock":
        frozen = frozen.model_copy(update={"candidate_sha256": ""})
    else:
        updates = {
            "wrong_collection": {"collection_id": uid(900)},
            "wrong_manifest": {"manifest_sha256": "f" * 64},
            "unknown_item": {"item_id": uid(900)},
            "unknown_role": {"role": "self_authorized"},
        }
        request = request.model_copy(update=updates[changed])
    store = MemoryStore(case())
    with pytest.raises(IsolationError):
        project_input(store, manifest=public_manifest(items), inventory=items, grant=request, lock=frozen)
    assert store.input_reads == 0 and store.review_reads == 0


@pytest.mark.parametrize("changed", ["query", "gold", "item", "inventory"])
def test_changed_content_or_inventory_does_not_reach_consumer(changed):
    items = inventory()
    manifest = public_manifest(items)
    request = grant(items, "generator")
    material = case()
    if changed == "inventory":
        items = items.model_copy(update={"items": (items.items[0].model_copy(update={"payload_sha256": "f" * 64}),)})
    else:
        material = material.model_copy(
            update={"query": "TAMPERED", "gold": "TAMPERED", "item_id": uid(999)}
            if changed == "item"
            else {changed: "TAMPERED"}
        )
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        project_input(MemoryStore(material), manifest=manifest, inventory=items, grant=request)
