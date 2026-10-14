import json

import pytest
from pydantic import ValidationError

from medops.evals.isolation import screening
from medops.evals.isolation.contracts import IsolationError
from medops.evals.isolation.screening import ScreeningPolicy, screen_queries
from tests.support.eval_isolation import GOLD_CANARY, uid
from tests.support.eval_screening import inputs, policy


@pytest.mark.parametrize(
    "left,right,reason",
    [
        ("same", "same", "query_exact"),
        ("剂量为５０㎎。", "剂量为50mg。", "query_normalized"),
        ("public synthetic question A?", "public synthetic question A!", "query_near"),
    ],
)
def test_exact_normalized_or_fuzzy_candidate_is_private_review_not_equivalence(left, right, reason):
    result = screen_queries(**inputs((left,), (right,)))
    assert len(result.matches) == 1 and result.matches[0].reason == reason
    assert result.matches[0].disposition == "review_required" and result.qualification == "unknown"
    assert result.compared_pairs == 1 and result.deployment_isolation_verified is False
    payload = json.loads(result.model_dump_json())
    assert "query" not in payload and "gold" not in payload and GOLD_CANARY not in json.dumps(payload)
    assert set(payload["matches"][0]) == {
        "left_item_id",
        "right_item_id",
        "reason",
        "numerator",
        "denominator",
        "disposition",
    }


@pytest.mark.parametrize(
    "left,right",
    [("ab", "ac"), ("甲乙", "AB"), ("中文药物警戒审计分级", "English audit finding classification"), ("", "x")],
)
def test_unmatched_or_short_queries_never_become_certified_unseen(left, right):
    if not left:
        with pytest.raises(ValidationError):
            inputs((left,), (right,))
        return
    result = screen_queries(**inputs((left,), (right,)))
    assert result.matches == () and result.qualification == "unknown"


def test_rational_threshold_boundary_is_inclusive_without_float_rounding():
    value = inputs(
        ("abcde",), ("abcfg",), width=2, min_normalized_chars=5, threshold_numerator=1, threshold_denominator=3
    )
    match = screen_queries(**value).matches[0]
    assert (match.numerator, match.denominator) == (2, 6)
    higher = inputs(
        ("abcde",), ("abcfg",), width=2, min_normalized_chars=5, threshold_numerator=2, threshold_denominator=5
    )
    assert not screen_queries(**higher).matches


@pytest.mark.parametrize(
    "left,right",
    [
        (
            "The synthetic record contains a dose of 10 mg and remains unchanged.",
            "The synthetic record contains a dose of 20 mg and remains unchanged.",
        ),
        (
            "The synthetic record states the action is permitted for this particular condition.",
            "The synthetic record states the action is not permitted for this particular condition.",
        ),
    ],
)
def test_numbers_and_negation_changes_are_not_normalized_away_or_auto_merged(left, right):
    value = inputs((left,), (right,))
    result = screen_queries(**value)
    assert result.matches and result.matches[0].reason == "query_near"
    assert value["left"].items[0].normalized_query_sha256 != value["right"].items[0].normalized_query_sha256
    assert result.matches[0].disposition == "review_required"


def test_all_cross_pairs_and_order_stable_content_bindings():
    value = inputs(
        ("public synthetic question A?", "public synthetic question B?"),
        ("public synthetic question A!", "public synthetic question B!"),
    )
    original = screen_queries(**value)
    reverse = screen_queries(
        **{
            **value,
            "left_inputs": tuple(reversed(value["left_inputs"])),
            "right_inputs": tuple(reversed(value["right_inputs"])),
        }
    )
    assert original == reverse and original.compared_pairs == 4 and len(original.matches) == 4


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "extra", "raw_hash", "norm_hash", "wrong_query", "same_collection", "method"]
)
def test_wrong_projection_or_method_binding_rejects_without_echo(change):
    value = inputs()
    if change == "missing":
        value["left_inputs"] = ()
    elif change == "duplicate":
        value["left_inputs"] = (value["left_inputs"][0],) * 2
    elif change == "extra":
        value["left_inputs"] = (value["left_inputs"][0].model_copy(update={"item_id": uid(999)}),)
    elif change == "wrong_query":
        value["left_inputs"] = (value["left_inputs"][0].model_copy(update={"query": GOLD_CANARY}),)
    elif change == "same_collection":
        value["right"] = value["right"].model_copy(update={"collection_id": value["left"].collection_id})
    elif change == "method":
        value["expected_method_sha256"] = "f" * 64
    else:
        field = "query_sha256" if change == "raw_hash" else "normalized_query_sha256"
        value["left"] = value["left"].model_copy(
            update={"items": (value["left"].items[0].model_copy(update={field: "f" * 64}),)}
        )
    with pytest.raises(IsolationError) as error:
        screen_queries(**value)
    assert str(error.value) in {"binding_mismatch", "invalid_metadata"} and GOLD_CANARY not in str(error.value)


@pytest.mark.parametrize(
    "changes", [{"max_items_per_collection": 1}, {"max_comparisons": 1}, {"max_total_query_chars": 1}]
)
def test_limits_fail_without_returning_a_truncated_match_list(changes):
    value = inputs(("public question one?", "public question two?"), ("public question one!",), **changes)
    with pytest.raises(IsolationError, match="^screening_limit$"):
        screen_queries(**value)


def test_raw_character_limit_is_checked_before_normalization(monkeypatch):
    value = inputs(max_total_query_chars=1)

    def forbidden(_):
        raise AssertionError("normalization should not run")

    monkeypatch.setattr(screening, "normalize_text", forbidden)
    with pytest.raises(IsolationError, match="^screening_limit$"):
        screen_queries(**value)


@pytest.mark.parametrize(
    "changes",
    [
        {"width": True},
        {"width": 1},
        {"min_normalized_chars": 2},
        {"threshold_numerator": 6, "threshold_denominator": 5},
        {"max_comparisons": 0},
        {"max_total_query_chars": True},
    ],
)
def test_invalid_copied_policy_has_fixed_error(changes):
    value = inputs()
    value["policy"] = policy(**changes)
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        screen_queries(**value)


def test_policy_limits_and_thresholds_must_be_explicit():
    with pytest.raises(ValidationError):
        ScreeningPolicy(method_id=uid(1))


def test_blank_normalized_projection_is_rejected():
    with pytest.raises(IsolationError, match="^invalid_payload$"):
        screen_queries(**inputs(("   ",), ("abc",)))
