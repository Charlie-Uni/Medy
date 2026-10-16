"""Sealed final requests spend existing protection, never a second root allowance."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from threading import Event

import pytest

from medops.core.deadline import CURRENT_DEADLINE, Deadline, DeadlineExceeded
from medops.infrastructure.llm.accounting import call_scope, new_call
from medops.infrastructure.llm.execution_budget import (
    BudgetProtection,
    CallAllowance,
    ExecutionBudgetExceeded,
    ExecutionLimits,
    estimate_request,
    execution_scope,
    finalization_scope,
    request_fits_budget,
)
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout, ModelUsage
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.model_gateway import _FixedCost, req


@contextmanager
def protected(requests, *, extra=0, floor_tokens=None, floor_cost=None):
    items = [estimate_request(r) for r in requests]
    tokens, cost = sum(e.tokens for e in items), round(sum(e.cost_usd for e in items), 8)
    with execution_scope(ExecutionLimits(token_limit=max(1, tokens + extra), cost_limit_usd=1, timeout_s=10)) as budget:
        budget.protect_remaining(
            BudgetProtection(
                tokens=tokens if floor_tokens is None else floor_tokens,
                cost_usd=cost if floor_cost is None else floor_cost,
            )
        )
        yield budget


def test_only_exact_final_requests_can_spend_protection_and_exit_never_reopens_it():
    r = req()
    meter = MeteredGateway(_FixedCost(0))
    with protected((r,)) as budget:
        assert not request_fits_budget(r)
        with finalization_scope((r,)) as profile:
            assert profile.estimated_tokens == estimate_request(r).tokens
            assert request_fits_budget(r)
            meter.complete(r)
        assert budget.finalization_snapshot().state == "closed"
        assert budget.protection().tokens == 0 and budget.snapshot().known_tokens == 15
        assert not request_fits_budget(r)
        with execution_scope(budget.limits), pytest.raises(ExecutionBudgetExceeded, match="sealed"):
            meter.complete(r)
    assert meter.calls == 1 and len(meter.receipts) == 2 and not meter.receipts[-1].provider_started


@pytest.mark.parametrize("field", ["tokens", "cost"])
def test_final_plan_must_fit_installed_protection_even_if_root_has_spare_capacity(field):
    r = req()
    e = estimate_request(r)
    changes = {"floor_tokens": e.tokens - 1} if field == "tokens" else {"floor_cost": 0.0}
    with protected((r,), extra=1000, **changes) as budget:
        before = budget.snapshot()
        with pytest.raises(ExecutionBudgetExceeded, match="finalization_" + field), finalization_scope((r,)):
            pytest.fail("insufficient floor cannot enter finalization")
        assert budget.finalization_snapshot() is None and budget.snapshot() == before


@pytest.mark.parametrize("change", ["prompt", "model", "purpose", "output", "schema", "temperature", "timeout"])
def test_changed_request_fails_before_provider_and_latches_integrity_stop(change):
    r = req().model_copy(update={"timeout_s": 5})
    updates = {
        "prompt": {"messages": req(text="jello").messages},
        "model": {"model_id": "gpt-6-sol"},
        "purpose": {"purpose": "other"},
        "output": {"max_output_tokens": 101},
        "schema": {"json_schema": {"type": "object"}},
        "temperature": {"temperature": 0.1},
        "timeout": {"timeout_s": 10},
    }[change]
    fake = FakeModelGateway(default=["ok"])
    meter = MeteredGateway(fake)
    with protected((r,), extra=1000) as budget:
        with finalization_scope((r,)):
            with pytest.raises(ExecutionBudgetExceeded, match="finalization_request"):
                meter.complete(r.model_copy(update=updates))
        assert budget.snapshot().blocked_reason == "finalization_request"
    assert not fake.calls and not meter.calls and not meter.receipts[0].provider_started


def test_retry_slots_count_failed_unknown_usage_and_stop_a_fourth_attempt():
    r = req()
    e = estimate_request(r)
    fake = FakeModelGateway(default=[ModelTimeout(), ModelTimeout(), ModelTimeout()])
    meter = MeteredGateway(fake)
    with protected((r,) * 3) as budget:
        with finalization_scope((r,) * 3) as profile:
            for _ in range(3):
                with pytest.raises(ModelTimeout):
                    meter.complete(r)
            with pytest.raises(ExecutionBudgetExceeded):
                meter.complete(r)
        assert budget.snapshot().accounted_tokens == profile.estimated_tokens == 3 * e.tokens
        assert budget.snapshot().known_tokens == 0 and budget.protection().tokens == 0
        assert budget.finalization_snapshot().admitted_calls == 3
    assert len(fake.calls) == 3 and len(meter.receipts) == 4
    assert all(x.cost_basis == "conservative_reservation" for x in meter.receipts[:3])


def test_success_returns_unused_allowance_without_authorizing_more_requests():
    r = req()
    meter = MeteredGateway(_FixedCost(0))
    with protected((r,) * 3) as budget:
        with finalization_scope((r,) * 3):
            meter.complete(r)
        assert budget.snapshot().known_tokens == 15 and budget.protection().tokens == 2 * estimate_request(r).tokens
        with pytest.raises(ExecutionBudgetExceeded), finalization_scope((r,)):
            pytest.fail("closed phase cannot restart")
        with pytest.raises(ExecutionBudgetExceeded):
            budget.protect_remaining(BudgetProtection(tokens=1))


@pytest.mark.parametrize("error", [ModelTimeout(), KeyboardInterrupt()])
def test_exception_or_cancel_seals_phase_and_keeps_unknown_usage(error):
    r = req()
    meter = MeteredGateway(FakeModelGateway(default=[error]))
    with protected((r,)) as budget:
        with pytest.raises(type(error)), finalization_scope((r,)):
            meter.complete(r)
        assert budget.finalization_snapshot().state == "closed"
        assert budget.snapshot().accounted_tokens == estimate_request(r).tokens
        assert budget.snapshot().known_tokens == 0 and len(meter.receipts) == 1


def test_child_thread_without_final_capability_cannot_spend_or_poison_final_lane():
    r = req()
    meter = MeteredGateway(_FixedCost(0))
    with protected((r,)) as budget:
        ordinary = copy_context()
        with finalization_scope((r,)):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(ordinary.run, meter.complete, r)
                with pytest.raises(ExecutionBudgetExceeded):
                    future.result(timeout=3)
            assert budget.snapshot().blocked_reason is None
            meter.complete(r)
    assert meter.calls == 1 and len(meter.receipts) == 2


def test_inherited_final_capability_still_denies_a_late_response_after_scope_exit():
    r = req()
    started = Event()
    release = Event()

    class Blocking(_FixedCost):
        def complete(self, request):
            started.set()
            assert release.wait(3)
            return super().complete(request)

    meter = MeteredGateway(Blocking(0.00001))
    with protected((r,)) as budget, ThreadPoolExecutor(max_workers=1) as pool:
        with finalization_scope((r,)):
            child = copy_context()
            future = pool.submit(child.run, meter.complete, r)
            assert started.wait(3)
        release.set()
        with pytest.raises(ExecutionBudgetExceeded, match="sealed"):
            future.result(timeout=3)
        assert budget.snapshot().known_tokens == 15 and budget.snapshot().accounted_cost_usd == 0.00001
        assert budget.snapshot().reserved_tokens == 0
    assert len(meter.receipts) == 1 and meter.receipts[0].provider_started


@pytest.mark.parametrize("dimension", ["tokens", "cost"])
def test_surprise_actual_usage_over_final_quote_is_retained_and_rejected(dimension):
    r = req()
    e = estimate_request(r)

    class Surprise(_FixedCost):
        def complete(self, request):
            response = super().complete(request)
            return (
                response.model_copy(update={"usage": ModelUsage(input_tokens=e.tokens + 1, output_tokens=0)})
                if dimension == "tokens"
                else response
            )

    meter = MeteredGateway(Surprise(e.cost_usd + 0.01 if dimension == "cost" else 0))
    with protected((r,), extra=1000) as budget:
        with pytest.raises(ExecutionBudgetExceeded, match=dimension), finalization_scope((r,)):
            meter.complete(r)
        assert budget.snapshot().blocked_reason == dimension and meter.receipts[0].usage is not None
        if dimension == "tokens":
            assert budget.snapshot().known_tokens == e.tokens + 1
        else:
            assert budget.snapshot().accounted_cost_usd == pytest.approx(e.cost_usd + 0.01)


def test_zero_model_final_phase_never_fabricates_calls_or_releases_unused_floor():
    with protected((), floor_tokens=1, floor_cost=0.01) as budget:
        before = budget.snapshot()
        with finalization_scope(()) as profile:
            assert profile.max_calls == profile.estimated_tokens == profile.estimated_cost_usd == 0
        assert budget.snapshot() == before and budget.finalization_snapshot().state == "closed"


def test_begin_requires_original_context_and_no_inflight_calls():
    r = req()
    with pytest.raises(ExecutionBudgetExceeded, match="context"), finalization_scope((r,)):
        pytest.fail("no root")
    with protected((r,), extra=1) as budget:
        budget.reserve(CallAllowance("PUBLIC-pending", 1, 0))
        with pytest.raises(ExecutionBudgetExceeded, match="inflight"), finalization_scope((r,)):
            pytest.fail("active call")
        assert budget.snapshot().reserved_tokens == 1 and budget.finalization_snapshot() is None


def test_finalization_cannot_reset_original_deadline_or_bypass_ownership_guard():
    import time

    r = req()
    with protected((r,)) as budget:
        token = CURRENT_DEADLINE.set(Deadline(time.monotonic() - 1))
        try:
            with pytest.raises(DeadlineExceeded), finalization_scope((r,)):
                pytest.fail("expired root")
        finally:
            CURRENT_DEADLINE.reset(token)

        def revoked():
            raise RuntimeError("PUBLIC revoked")

        with call_scope(before_call=revoked), pytest.raises(RuntimeError), finalization_scope((r,)):
            pytest.fail("revoked owner")
        assert budget.finalization_snapshot() is None


def test_unissued_requests_only_and_original_bound_are_enforced():
    r = req()
    with protected((r,) * 3) as budget:
        with pytest.raises(ValueError), finalization_scope((r,) * 61):
            pytest.fail("unbounded plan")
        with pytest.raises(ValueError), finalization_scope((r.model_copy(update={"call": new_call(r, "fake")}),)):
            pytest.fail("issued request")
        assert budget.finalization_snapshot() is None


def test_nested_monthly_gateway_and_meters_consume_one_final_slot_and_one_real_receipt():
    from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
    from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable

    r = req()
    inner = _FixedCost(0.00001)
    ledger = InMemorySpendLedger()
    monthly = BudgetedGateway(inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=1)
    meter = MeteredGateway(MeteredGateway(monthly))
    with protected((r,)) as budget:
        with finalization_scope((r,), prices=meter.execution_prices):
            meter.complete(r)
        assert budget.finalization_snapshot().admitted_calls == budget.snapshot().calls == 1
        assert budget.snapshot().known_tokens == 15 and budget.snapshot().reserved_tokens == 0
    assert inner.calls == len(meter.receipts) == len(ledger.receipts) == 1


def test_pricing_change_after_final_quote_cannot_reprice_the_allowed_call_silently():
    from medops.infrastructure.llm.gateway import ModelPrice, PriceTable

    r = req()
    inner = _FixedCost(0)
    meter = MeteredGateway(inner)
    with protected((r,)) as budget:
        with finalization_scope((r,)):
            inner.execution_prices = PriceTable(
                {r.model_id: ModelPrice(input_per_mtok=10, output_per_mtok=10, cached_input_per_mtok=10)}
            )
            with pytest.raises(ExecutionBudgetExceeded, match="finalization_request"):
                meter.complete(r)
        assert budget.snapshot().calls == 0
    assert inner.calls == 0 and not meter.receipts[0].provider_started
