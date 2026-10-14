import pytest
from pydantic import ValidationError

from medops.evals.isolation.contracts import IsolationError
from medops.evals.isolation.history import HistoryPlan, HistoryReceipt, check_history_coverage, history_plan_digest
from tests.support.eval_isolation import GOLD_CANARY, uid
from tests.support.eval_screening import history


def test_complete_declared_scope_is_not_exhaustive_history_or_unseen_qualification():
    plan, receipts, digest = history()
    result = check_history_coverage(plan, receipts, expected_plan_sha256=digest)
    assert result.declared_scope_status == "complete" and result.checked_artifacts == result.declared_artifacts == 2
    assert result.unresolved_artifacts == () and result.qualification == "unknown"
    assert result.historical_scope_exhaustive_verified is False


@pytest.mark.parametrize("state", ["missing", "unreadable", "unsupported", "not_selected", "omitted"])
def test_gaps_are_preserved_instead_of_claiming_no_exposure(state):
    plan, receipts, digest = history()
    values = (
        receipts[:1]
        if state == "omitted"
        else (receipts[0], receipts[1].model_copy(update={"state": state, "checked_levels": (), "record_count": None}))
    )
    result = check_history_coverage(plan, values, expected_plan_sha256=digest)
    assert result.declared_scope_status == "incomplete" and result.checked_artifacts == 1
    assert result.unresolved_artifacts == (uid(2),) and result.qualification == "unknown"


def test_no_receipts_or_a_checked_empty_artifact_does_not_prove_unseen():
    plan, receipts, digest = history()
    missing = check_history_coverage(plan, (), expected_plan_sha256=digest)
    assert missing.checked_artifacts == 0 and len(missing.unresolved_artifacts) == 2
    empty = check_history_coverage(
        plan, tuple(r.model_copy(update={"record_count": 0}) for r in receipts), expected_plan_sha256=digest
    )
    assert empty.declared_scope_status == "complete" and empty.qualification == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "extra",
        "artifact",
        "plan",
        "adapter",
        "missing_level",
        "extra_level",
        "expected_plan",
        "changed_scope",
    ],
)
def test_receipt_must_match_original_artifact_adapter_levels_and_scope(change):
    plan, receipts, digest = history()
    values = list(receipts)
    if change == "duplicate":
        values[1] = values[0]
    elif change == "extra":
        values[1] = values[1].model_copy(update={"artifact_id": uid(99)})
    elif change == "expected_plan":
        digest = "f" * 64
    elif change == "changed_scope":
        plan = plan.model_copy(update={"scope_id": uid(99)})
    else:
        updates = {
            "artifact": {"artifact_sha256": "f" * 64},
            "plan": {"plan_sha256": "f" * 64},
            "adapter": {"adapter": "dataset-fields-v1"},
            "missing_level": {"checked_levels": ("query",)},
            "extra_level": {"checked_levels": ("query", "source", "gold")},
        }
        values[1] = values[1].model_copy(update=updates[change])
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        check_history_coverage(plan, values, expected_plan_sha256=digest)


@pytest.mark.parametrize(
    "changes",
    [
        {"record_count": None},
        {"record_count": True},
        {"artifact_sha256": None},
        {"checked_levels": ()},
        {"checked_levels": ("query", "query")},
        {"state": "missing"},
    ],
)
def test_copied_inconsistent_receipt_is_revalidated_without_private_error(changes):
    plan, receipts, digest = history()
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        check_history_coverage(plan, (receipts[0].model_copy(update=changes),), expected_plan_sha256=digest)


def test_copied_unknown_metadata_has_fixed_error_and_no_echo():
    plan, receipts, digest = history()
    with pytest.raises(IsolationError, match="^invalid_metadata$") as error:
        check_history_coverage(
            plan, (receipts[0].model_copy(update={"adapter": GOLD_CANARY}),), expected_plan_sha256=digest
        )
    assert GOLD_CANARY not in str(error.value)


def test_plan_requires_nonempty_unique_pinned_artifacts_and_unique_levels():
    plan, receipts, digest = history()
    for requirements in ((), (plan.requirements[0],) * 2):
        with pytest.raises(ValidationError):
            HistoryPlan(scope_id=uid(1), requirements=requirements)
    bad = plan.model_copy(
        update={"requirements": (plan.requirements[0].model_copy(update={"required_levels": ("query", "query")}),)}
    )
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        history_plan_digest(bad)


def test_unknown_extra_body_fields_are_forbidden():
    plan, receipts, digest = history()
    with pytest.raises(ValidationError):
        HistoryReceipt(**{**receipts[0].model_dump(), "gold": GOLD_CANARY})
