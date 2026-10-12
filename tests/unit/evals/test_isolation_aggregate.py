import json
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from medops.evals.isolation import aggregate
from medops.evals.isolation.aggregate import (
    ArmCounts,
    ExportPolicy,
    ReleasedMetric,
    SuppressedMetric,
    batch_digest,
    project_summary,
)
from medops.evals.isolation.contracts import IsolationError, ReadGrant, validated_copy
from tests.support.eval_aggregate import material, pin
from tests.support.eval_isolation import GOLD_CANARY, QUERY_CANARY, uid


def test_whole_paired_batch_keeps_unknowns_denominator_and_unique_task_count():
    source = material()
    rows = tuple(
        row.model_copy(update={"result": "unknown"}) if row.item_id.int > 15 else row
        for row in source["batch"].observations
    )
    source["batch"] = source["batch"].model_copy(update={"observations": rows})
    result = project_summary(**pin(source))
    metric = result.metrics[0]
    assert isinstance(metric, ReleasedMetric)
    assert result.unique_tasks == 20 and result.rounds == 3
    assert metric.baseline == ArmCounts(executions=60, passed=30, failed=15, unknown=15)
    assert metric.candidate == ArmCounts(executions=60, passed=45, failed=0, unknown=15)
    assert result.qualification == "unknown" and result.independent_human_review_verified is False
    payload = result.model_dump_json()
    assert GOLD_CANARY not in payload and QUERY_CANARY not in payload
    assert set(json.loads(payload)) == {
        "format",
        "release_id",
        "batch_id",
        "collection_id",
        "manifest_sha256",
        "lock_sha256",
        "policy_sha256",
        "unique_tasks",
        "families",
        "rounds",
        "metrics",
        "qualification",
        "deployment_isolation_verified",
        "independent_human_review_verified",
    }
    assert "item_id" not in payload and "batch_sha256" not in payload


@pytest.mark.parametrize("state", ["running", "failed", "cancelled"])
def test_incomplete_batch_cannot_export_even_with_a_matching_grant(state):
    source = material()
    source["batch"] = source["batch"].model_copy(update={"state": state})
    with pytest.raises(IsolationError, match="^batch_incomplete$"):
        project_summary(**pin(source))


@pytest.mark.parametrize("role", ["developer", "generator", "runtime", "validator", "self_authorized"])
def test_holdout_export_issuance_rejects_untrusted_roles(role):
    source = material()
    source["grant"] = source["grant"].model_copy(update={"role": role})
    with pytest.raises(IsolationError, match="^release_denied$"):
        project_summary(**source)


@pytest.mark.parametrize(
    "role,split", [("custodian", "holdout"), ("validator", "validation"), ("custodian", "validation")]
)
def test_trusted_role_projection_for_matching_split(role, split):
    source = material(split=split)
    source["grant"] = source["grant"].model_copy(update={"role": role})
    assert isinstance(project_summary(**source).metrics[0], ReleasedMetric)


@pytest.mark.parametrize(
    "target,field",
    [
        ("lock", "candidate_sha256"),
        ("policy", "manifest_sha256"),
        ("policy", "lock_sha256"),
        ("batch", "manifest_sha256"),
        ("batch", "lock_sha256"),
        ("grant", "manifest_sha256"),
        ("grant", "lock_sha256"),
        ("grant", "policy_sha256"),
        ("grant", "batch_sha256"),
    ],
)
def test_binding_changes_fail_without_releasing_counts(target, field):
    source = material()
    source[target] = source[target].model_copy(update={field: "f" * 64})
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        project_summary(**source)


@pytest.mark.parametrize(
    "change",
    ["remove_failure", "remove_unknown", "duplicate", "extra_item", "extra_metric", "extra_round", "missing_arm"],
)
def test_missing_extra_or_duplicate_observations_do_not_change_denominator(change):
    source = material()
    rows = list(source["batch"].observations)
    if change == "remove_failure":
        rows.pop()
    elif change == "remove_unknown":
        rows[-1] = rows[-1].model_copy(update={"result": "unknown"})
        rows.pop()
    elif change == "duplicate":
        rows[-1] = rows[0]
    elif change == "missing_arm":
        rows = [row for row in rows if row.arm == "baseline"]
    else:
        updates = {
            "extra_item": {"item_id": uid(9999)},
            "extra_metric": {"metric_id": uid(9999)},
            "extra_round": {"round": 3},
        }
        if change == "extra_round":
            source["policy"] = source["policy"].model_copy(update={"rounds": 2})
        rows[-1] = rows[-1].model_copy(update=updates[change])
    source["batch"] = source["batch"].model_copy(update={"observations": tuple(rows)})
    with pytest.raises(IsolationError, match="^batch_incomplete$"):
        project_summary(**pin(source))


