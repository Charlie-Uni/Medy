import json

import pytest
from pydantic import ValidationError

from medops.evals.isolation.contracts import IsolationError, PrivateInventory, parse_public_manifest
from medops.evals.isolation.manifests import check_disjoint, inventory_item, public_manifest
from tests.support.eval_isolation import GOLD_CANARY, QUERY_CANARY, case, inventory, uid


def test_public_manifest_has_no_payload_or_per_item_identity():
    result = public_manifest(inventory()).model_dump_json()
    assert QUERY_CANARY not in result and GOLD_CANARY not in result
    assert set(json.loads(result)) == {
        "format",
        "collection_id",
        "split",
        "item_count",
        "family_count",
        "inventory_sha256",
        "qualification",
        "deployment_isolation_verified",
        "independent_human_review_verified",
    }
    assert json.loads(result)["qualification"] == "unknown"
    assert parse_public_manifest(result) == public_manifest(inventory())


@pytest.mark.parametrize("field", ["query", "gold", "trace", "free_text_label", "item_ids"])
def test_public_extra_fields_rejected_without_echoing_private_content(field):
    value = public_manifest(inventory()).model_dump(mode="json")
    value[field] = GOLD_CANARY
    with pytest.raises(IsolationError, match="^invalid_metadata$") as error:
        parse_public_manifest(json.dumps(value))
    assert GOLD_CANARY not in str(error.value)


@pytest.mark.parametrize(
    "field,value", [("item_count", True), ("qualification", "unseen"), ("deployment_isolation_verified", True)]
)
def test_public_manifest_cannot_assert_unsupported_evidence(field, value):
    data = public_manifest(inventory()).model_dump(mode="json")
    data[field] = value
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        parse_public_manifest(json.dumps(data))


def test_manifest_order_independent_content_bound_and_counts_computed():
    first = inventory_item(case(), family_ids=(uid(10), uid(11)))
    second = inventory_item(case(2, query="OTHER SYNTHETIC QUERY"), family_ids=(uid(11),))
    source = PrivateInventory(collection_id=uid(50), split="development", items=(first, second))
    reverse = source.model_copy(update={"items": (second, first)})
    assert public_manifest(source) == public_manifest(reverse)
    assert public_manifest(source).item_count == 2 and public_manifest(source).family_count == 2
    changed = source.model_copy(update={"items": (first, second.model_copy(update={"payload_sha256": "f" * 64}))})
    assert public_manifest(changed).inventory_sha256 != public_manifest(source).inventory_sha256


def test_duplicate_task_ids_and_family_metadata_rejected():
    source = inventory()
    with pytest.raises(ValidationError):
        PrivateInventory(collection_id=source.collection_id, split="development", items=source.items * 2)
    with pytest.raises(ValidationError):
        inventory_item(case(), family_ids=(uid(1), uid(1)))


@pytest.mark.parametrize("collision", ["item", "family", "related", "query", "normalized_query"])
def test_cross_collection_collisions_fail_without_private_diagnostics(collision):
    left = inventory()
    right = inventory("holdout", 2, query="OTHER SYNTHETIC QUERY")
    item = right.items[0]
    if collision == "item":
        item = item.model_copy(update={"item_id": left.items[0].item_id})
    elif collision == "family":
        item = item.model_copy(update={"family_ids": left.items[0].family_ids})
    elif collision == "related":
        group = uid(500)
        left = left.model_copy(update={"items": (left.items[0].model_copy(update={"related_group_ids": (group,)}),)})
        item = item.model_copy(update={"related_group_ids": (group,)})
    else:
        key = collision + "_sha256"
        item = item.model_copy(update={key: getattr(left.items[0], key)})
    right = right.model_copy(update={"items": (item,)})
    with pytest.raises(IsolationError, match="^split_overlap$") as error:
        check_disjoint((left, right))
    assert QUERY_CANARY not in str(error.value)


def test_distinct_inputs_pass_and_shared_collection_id_does_not():
    left = inventory()
    right = inventory("validation", 2, query="OTHER SYNTHETIC QUERY")
    check_disjoint((left, right))
    with pytest.raises(IsolationError, match="^split_overlap$"):
        check_disjoint((left, right.model_copy(update={"collection_id": left.collection_id})))


def test_normalized_query_equivalence_is_detected_from_actual_strings():
    left = inventory(query="synthetic 5㎎")
    right = inventory("holdout", 2, query="synthetic 5mg")
    assert left.items[0].query_sha256 != right.items[0].query_sha256
    with pytest.raises(IsolationError, match="^split_overlap$"):
        check_disjoint((left, right))


@pytest.mark.parametrize("data", [b"\xff", '{"item_count":1,"item_count":2}', "[", "null"])
def test_public_parser_rejects_invalid_encoding_shape_and_duplicate_keys(data):
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        parse_public_manifest(data)


def test_unvalidated_nested_metadata_and_private_copy_cannot_enter_manifest():
    source = inventory()
    changed = source.model_copy(update={"items": (source.items[0].model_copy(update={"query_sha256": "INVALID"}),)})
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        public_manifest(changed)
    with pytest.raises(IsolationError, match="^invalid_payload$") as error:
        inventory_item(case().model_copy(update={"query": GOLD_CANARY * 4000}), family_ids=(uid(1),))
    assert GOLD_CANARY not in str(error.value)
