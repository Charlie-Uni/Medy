"""Task use cases (M3-02/04) on the in-memory store: scoped idempotency (same key + payload -> original task,
different payload -> 422), creator-only visibility, retry only for failed+retryable, and the worker step with
claim/lease/attempt semantics, re-resolved identity and fail-closed error persistence."""

from __future__ import annotations

from datetime import timedelta

import pytest

from medops.application.contracts import TaskStatus
from medops.application.tasks import InMemoryTaskStore, TaskRunner, TaskService, to_response
from medops.core.errors import BusinessError, ErrorCode
from tests.support.tasks import T0, Clock, FakeEnv, registry, req, user

# ------------------------------------------------------------------------------------ service


def test_create_is_idempotent_per_principal_route_and_key():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    svc = TaskService(store=store, clock=clock, idempotency_ttl_s=3600)
    first = svc.create(user(), req(), "k1")
    again = svc.create(user(), req(), "k1")
    assert again.task_id == first.task_id and len(store.tasks) == 1
    with pytest.raises(BusinessError) as exc:
        svc.create(user(), req("other"), "k1")
    assert exc.value.code is ErrorCode.idempotency_payload_mismatch
    other_principal = svc.create(user(uid="q" * 32), req(), "k1")
    assert other_principal.task_id != first.task_id  # scope includes the principal
    assert svc.create(user(), req(), None).task_id != first.task_id  # no key, no dedup
    clock.now = T0 + timedelta(hours=2)
    assert svc.create(user(), req(), "k1").task_id != first.task_id  # expired key


def test_visibility_and_retry_rules():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    svc = TaskService(store=store, clock=clock)
    rec = svc.create(user(), req(), None)
    with pytest.raises(BusinessError) as exc:
        svc.get(user(uid="q" * 32), rec.task_id)
    assert exc.value.code is ErrorCode.not_found
    with pytest.raises(BusinessError) as exc2:
        svc.retry(user(), rec.task_id)  # queued, not failed
    assert exc2.value.code is ErrorCode.task_not_retryable
    claimed = store.claim_next("w1", 60, clock())
    store.fail(
        claimed.task_id,
        "w1",
        1,
        "a" * 32,
        {"code": "dependency_timeout", "message": "x", "trace_id": "a" * 32, "retryable": True},
        clock(),
    )
    requeued = svc.retry(user(), rec.task_id)
    assert requeued.status is TaskStatus.queued and requeued.error is None
    claimed2 = store.claim_next("w1", 60, clock())
    store.fail(
        claimed2.task_id,
        "w1",
        2,
        None,
        {"code": "internal_error", "message": "x", "trace_id": None, "retryable": False},
        clock(),
    )
    with pytest.raises(BusinessError) as exc3:
        svc.retry(user(), rec.task_id)  # not retryable
    assert exc3.value.code is ErrorCode.task_not_retryable
    resp = to_response(store.get(rec.task_id))
    assert resp.status is TaskStatus.failed and resp.error is not None and resp.error.retryable is False


# ------------------------------------------------------------------------------------ worker


def test_worker_runs_the_skill_under_the_stored_identity_and_persists_the_result():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    reg = registry()
    u = user()
    TaskService(store=store, clock=clock).create(u, req("hello"), None)
    runner = TaskRunner(env=FakeEnv(store, reg, {u.user_id: u}), registry=reg, worker_id="w1", clock=clock)
    execution = runner.run_once()
    assert execution is not None and execution.outcome == "completed" and execution.attempt == 1
    done = execution.record
    assert done is not None and done.status is TaskStatus.completed and done.trace_id
    assert (
        done.result["skill"] == "echo_skill@1.0.0"
        and done.result["output"]["text"] == "HELLO"
        and done.result["status"] == "completed"
    )
    assert "echo_skill@1.0.0" in done.result["versions"]["skill_version_set"]
    assert [a["outcome"] for a in store.attempts] == ["completed"]
    trace = runner.env.traces.traces[done.trace_id]
    assert (
        trace.kind == "task"
        and trace.task_id == done.task_id
        and trace.outcome == "completed"
        and [s.node for s in trace.spans] == ["skill:echo_skill"]
    )
    assert runner.run_once() is None  # nothing left


def test_worker_fails_closed_when_the_principal_is_gone_or_the_skill_errors():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    reg = registry()
    u = user()
    svc = TaskService(store=store, clock=clock)
    gone = svc.create(u, req(), None)
    execution = TaskRunner(env=FakeEnv(store, reg, {}), registry=reg, worker_id="w1", clock=clock).run_once()
    assert execution.outcome == "failed"
    done = execution.record
    assert done.task_id == gone.task_id and done.status is TaskStatus.failed and done.error["code"] == "forbidden"

    def boom(ctx, inp):
        raise RuntimeError("kaboom")

    reg2 = registry(handler=boom)
    crash = svc.create(u, req(), None)
    execution2 = TaskRunner(
        env=FakeEnv(store, reg2, {u.user_id: u}), registry=reg2, worker_id="w1", clock=clock
    ).run_once()
    assert execution2.outcome == "completed"
    done2 = execution2.record
    # the Registry turns a crash inside the handler into an escalated skill output (system_failure): the task
    # itself completed, the result says the skill did not; nothing internal leaks
    assert done2.task_id == crash.task_id and done2.status is TaskStatus.completed
    assert done2.result["status"] == "escalated" and done2.result["reason_codes"] == ["system_failure"]
    assert "kaboom" not in str(done2.result)


def test_lost_lease_is_reclaimed_and_bounded_by_max_attempts():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    u = user()
    TaskService(store=store, clock=clock, max_attempts=2).create(u, req(), None)
    first = store.claim_next("w1", 60, clock())
    assert first.attempts == 1 and store.claim_next("w2", 60, clock()) is None  # leased
    clock.now = T0 + timedelta(seconds=61)
    second = store.claim_next("w2", 60, clock())
    assert second is not None and second.attempts == 2 and second.lease_owner == "w2"
    assert [a["outcome"] for a in store.attempts] == ["lost", "running"]
    assert (
        store.complete(first.task_id, "w1", 1, "a" * 32, {}, clock()) is False
    )  # w1 lost the lease: its late report is ignored
    clock.now = T0 + timedelta(seconds=130)
    assert store.claim_next("w3", 60, clock()) is None  # attempts exhausted -> failed
    assert store.get(first.task_id).status is TaskStatus.failed
