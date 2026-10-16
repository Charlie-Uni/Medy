"""Whole-operation estimates are not usage, reservations or provider calls."""

import pytest
from pydantic import ValidationError

from medops.infrastructure.llm.accounting import new_call
from medops.infrastructure.llm.call_plan import ModelCallPlan
from medops.infrastructure.llm.execution_budget import (
    BudgetProtection,
    CallAllowance,
    ExecutionBudget,
    ExecutionLimits,
    allowance,
    estimate_request,
)
from medops.infrastructure.llm.gateway import Message, ModelPrice, ModelRequest, PriceTable


def request(**updates):
    values = dict(
        purpose="PUBLIC",
        model_id="gpt-6-sol",
        messages=(Message(role="user", content="PUBLIC 药物警戒"),),
        max_output_tokens=80,
        json_schema={"type": "object"},
    )
    values.update(updates)
    return ModelRequest(**values)


def test_pure_request_estimate_matches_original_physical_allowance():
    r = request()
    item = estimate_request(r)
    actual = allowance(r.model_copy(update={"call": new_call(r, "fake")}))
    assert r.call is None and (item.tokens, item.cost_usd) == (actual.tokens, actual.cost_usd)
    assert item.tokens > 80 + len("PUBLIC 药物警戒".encode())


def test_retry_bound_and_each_request_output_and_schema_are_counted():
    items = (request(), request(max_output_tokens=600, json_schema={"type": "object", "description": "PUBLIC长Schema"}))
    estimate = ModelCallPlan(requests=items, max_attempts=3).estimate()
    assert estimate.tokens == sum(estimate_request(r).tokens for r in items) * 3
    assert estimate.cost_usd == sum(estimate_request(r).cost_usd for r in items) * 3
    assert ModelCallPlan().estimate().tokens == ModelCallPlan().estimate().cost_usd == 0


def test_custom_gateway_price_table_is_used():
    prices = PriceTable({"gpt-6-sol": ModelPrice(input_per_mtok=20, output_per_mtok=100, cached_input_per_mtok=2)})
    plan = ModelCallPlan(requests=(request(),), max_attempts=3)
    assert plan.estimate(prices).cost_usd == pytest.approx(plan.estimate().cost_usd * 10)
    assert plan.audit_record(prices)["plan_sha256"] != plan.audit_record()["plan_sha256"]


def test_fits_includes_inflight_and_protection_without_mutation_or_fake_accounting():
    budget = ExecutionBudget(ExecutionLimits(token_limit=1000, cost_limit_usd=1, timeout_s=10))
    budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.1))
    budget.reserve(CallAllowance("PUBLIC-pending", 300, 0.3))
    before = budget.snapshot()
    assert not budget.fits(ModelCallPlan(requests=(request(),), max_attempts=3).estimate())
    assert budget.snapshot() == before and before.calls == before.accounted_tokens == 0


@pytest.mark.parametrize("attempts", [0, 4, True, "3"])
def test_invalid_retry_count_fails_closed(attempts):
    with pytest.raises(ValidationError):
        ModelCallPlan(max_attempts=attempts)


def test_unbounded_request_list_rejected():
    with pytest.raises(ValidationError):
        ModelCallPlan(requests=(request(),) * 21)
