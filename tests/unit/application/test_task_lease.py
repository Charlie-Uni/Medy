"""Expired ownership must stop an attempt, even before a replacement worker arrives."""

import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from datetime import timedelta
from threading import Event

import pytest

from medops.application.tasks import InMemoryTaskStore, TaskLeaseLost, TaskRunner, TaskService
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.execution_budget import default_limits, execution_scope
from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable
from medops.infrastructure.llm.meter import MeteredGateway
from medops.skills.registry import SkillRegistry
from tests.unit.application.test_tasks import Clock, EchoOut, FakeEnv, registry, req, user
from tests.unit.infrastructure.test_llm_gateway import _FixedCost
from tests.unit.infrastructure.test_llm_gateway import req as model_request


def test_expired_lease_cannot_complete_without_takeover():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    task = TaskService(store=store, clock=clock).create(user(), req(), None)
    store.claim_next("w1", 60, clock())
    clock.now += timedelta(seconds=60)
    assert store.complete(task.task_id, "w1", 1, "a" * 32, {}, clock()) is False


def test_failed_attempt_is_not_recorded_as_completed():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    task = TaskService(store=store, clock=clock).create(user(), req(), None)
    store.claim_next("w1", 60, clock())
    assert store.fail(task.task_id, "w1", 1, "a" * 32, {"code": "forbidden"}, clock())
    assert store.attempts[0]["outcome"] == "failed"


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_lease_is_rejected_before_claim(value):
    clock, reg = Clock(), registry()
    store = InMemoryTaskStore(clock=clock)
    with pytest.raises(ValueError, match="finite and positive"):
        TaskRunner(env=FakeEnv(store, reg, {}), registry=reg, lease_s=value)
    with pytest.raises(ValueError, match="finite and positive"):
        store.claim_next("w1", value, clock())
    assert not store.attempts


def test_lost_report_is_identity_fenced_and_preserves_takeover_timestamp():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    task = TaskService(store=store, clock=clock).create(user(), req(), None)
    store.claim_next("same-worker", 10, clock())
    assert not store.record_lost(task.task_id, "same-worker", 1, "a" * 32, clock())
    clock.now += timedelta(seconds=11)
    store.claim_next("same-worker", 60, clock())
    finished = store.attempts[0]["finished_at"]
    clock.now += timedelta(seconds=1)
    assert not store.record_lost(task.task_id, "other-worker", 1, "a" * 32, clock())
    assert store.record_lost(task.task_id, "same-worker", 1, "a" * 32, clock())
    assert not store.record_lost(task.task_id, "same-worker", 1, "b" * 32, clock())
    assert store.attempts[0]["finished_at"] == finished and store.attempts[0]["trace_id"] == "a" * 32
    assert store.owns_lease(task.task_id, "same-worker", 2, clock())
    assert not store.fail(task.task_id, "same-worker", 1, "a" * 32, {"code": "forbidden"}, clock())


class PaidFakeEnv(FakeEnv):
    def __init__(self, store, reg, principals, gateway):
        super().__init__(store, reg, principals)
        self.gateway = gateway
        self.meters = {}

    def skill_context(self, conn, user, trace_id, historical):
        ctx = super().skill_context(conn, user, trace_id, historical)
        meter = MeteredGateway(self.gateway)
        self.meters[trace_id] = meter
        return replace(ctx, deps=replace(ctx.deps, gateway=meter))


def test_two_workers_old_attempt_cannot_pay_again_or_return_new_workers_result():
    clock, entered, release = Clock(), Event(), Event()
    store = InMemoryTaskStore(clock=clock)
    u = user()
    denied = []
    provider, ledger = _FixedCost(0.00001), InMemorySpendLedger()
    gateway = BudgetedGateway(
        provider, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=10, clock=clock
    )

    def handler(ctx, inp):
        ctx.deps.gateway.complete(model_request())
        if inp.text == "old" and not entered.is_set():
            entered.set()
            assert release.wait(5)
            # Nested child/translation threads inherit the attempt fence and cannot remove it.
            with ThreadPoolExecutor(max_workers=1) as children, call_scope(run_id="child"):
                pending = children.submit(copy_context().run, ctx.deps.gateway.complete, model_request())
                with pytest.raises(TaskLeaseLost):
                    pending.result(timeout=5)
                denied.append(True)
        return EchoOut(status=SkillStatus.completed, text=ctx.trace_id)

    reg = registry(handler)
    env = PaidFakeEnv(store, reg, {u.user_id: u}, gateway)
    task = TaskService(store=store, clock=clock).create(u, req("old"), None)
    a = TaskRunner(env=env, registry=reg, worker_id="w1", clock=clock)
    b = TaskRunner(env=env, registry=reg, worker_id="w2", clock=clock)
    with ThreadPoolExecutor(max_workers=1) as workers:
        old = workers.submit(a.run_once)
        try:
            assert entered.wait(5)
            assert b.run_once() is None
            clock.now += timedelta(seconds=301)
            replacement = b.run_once()
        finally:
            release.set()
        stale = old.result(timeout=5)
    assert replacement.outcome == "completed" and replacement.attempt == 2
    assert stale.outcome == "lost" and stale.attempt == 1 and stale.record is None
    assert stale.trace_id != replacement.trace_id and denied == [True] and provider.calls == 2
    assert store.get(task.task_id).trace_id == replacement.trace_id
    assert store.get(task.task_id).result["output"]["text"] == replacement.trace_id
    assert [(a["outcome"], a["trace_id"]) for a in store.attempts] == [
        ("lost", stale.trace_id),
        ("completed", replacement.trace_id),
    ]
    traces = [env.traces.traces[t] for t in (stale.trace_id, replacement.trace_id)]
    assert [t.outcome for t in traces] == ["escalated", "completed"]
    assert sum(t.cost_usd for t in traces) == pytest.approx(ledger.month_total("2026-09"))
    assert [t.model_calls for t in traces] == [1, 1]
    old_meter = env.meters[stale.trace_id]
    denied_receipt = next(r for r in old_meter.receipts if not r.provider_started)
    assert denied_receipt.accounted_cost_usd == 0 and denied_receipt.call.attempt_id.startswith(
        f"task:{task.task_id}:1/"
    )


