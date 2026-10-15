"""Final-verification headroom shares the original atomic execution budget."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event

import pytest
from pydantic import ValidationError

from medops.infrastructure.llm.accounting import new_call
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.execution_budget import (
    PRICES,
    BudgetProtection,
    CallAllowance,
    ExecutionBudget,
    ExecutionBudgetExceeded,
    ExecutionLimits,
    allowance,
    current_budget,
    execution_scope,
    request_tokens,
)
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelCall, ModelCallReceipt, ModelTimeout, ModelUsage
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.model_gateway import _FixedCost, req


def limits(tokens=12000, cost=0.6):
    return ExecutionLimits(token_limit=tokens, cost_limit_usd=cost, timeout_s=125)


def priced_request():
    request = req()
    return request.model_copy(update={"call": new_call(request, "stub")})


def receipt(item, *, tokens, cost=0):
    return ModelCallReceipt(
        call=ModelCall(call_id=item.call_id, purpose="PUBLIC-test", requested_model="gpt-6-luna", provider="stub"),
        outcome="succeeded",
        provider_started=True,
        estimated_cost_usd=item.cost_usd,
        actual_cost_usd=cost,
        accounted_cost_usd=cost,
        cost_basis="reported_usage",
        settlement_status="not_required",
        usage=ModelUsage(input_tokens=tokens, output_tokens=0),
    )


@pytest.mark.parametrize("dimension", ["tokens", "cost"])
def test_protection_refuses_before_provider_and_monthly_reservation(dimension):
    request = priced_request()
    expected = allowance(request)
    bound = limits(tokens=expected.tokens + 99) if dimension == "tokens" else limits(cost=0.01 + expected.cost_usd / 2)
    ledger, provider = InMemorySpendLedger(), _FixedCost(0.000001)
    meter = MeteredGateway(BudgetedGateway(provider, prices=PRICES, ledger=ledger, monthly_cap_usd=10))
    with execution_scope(bound) as budget:
        budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        assert not budget.fits(expected)
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(request)
    s = budget.snapshot()
    assert provider.calls == meter.calls == 0 and not ledger.receipts
    assert s.accounted_tokens == s.reserved_tokens == s.accounted_cost_usd == s.reserved_cost_usd == 0
    assert s.protected_tokens == 100 and s.protected_cost_usd == 0.01
    assert len(meter.receipts) == 1 and meter.receipts[0].outcome == "denied" and not meter.receipts[0].provider_started


def test_nested_scopes_and_meters_cannot_double_spend_or_relax_the_floor():
    provider = _FixedCost(0.000001)
    meter = MeteredGateway(MeteredGateway(provider))
    request = priced_request()
    with execution_scope(limits(tokens=request_tokens(request) + 100)) as budget:
        budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        with execution_scope(limits(tokens=50000, cost=50)) as nested:
            assert nested is current_budget() is budget
            nested.protect_remaining(BudgetProtection(tokens=0, cost_usd=0.0))
            meter.complete(request)
    s = budget.snapshot()
    assert s.protected_tokens == 100 and s.protected_cost_usd == 0.01
    assert s.calls == provider.calls == 1 and s.accounted_tokens == s.known_tokens == 15
    assert s.reserved_tokens == s.reserved_cost_usd == 0 and len(meter.receipts) == 1


def test_parallel_calls_cannot_overbook_protected_tokens():
    entered, release = Event(), Event()

    class Provider(_FixedCost):
        def complete(self, request):
            entered.set()
            assert release.wait(5)
            return super().complete(request)

    provider = Provider(0.000001)
    meter = MeteredGateway(provider)
    n = request_tokens(req())
    with execution_scope(limits(tokens=2 * n + 99)) as budget, ThreadPoolExecutor(max_workers=1) as pool:
        budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        pending = pool.submit(copy_context().run, meter.complete, req())
        try:
            assert entered.wait(5)
            with pytest.raises(ExecutionBudgetExceeded):
                meter.complete(req(purpose="query_translation"))
        finally:
            release.set()
        with pytest.raises(ExecutionBudgetExceeded):
            pending.result(timeout=5)  # denial is latched, including an already-running answer
    s = budget.snapshot()
    assert provider.calls == 1 and len(meter.receipts) == 2
    assert s.calls == 1 and s.accounted_tokens == 15 and s.reserved_tokens == 0 and s.protected_tokens == 100


@pytest.mark.parametrize("error", [ModelTimeout(), asyncio.CancelledError()])
def test_unknown_usage_and_cancel_retain_conservative_cost_and_protection(error):
    meter = MeteredGateway(FakeModelGateway({"answer": [error]}))
    request = priced_request()
    expected = allowance(request)
    with execution_scope(limits(tokens=expected.tokens + 100)) as budget:
        budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        with pytest.raises(type(error)):
            meter.complete(request)
    s = budget.snapshot()
    assert s.accounted_tokens == expected.tokens and s.known_tokens == 0
    assert s.accounted_cost_usd == pytest.approx(expected.cost_usd) and s.known_cost_usd == 0
    assert s.protected_tokens == 100 and s.protected_cost_usd == 0.01 and s.reserved_tokens == 0
    assert meter.receipts[0].cost_basis == "conservative_reservation"


@pytest.mark.parametrize("dimension", ["tokens", "cost"])
def test_reported_usage_invading_protection_is_retained_then_stops(dimension):
    request = priced_request()
    expected = allowance(request)

    class Provider(_FixedCost):
        def complete(self, request):
            response = super().complete(request)
            return response.model_copy(update={"usage": ModelUsage(input_tokens=expected.tokens + 1, output_tokens=0)})

    provider = Provider(expected.cost_usd + 0.000001 if dimension == "cost" else 0.000001)
    meter = MeteredGateway(provider)
    bound = limits(tokens=expected.tokens + 100) if dimension == "tokens" else limits(cost=expected.cost_usd + 0.01)
    with execution_scope(bound) as budget:
        budget.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(request)
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(req(purpose="PUBLIC-second"))
    s = budget.snapshot()
    assert provider.calls == 1 and s.accounted_tokens == expected.tokens + 1
    assert s.accounted_cost_usd == provider.cost and s.blocked_reason == dimension
    assert meter.receipts[0].provider_started and meter.receipts[0].usage.total_tokens == expected.tokens + 1


@pytest.mark.parametrize("protected", [False, True])
def test_settlement_preserves_zero_protection_legacy_behavior_with_pending_calls(protected):
    budget = ExecutionBudget(limits(tokens=25 if protected else 20))
    if protected:
        budget.protect_remaining(BudgetProtection(tokens=5))
    one, two = CallAllowance("PUBLIC-one", 10, 0), CallAllowance("PUBLIC-two", 10, 0)
    budget.reserve(one)
    budget.reserve(two)
    budget.settle(one, receipt(one, tokens=15))
    assert budget.snapshot().blocked_reason == ("tokens" if protected else None)
    budget.settle(two, receipt(two, tokens=5))
    assert budget.snapshot().accounted_tokens == 20 and budget.snapshot().reserved_tokens == 0
    if protected:
        with pytest.raises(ExecutionBudgetExceeded):
            budget.check()
    else:
        budget.check()


def test_protection_increase_accounts_for_active_and_known_usage_without_new_fee_entries():
    budget = ExecutionBudget(limits(tokens=100))
    item = CallAllowance("PUBLIC-pending", 60, 0.01)
    budget.reserve(item)
    budget.protect_remaining(BudgetProtection(tokens=40, cost_usd=0.02))
    before = budget.snapshot()
    assert before.reserved_tokens == 60 and before.calls == 0 and before.accounted_cost_usd == 0
    with pytest.raises(ExecutionBudgetExceeded):
        budget.protect_remaining(BudgetProtection(tokens=41))
    assert budget.protection().tokens == 40 and budget.snapshot().reserved_tokens == 60
    budget.settle(item, receipt(item, tokens=15, cost=0.001))
    assert budget.snapshot().known_tokens == 15 and budget.snapshot().accounted_cost_usd == 0.001


def test_protection_is_monotone_per_dimension_and_survives_context_reentry():
    owned = ExecutionBudget(limits())
    with execution_scope(limits(), budget=owned):
        owned.protect_remaining(BudgetProtection(tokens=100, cost_usd=0.01))
        owned.protect_remaining(BudgetProtection(tokens=50, cost_usd=0.02))
    with execution_scope(limits(tokens=50000, cost=100), budget=owned):
        owned.protect_remaining(BudgetProtection())
        assert owned.protection() == BudgetProtection(tokens=100, cost_usd=0.02)
    s = owned.snapshot()
    assert s.accounted_tokens == s.reserved_tokens == s.calls == 0 and s.accounted_cost_usd == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("tokens", True),
        ("tokens", -1),
        ("tokens", 1.5),
        ("cost_usd", True),
        ("cost_usd", -0.01),
        ("cost_usd", float("inf")),
        ("cost_usd", float("nan")),
    ],
)
def test_forged_protection_values_cannot_change_budget(field, value):
    budget = ExecutionBudget(limits())
    forged = BudgetProtection().model_copy(update={field: value})
    with pytest.raises(ValidationError):
        budget.protect_remaining(forged)
    assert budget.protection() == BudgetProtection() and budget.snapshot().blocked_reason is None
