"""Original-root handoff, exact accounting and fail-closed interrupted final phases."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event

import pytest
from pydantic import ValidationError

from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, restore_consumed_budget
from medops.infrastructure.llm.execution_budget import (
    BudgetProtection,
    CallAllowance,
    ExecutionBudget,
    ExecutionBudgetExceeded,
    ExecutionLimits,
    execution_scope,
    finalization_scope,
)
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.model_gateway import _FixedCost, req


def limits():
    return ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=10)


def recover(state):
    return restore_consumed_budget(state, expires_at_monotonic=time.monotonic() + state.remaining_timeout_s - 0.01)


def test_settled_cost_and_protection_survive_and_original_root_is_permanently_stopped():
    meter = MeteredGateway(_FixedCost(0.001))
    with execution_scope(limits()) as old:
        old.protect_remaining(BudgetProtection(tokens=1000, cost_usd=0.05))
        meter.complete(req())
        before = old.snapshot()
        state = FrozenBudgetState.model_validate(old.freeze_state())
        for action in [
            old.check,
            lambda: old.freeze_state(),
            lambda: old.protect_remaining(BudgetProtection()),
            lambda: old.remaining_timeout(100),
        ]:
            with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
                action()
        assert not old.fits(CallAllowance("other", 1, 0))
        with pytest.raises(ValueError, match="replace"):
            recover(state)
    restored = recover(state)
    assert restored.snapshot() == before
    with execution_scope(limits(), budget=restored):
        meter.complete(req())
    assert restored.snapshot().accounted_tokens == 30
    assert restored.snapshot().accounted_cost_usd == pytest.approx(0.002)
    assert restored.protection() == old.protection()
    with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"), execution_scope(limits(), budget=old):
        pytest.fail("old root cannot reopen")


def test_concurrent_freeze_grants_one_image():
    with execution_scope(limits()) as budget:
        contexts = [copy_context() for _ in range(6)]

        def freeze(context):
            try:
                return context.run(budget.freeze_state)
            except ExecutionBudgetExceeded:
                return None

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(freeze, contexts))
    assert sum(isinstance(r, dict) for r in results) == 1


def test_pending_call_remains_reserved_and_late_known_fee_is_not_erased():
    entered, release = Event(), Event()

    class Provider(_FixedCost):
        def complete(self, request):
            entered.set()
            assert release.wait(3)
            return super().complete(request)

    meter = MeteredGateway(Provider(0.001))
    with execution_scope(limits()) as old, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(copy_context().run, meter.complete, req())
        assert entered.wait(2)
        state = FrozenBudgetState.model_validate(old.freeze_state())
        assert len(state.pending) == 1 and state.snapshot.reserved_tokens > 0
        release.set()
        with pytest.raises(ExecutionBudgetExceeded, match="checkpoint_suspended"):
            pending.result(timeout=3)
        assert old.snapshot().known_tokens == 15 and old.snapshot().accounted_cost_usd == 0.001
    restored = recover(state)
    assert restored.snapshot().reserved_tokens == state.snapshot.reserved_tokens
    assert restored.snapshot().reserved_cost_usd == state.snapshot.reserved_cost_usd
    assert restored.snapshot().known_tokens == 0
    with pytest.raises(ExecutionBudgetExceeded, match="recovery_inflight"):
        restored.check()
    assert len(meter.receipts) == 1 and meter.receipts[0].usage.total_tokens == 15


def test_settled_unknown_usage_keeps_conservative_cost_and_original_call_identity():
    meter = MeteredGateway(FakeModelGateway(default=[ModelTimeout()]))
    with execution_scope(limits()) as budget:
        with pytest.raises(ModelTimeout):
            meter.complete(req())
        before = budget.snapshot()
        state = FrozenBudgetState.model_validate(budget.freeze_state())
    restored = recover(state)
    assert restored.snapshot() == before and before.known_tokens == 0 and before.accounted_tokens > 0
    assert before.accounted_cost_usd > 0
    with pytest.raises(ValueError, match="reused"):
        restored.reserve(CallAllowance(meter.receipts[0].call.call_id, 1, 0))


@pytest.mark.parametrize("active", [False, True])
def test_final_profile_used_slots_and_seal_survive_without_releasing_remaining_floor(active):
    request = req(text="PUBLIC-PRIVATE-CANARY-NOT-IN-CHECKPOINT")
    meter = MeteredGateway(_FixedCost(0.00001))
    with execution_scope(limits()) as budget:
        budget.protect_remaining(BudgetProtection(tokens=2000, cost_usd=0.05))
        with finalization_scope((request,) * 3):
            meter.complete(request)
            if active:
                raw = budget.freeze_state()
        if not active:
            raw = budget.freeze_state()
        state = FrozenBudgetState.model_validate(raw)
    assert "PUBLIC-PRIVATE-CANARY" not in json.dumps(raw)
    restored = recover(state)
    final = restored.finalization_snapshot()
    assert final.state == "closed" and final.admitted_calls == 1 and final.profile == state.final_phase.profile
    assert restored.protection() == budget.protection()
    assert len(state.final_phase.slots) == 3 and sum(s.used for s in state.final_phase.slots) == 1
    with execution_scope(limits(), budget=restored):
        with pytest.raises(ExecutionBudgetExceeded):
            meter.complete(request)
        with pytest.raises(ExecutionBudgetExceeded), finalization_scope((request,)):
            pytest.fail("cannot mint fresh final slots")
    assert meter.calls == 1


@pytest.mark.parametrize(
    "field", ["protected_tokens", "protected_cost_usd", "calls", "blocked_reason", "known_cost_usd", "limits"]
)
def test_snapshot_compatibility_defaults_cannot_fill_holes_in_recovery(field):
    with execution_scope(limits()) as budget:
        raw = budget.freeze_state()
    del raw["snapshot"][field]
    with pytest.raises(ValidationError):
        FrozenBudgetState.model_validate(raw)


@pytest.mark.parametrize(
    "change", ["version", "runtime", "duplicate", "reservation", "counter", "boolean", "limit", "extra"]
)
def test_corrupt_or_foreign_state_fails_closed(change):
    with execution_scope(limits()) as budget:
        meter = MeteredGateway(_FixedCost(0))
        meter.complete(req())
        raw = budget.freeze_state()
    if change == "version":
        raw["version"] = "future"
    elif change == "runtime":
        raw["runtime_version"] = "future"
    elif change == "duplicate":
        raw["settled"] *= 2
    elif change == "reservation":
        raw["snapshot"]["reserved_tokens"] = 1
    elif change == "counter":
        raw["snapshot"]["calls"] = 20
    elif change == "boolean":
        raw["snapshot"]["protected_tokens"] = False
    elif change == "limit":
        raw["snapshot"]["limits"]["token_limit"] = True
    else:
        raw["body"] = "PRIVATE"
    with pytest.raises(ValidationError):
        FrozenBudgetState.model_validate(raw)


def test_freeze_requires_actual_parent_and_restored_clock_never_resets_full_timeout():
    standalone = ExecutionBudget(limits())
    with pytest.raises(ValueError, match="original execution"):
        standalone.freeze_state()
    with execution_scope(limits()) as budget:
        state = FrozenBudgetState.model_validate(budget.freeze_state())
    deadline = time.monotonic() + 0.04
    restored = restore_consumed_budget(state, expires_at_monotonic=deadline)
    assert restored.remaining_timeout(100) < 0.05
    with pytest.raises(ValueError, match="deadline"):
        restore_consumed_budget(state, expires_at_monotonic=time.monotonic() + 100)


def test_actual_fee_overage_and_blocked_reason_survive_without_clamping():
    with execution_scope(limits()) as budget:
        with pytest.raises(ExecutionBudgetExceeded, match="cost"):
            MeteredGateway(_FixedCost(0.7)).complete(req())
        state = FrozenBudgetState.model_validate(budget.freeze_state())
    restored = recover(state)
    assert restored.snapshot().accounted_cost_usd == restored.snapshot().known_cost_usd == 0.7
    with pytest.raises(ExecutionBudgetExceeded, match="cost"):
        restored.check()