@pytest.mark.parametrize("change", ["tiny_dataset", "one_family"])
def test_task_and_family_thresholds_refuse_whole_export(change):
    source = material(count=3 if change == "tiny_dataset" else 20, shared_family=change == "one_family")
    with pytest.raises(IsolationError, match="^aggregate_too_small$"):
        project_summary(**source)


@pytest.mark.parametrize("rounds", [1, 3])
def test_rare_result_suppresses_both_arms_and_rounds_never_inflate_unique_cell(rounds):
    source = material(rounds=rounds)
    rows = tuple(
        row.model_copy(update={"result": "unknown"}) if row.arm == "candidate" and row.item_id == uid(20) else row
        for row in source["batch"].observations
    )
    source["batch"] = source["batch"].model_copy(update={"observations": rows})
    metric = project_summary(**pin(source)).metrics[0]
    assert isinstance(metric, SuppressedMetric)
    assert metric.model_dump() == {"metric_id": uid(300), "status": "suppressed"}


def test_nonzero_cell_with_many_tasks_but_one_family_is_suppressed():
    source = material()
    items = tuple(
        item.model_copy(update={"family_ids": (uid(9000),)}) if item.item_id.int > 15 else item
        for item in source["inventory"].items
    )
    # Rebuild the trusted bindings for a different synthetic inventory.
    from medops.evals.isolation.manifests import manifest_digest, public_manifest

    source["inventory"] = source["inventory"].model_copy(update={"items": items})
    source["manifest"] = public_manifest(source["inventory"])
    digest = manifest_digest(source["manifest"])
    source["lock"] = source["lock"].model_copy(update={"manifest_sha256": digest})
    lock_sha = aggregate.lock_digest(source["lock"])
    for key in ("policy", "batch", "grant"):
        source[key] = source[key].model_copy(update={"manifest_sha256": digest, "lock_sha256": lock_sha})
    assert isinstance(project_summary(**pin(source)).metrics[0], SuppressedMetric)


def test_single_metric_suppression_does_not_release_its_other_arm_or_block_other_metric():
    source = material(metrics=2)
    source["batch"] = source["batch"].model_copy(
        update={
            "observations": tuple(
                row.model_copy(update={"result": "unknown"})
                if row.metric_id == uid(300) and row.item_id == uid(1)
                else row
                for row in source["batch"].observations
            )
        }
    )
    result = project_summary(**pin(source))
    assert isinstance(result.metrics[0], SuppressedMetric) and isinstance(result.metrics[1], ReleasedMetric)


def test_changed_rows_cannot_reuse_an_issued_release_grant():
    source = material()
    source["batch"] = source["batch"].model_copy(
        update={
            "observations": tuple(
                row.model_copy(update={"result": "failed"}) if row.item_id == uid(1) else row
                for row in source["batch"].observations
            )
        }
    )
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        project_summary(**source)


def test_row_order_is_not_a_different_result():
    source = material()
    reverse = source["batch"].model_copy(update={"observations": tuple(reversed(source["batch"].observations))})
    assert batch_digest(reverse) == batch_digest(source["batch"])
    assert project_summary(**{**source, "batch": reverse}) == project_summary(**source)


@pytest.mark.parametrize(
    "field,value",
    [("min_tasks", True), ("min_cell_tasks", 1), ("min_families", 1), ("rounds", 4), ("metric_ids", (uid(1), uid(1)))],
)
def test_export_policy_has_no_implicit_or_unsafe_thresholds(field, value):
    value = {**material()["policy"].model_dump(), field: value}
    with pytest.raises(ValidationError):
        ExportPolicy(**value)
    with pytest.raises(ValidationError):
        ExportPolicy(policy_id=uid(1))


def test_size_limit_is_checked_before_allocating_expected_grid(monkeypatch):
    source = material()
    monkeypatch.setattr(aggregate, "MAX_OBSERVATIONS", 10)
    with pytest.raises(IsolationError, match="^release_limit$"):
        project_summary(**source)


def test_copy_revalidation_never_emits_private_serializer_warning(recwarn, capsys):
    value = ReadGrant(actor_id=uid(1), role="runtime", collection_id=uid(2), manifest_sha256="a" * 64, item_id=uid(3))
    with pytest.raises(IsolationError, match="^access_denied$") as error:
        validated_copy(ReadGrant, value.model_copy(update={"item_id": GOLD_CANARY}), code="access_denied")
    assert not recwarn and GOLD_CANARY not in str(error.value) and GOLD_CANARY not in capsys.readouterr().err


def test_nonserializable_copy_also_has_fixed_error():
    @dataclass
    class NotSerializable:
        value: object

    source = material()
    with pytest.raises(IsolationError, match="^release_denied$") as error:
        project_summary(
            **{**source, "grant": source["grant"].model_copy(update={"actor_id": NotSerializable(object())})}
        )
    assert str(error.value) == "release_denied"
