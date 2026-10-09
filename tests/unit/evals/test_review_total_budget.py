from __future__ import annotations

import json
from pathlib import Path

import pytest

from medops.evals.review_budget import ReviewBudget

SCOPE = {"model": "fixed", "inputs": "hash", "approval": "fixture"}


def ledger(path: Path, total=1):
    return ReviewBudget(path, total_usd=total, scope=SCOPE)


def test_success_failure_and_invalid_reply_all_count_across_restarts(tmp_path):
    path = tmp_path / "budget.json"
    b = ledger(path)
    for outcome, cost in [("validated_reply", 0.2), ("cli_failed", 0.1), ("ValueError", 0.3)]:
        a = b.reserve(0.4, identity={"sample_id": "fixture"})
        b.finish(a["attempt_id"], cost_usd=cost, outcome=outcome, metadata={})
        b = ledger(path)
    assert b.summary()["known_cost_usd"] == "0.600000"
    assert b.summary()["remaining_usd"] == "0.400000"
    with pytest.raises(ValueError, match="smaller"):
        b.reserve(0.5, identity={})


def test_crash_and_unknown_charges_block_further_calls(tmp_path):
    path = tmp_path / "budget.json"
    b = ledger(path)
    a = b.reserve(0.25, identity={})
    resumed = ledger(path)
    with pytest.raises(ValueError, match="unfinished"):
        resumed.reserve(0.25, identity={})
    resumed.finish(a["attempt_id"], cost_usd=None, outcome="timeout", metadata={})
    with pytest.raises(ValueError, match="unknown-charge"):
        resumed.reserve(0.1, identity={})
    assert resumed.summary()["unresolved_reserved_usd"] == "0.250000"


def test_two_callers_cannot_reserve_overlapping_spend(tmp_path):
    path = tmp_path / "budget.json"
    one, two = ledger(path), ledger(path)
    a = one.reserve(0.6, identity={})
    with pytest.raises(ValueError, match="unfinished"):
        two.reserve(0.6, identity={})
    one.finish(a["attempt_id"], cost_usd=0.6, outcome="valid", metadata={})
    with pytest.raises(ValueError, match="smaller"):
        two.reserve(0.6, identity={})


def test_failed_zero_cost_is_known_and_can_be_retried_under_same_cap(tmp_path):
    b = ledger(tmp_path / "budget.json")
    a = b.reserve(0.25, identity={})
    b.finish(a["attempt_id"], cost_usd=0, outcome="cli_failed", metadata={})
    assert b.summary()["known_cost_usd"] == "0.000000"
    b.reserve(0.25, identity={})


def test_cli_cap_breach_is_retained_and_stops_further_spend(tmp_path):
    b = ledger(tmp_path / "budget.json")
    a = b.reserve(0.1, identity={})
    b.finish(a["attempt_id"], cost_usd=0.15, outcome="valid", metadata={})
    assert b.summary()["known_cost_usd"] == "0.150000"
    with pytest.raises(ValueError, match="exceeded"):
        b.reserve(0.1, identity={})


def test_budget_identity_cannot_be_silently_expanded_or_retargeted(tmp_path):
    path = tmp_path / "budget.json"
    ledger(path)
    with pytest.raises(ValueError, match="authorization changed"):
        ledger(path, total=2)
    with pytest.raises(ValueError, match="authorization changed"):
        ReviewBudget(path, total_usd=1, scope={"model": "different"})


def test_settlement_requires_exactly_one_reservation(tmp_path):
    b = ledger(tmp_path / "budget.json")
    with pytest.raises(ValueError, match="without"):
        b.finish("absent", cost_usd=0, outcome="valid", metadata={})
    a = b.reserve(0.1, identity={})
    b.finish(a["attempt_id"], cost_usd=0, outcome="valid", metadata={})
    with pytest.raises(ValueError, match="twice"):
        b.finish(a["attempt_id"], cost_usd=0, outcome="valid", metadata={})


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), "not_money"])
def test_invalid_budget_never_creates_a_ledger(tmp_path, value):
    path = tmp_path / "budget.json"
    with pytest.raises(ValueError):
        ledger(path, total=value)
    assert not path.exists()


def test_fractional_microdollar_charge_is_rounded_up(tmp_path):
    b = ledger(tmp_path / "budget.json")
    a = b.reserve(0.1, identity={})
    b.finish(a["attempt_id"], cost_usd=0.0000001, outcome="valid", metadata={})
    assert b.summary()["known_cost_usd"] == "0.000001"
    assert json.loads((tmp_path / "budget.json").read_text())["attempts"][0]["cost_usd"] == "0.000001"


def test_authorization_can_limit_attempt_count(tmp_path):
    path = tmp_path / "budget.json"
    scope = {**SCOPE, "max_attempts": 1}
    budget = ReviewBudget(path, total_usd=1, scope=scope)
    attempt = budget.reserve(0.1, identity={})
    budget.finish(attempt["attempt_id"], cost_usd=0.01, outcome="validated_reply", metadata={})
    with pytest.raises(ValueError, match="maximum number"):
        budget.reserve(0.1, identity={})


def test_authorization_can_stop_after_any_nonvalidated_attempt(tmp_path):
    path = tmp_path / "budget.json"
    scope = {**SCOPE, "max_attempts": 3, "stop_on_nonvalidated_attempt": True}
    budget = ReviewBudget(path, total_usd=1, scope=scope)
    attempt = budget.reserve(0.1, identity={})
    budget.finish(attempt["attempt_id"], cost_usd=0, outcome="cli_failed", metadata={})
    with pytest.raises(ValueError, match="nonvalidated"):
        budget.reserve(0.1, identity={})


def test_validated_reply_reconciliation_preserves_failure_and_unblocks_remaining_calls(tmp_path):
    scope = {**SCOPE, "max_attempts": 3, "stop_on_nonvalidated_attempt": True}
    budget = ReviewBudget(tmp_path / "budget.json", total_usd=1.0, scope=scope)
    failed = budget.reserve(0.3, identity={"sample_id": "case-1"})
    budget.finish(failed["attempt_id"], cost_usd=0.08, outcome="ValueError", metadata={})
    evidence = {"kind": "structured-output-recovery", "capture_sha256": "a" * 64}
    budget.reconcile_validated_reply(failed["attempt_id"], evidence=evidence)
    budget.reconcile_validated_reply(failed["attempt_id"], evidence=evidence)
    following = budget.reserve(0.3, identity={"sample_id": "case-2"})
    assert following["status"] == "reserved"
    document = json.loads((tmp_path / "budget.json").read_text())
    assert document["attempts"][0]["outcome"] == "ValueError"
    assert document["attempts"][0]["reconciliation"]["outcome"] == "validated_reply"


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3"])
def test_invalid_max_attempts_is_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="max_attempts"):
        ReviewBudget(tmp_path / "budget.json", total_usd=1, scope={**SCOPE, "max_attempts": value})
