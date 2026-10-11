"""Single execution admission covers shared gateways, nesting, retries and concurrent translation."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event

import pytest

from medops.core.deadline import DeadlineExceeded, deadline_scope
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.execution_budget import (
    ExecutionBudget,
    ExecutionBudgetExceeded,
    ExecutionLimits,
    current_budget,
    default_limits,
    execution_scope,
    request_tokens,
)
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import (
    OPENAI_PRICES,
    ModelOutputInvalid,
    ModelPrice,
    ModelTimeout,
    ModelUsage,
    PriceTable,
)
from medops.infrastructure.llm.meter import MeteredGateway
from tests.unit.infrastructure.test_llm_gateway import _FixedCost, req


def make_gateway(inner=None, **kw):
    inner = inner or _FixedCost(0.00001)
    ledger = InMemorySpendLedger()
    gateway = BudgetedGateway(inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=10, **kw)
    return MeteredGateway(gateway), inner, ledger


def limits(tokens=12_000, cost=0.6, timeout=1):
    return ExecutionLimits(token_limit=tokens, cost_limit_usd=cost, timeout_s=timeout)


def test_shared_execution_rejects_translation_before_provider_when_tokens_insufficient():
    meter, inner, ledger = make_gateway()
    with execution_scope(limits(tokens=1)) as budget, pytest.raises(ExecutionBudgetExceeded):
        meter.complete(req(purpose="query_translation"))
    assert inner.calls == meter.calls == 0 and meter.cost_usd == 0 and not ledger.receipts
    assert budget.snapshot().blocked_reason == "tokens" and budget.snapshot().reserved_tokens == 0
    assert meter.receipts[0].outcome == "denied" and not meter.receipts[0].provider_started


def test_fee_admission_stops_before_provider_and_monthly_reservation():
    meter, inner, ledger = make_gateway()
    with execution_scope(limits(cost=0)) as budget, pytest.raises(ExecutionBudgetExceeded, match="cost"):
        meter.complete(req())
    assert inner.calls == meter.calls == 0 and not ledger.receipts and budget.snapshot().accounted_cost_usd == 0


def test_nested_scopes_and_meters_share_one_allowance_and_return_unused_capacity():
    meter, _, ledger = make_gateway()
    nested = MeteredGateway(meter)
    with execution_scope(limits()) as budget:
        with execution_scope(limits(tokens=50_000, cost=100)) as child:
            assert child is budget
            nested.complete(req())
        meter.complete(req(purpose="judge"))
    s = budget.snapshot()
    assert s.calls == 2 and s.accounted_tokens == s.known_tokens == 30
    assert s.accounted_cost_usd == pytest.approx(0.00002) and s.reserved_tokens == s.reserved_cost_usd == 0
    assert len(ledger.receipts) == 2 and s.limits == limits()


def test_nested_execution_cannot_replace_budget_and_context_is_restored():
    assert current_budget() is None
    with execution_scope(limits()) as outer:
        with pytest.raises(ValueError, match="replace"):
            with execution_scope(limits(), budget=ExecutionBudget(limits())):
                pass
        assert current_budget() is outer
    assert current_budget() is None


def test_concurrent_translation_and_answer_cannot_overbook_one_execution():
    entered, release = Event(), Event()

    class Provider(_FixedCost):
        def complete(self, request):
            entered.set()
            assert release.wait(5)
            return super().complete(request)

    meter, inner, _ = make_gateway(Provider(0.00001))
    request = req()
    with execution_scope(limits(tokens=request_tokens(request))) as budget, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(copy_context().run, meter.complete, request)
        try:
            assert entered.wait(5)
            with pytest.raises(ExecutionBudgetExceeded):
                meter.complete(req(purpose="query_translation"))
        finally:
            release.set()
        # Denial latches the execution: even an in-flight successful response may no longer become an answer.
        with pytest.raises(ExecutionBudgetExceeded):
            pending.result(timeout=5)
    assert inner.calls == 1 and meter.calls == 1 and budget.snapshot().reserved_tokens == 0


@pytest.mark.parametrize("error", [ModelTimeout(), asyncio.CancelledError()])
def test_unknown_failure_consumes_reserved_tokens_and_fee_without_claiming_usage(error):
    meter, _, ledger = make_gateway(FakeModelGateway({"answer": [error]}))
    with execution_scope(limits()) as budget, pytest.raises(type(error)):
        meter.complete(req())
    s = budget.snapshot()
    assert s.accounted_tokens == request_tokens(req()) and s.known_tokens == 0
    assert s.accounted_cost_usd == ledger.receipts[0].accounted_cost_usd == meter.cost_usd
    assert s.known_cost_usd == 0 and s.reserved_tokens == s.reserved_cost_usd == 0


def test_reported_overage_is_preserved_and_no_second_model_call_can_start():
    class Provider(_FixedCost):
        def complete(self, request):
            return super().complete(request).model_copy(update={"usage": ModelUsage(input_tokens=500, output_tokens=5)})

    meter, inner, _ = make_gateway(Provider(0.00001))
    with execution_scope(limits(tokens=request_tokens(req()))) as budget:
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(req())
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(req())
    assert budget.snapshot().accounted_tokens == 505 and inner.calls == 1 and meter.tokens == 505
    assert meter.receipts[0].usage.total_tokens == 505


def test_invalid_structured_response_settles_known_usage_not_the_reservation():
    response = _FixedCost(0.00001).complete(req())
    meter, _, _ = make_gateway(FakeModelGateway({"answer": [ModelOutputInvalid("bad", response=response)]}))
    with execution_scope(limits()) as budget, pytest.raises(ModelOutputInvalid):
        meter.complete(req())
    assert budget.snapshot().accounted_tokens == 15 and budget.snapshot().known_cost_usd == 0.00001


def test_required_gateway_refuses_missing_execution_context_without_charge():
    meter, inner, _ = make_gateway(require_execution_budget=True)
    with pytest.raises(ExecutionBudgetExceeded, match="context"):
        meter.complete(req())
    assert inner.calls == meter.calls == 0 and meter.receipts[0].accounted_cost_usd == 0
    with execution_scope(limits()):
        meter.complete(req())
    assert inner.calls == 1


def test_total_deadline_is_shared_and_nested_scope_cannot_restart_it():
    meter, inner, _ = make_gateway()
    with execution_scope(limits(timeout=0.01)):
        time.sleep(0.02)
        with pytest.raises(DeadlineExceeded), execution_scope(limits(timeout=10)):
            meter.complete(req())
    assert inner.calls == 0


def test_schema_and_utf8_are_included_in_preflight_and_compatible_limits_are_derived():
    plain = req(text="藥abc")
    schema = req(text="藥abc", schema={"type": "object", "properties": {"非常长的字段": {"type": "string"}}})
    assert request_tokens(schema) > request_tokens(plain)
    assert request_tokens(plain) >= len("藥abc".encode()) + plain.max_output_tokens
    assert default_limits(timeout_s=125) == limits(timeout=125)


@pytest.mark.parametrize("owner_timeout,scope_timeout", [(0.01, 10), (1, 0.01)])
def test_reentering_an_explicit_budget_cannot_refresh_its_total_deadline(owner_timeout, scope_timeout):
    owned = ExecutionBudget(limits(timeout=owner_timeout))
    with execution_scope(limits(timeout=scope_timeout), budget=owned):
        pass
    time.sleep(0.02)
    with pytest.raises(DeadlineExceeded):
        with execution_scope(limits(timeout=10), budget=owned):
            pass
    assert current_budget() is None


def test_nested_meter_uses_its_monthly_gateways_admitted_prices():
    prices = PriceTable(
        {"gpt-6-luna": ModelPrice(input_per_mtok=1_000, cached_input_per_mtok=0, output_per_mtok=1_000)}
    )
    inner = _FixedCost(0.00001)
    meter = MeteredGateway(
        MeteredGateway(BudgetedGateway(inner, prices=prices, ledger=InMemorySpendLedger(), monthly_cap_usd=10))
    )
    with execution_scope(limits(cost=0.001)), pytest.raises(ExecutionBudgetExceeded):
        meter.complete(req())
    assert inner.calls == 0 and meter.calls == 0


def test_owned_budget_cannot_outlive_the_deadline_under_which_it_was_started():
    owned = ExecutionBudget(limits(timeout=10))
    with deadline_scope(0.01), execution_scope(limits(timeout=10), budget=owned):
        pass
    time.sleep(0.02)
    with pytest.raises(DeadlineExceeded), execution_scope(limits(timeout=10), budget=owned):
        pass