def test_loss_during_monthly_reservation_refunds_unstarted_call():
    clock, store = Clock(), InMemoryTaskStore()
    store.clock = clock
    u = user()
    task = TaskService(store=store, clock=clock).create(u, req(), None)
    store.claim_next("w1", 10, clock())

    class DelayedLedger(InMemorySpendLedger):
        def reserve(self, *args, **kwargs):
            reservation = super().reserve(*args, **kwargs)
            clock.now += timedelta(seconds=11)
            store.claim_next("w2", 60, clock())
            return reservation

    ledger, provider = DelayedLedger(), _FixedCost(0.00001)
    gateway = MeteredGateway(
        BudgetedGateway(provider, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=10, clock=clock)
    )

    def guard():
        if not store.owns_lease(task.task_id, "w1", 1, clock()):
            raise TaskLeaseLost()

    with (
        execution_scope(default_limits(timeout_s=1)) as budget,
        call_scope(before_call=guard),
        pytest.raises(TaskLeaseLost),
    ):
        gateway.complete(model_request())
    assert provider.calls == gateway.calls == 0 and gateway.cost_usd == ledger.month_total("2026-09") == 0
    assert budget.snapshot().accounted_tokens == 0 and budget.snapshot().reserved_tokens == 0
    receipt = gateway.receipts[0]
    assert (
        not receipt.provider_started and receipt.cost_basis == "not_started" and receipt.settlement_status == "settled"
    )


def test_context_setup_is_bounded_by_the_lease_and_never_starts_late_model():
    store, u = InMemoryTaskStore(), user()
    provider = _FixedCost(0.00001)

    def handler(ctx, inp):
        ctx.deps.gateway.complete(model_request())
        return EchoOut(status=SkillStatus.completed, text=inp.text)

    reg = registry(handler)

    class SlowEnv(PaidFakeEnv):
        def skill_context(self, *args):
            time.sleep(0.08)
            return super().skill_context(*args)

    env = SlowEnv(store, reg, {u.user_id: u}, provider)
    task = TaskService(store=store).create(u, req(), None)
    execution = TaskRunner(env=env, registry=reg, lease_s=0.06).run_once()
    assert execution.outcome == "lost" and execution.record is None and provider.calls == 0
    assert store.attempts[0]["trace_id"] == execution.trace_id and store.get(task.task_id).result is None


def test_request_timeout_is_shortened_to_the_remaining_task_lease():
    store, u, provider = InMemoryTaskStore(), user(), _FixedCost(0.00001)
    remaining = []

    class Provider(_FixedCost):
        def complete(self, request):
            remaining.append(request.timeout_s)
            return super().complete(request)

    provider = Provider(0.00001)

    def handler(ctx, inp):
        ctx.deps.gateway.complete(model_request())
        return EchoOut(status=SkillStatus.completed, text=inp.text)

    reg = registry(handler)
    env = PaidFakeEnv(store, reg, {u.user_id: u}, provider)
    TaskService(store=store).create(u, req(), None)
    execution = TaskRunner(env=env, registry=reg, lease_s=0.2).run_once()
    assert execution.outcome == "completed" and len(remaining) == 1 and 0 < remaining[0] < 0.18


@pytest.mark.parametrize("flag", ["--lease", "--poll"])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_worker_cli_rejects_invalid_durations_before_runtime_start(flag, value, capsys):
    from medops.worker.serve import main

    with pytest.raises(SystemExit) as exc:
        main([flag, value, "--once"])
    assert exc.value.code == 2 and "finite and positive" in capsys.readouterr().err


@pytest.mark.parametrize("short_limit", ["skill", "profile"])
def test_context_setup_consumes_skill_and_profile_total_time(short_limit):
    store, u, provider = InMemoryTaskStore(), user(), _FixedCost(0.00001)

    def handler(ctx, inp):
        ctx.deps.gateway.complete(model_request())
        return EchoOut(status=SkillStatus.completed, text=inp.text)

    reg = registry(handler)
    if short_limit == "skill":
        reg = SkillRegistry(sleep=lambda _: None)
        original = registry(handler).get("echo_skill", "1.0.0")
        reg.register(replace(original, spec=original.spec.model_copy(update={"timeout_s": 0.04})))

    class SlowEnv(PaidFakeEnv):
        def skill_context(self, *args):
            time.sleep(0.06)
            ctx = super().skill_context(*args)
            if short_limit == "profile":
                ctx = replace(ctx, deps=replace(ctx.deps, execution_limits=default_limits(timeout_s=0.04)))
            return ctx

    env = SlowEnv(store, reg, {u.user_id: u}, provider)
    TaskService(store=store).create(u, req(), None)
    execution = TaskRunner(env=env, registry=reg, lease_s=1).run_once()
    assert execution.outcome == "failed" and execution.record.error["code"] == "dependency_timeout"
    assert provider.calls == 0 and env.traces.traces[execution.trace_id].model_calls == 0
