"""M2-02 node policy: bounded retries with backoff, timeouts, no retry on business errors."""

from __future__ import annotations

import time

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.harness.contracts import NodeFailure, NodeSpec, run_node

KEY = "0" * 64


def test_success_records_one_ok_attempt():
    value, attempts = run_node(NodeSpec(name="n", timeout_s=1), KEY, lambda: 42, sleep=lambda s: None)
    assert value == 42 and [a.outcome for a in attempts] == ["ok"] and attempts[0].operation_key == KEY


def test_retryable_infrastructure_error_is_retried_with_exponential_backoff():
    calls = {"n": 0}
    slept = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise InfrastructureError(ErrorCode.dependency_unavailable, detail="down", retryable=True)
        return "ok"

    value, attempts = run_node(NodeSpec(name="n", timeout_s=1, backoff_base_s=0.1), KEY, flaky, sleep=slept.append)
    assert value == "ok" and [a.outcome for a in attempts] == ["retry", "retry", "ok"] and slept == [0.1, 0.2]


def test_retry_budget_is_at_most_two_then_failure_with_all_attempts():
    def always_down():
        raise InfrastructureError(ErrorCode.dependency_unavailable, detail="down", retryable=True)

    with pytest.raises(NodeFailure) as exc:
        run_node(NodeSpec(name="n", timeout_s=1), KEY, always_down, sleep=lambda s: None)
    assert [a.outcome for a in exc.value.attempts] == ["retry", "retry", "failed"]
    assert all(a.error_code == "dependency_unavailable" for a in exc.value.attempts)


def test_business_errors_and_unexpected_exceptions_never_retry():
    def bad_request():
        raise BusinessError(ErrorCode.invalid_request, "nope")

    with pytest.raises(NodeFailure) as exc:
        run_node(NodeSpec(name="n", timeout_s=1), KEY, bad_request, sleep=lambda s: None)
    assert [a.outcome for a in exc.value.attempts] == ["failed"]

    def boom():
        raise ValueError("unexpected")

    with pytest.raises(NodeFailure) as exc2:
        run_node(NodeSpec(name="n", timeout_s=1), KEY, boom, sleep=lambda s: None)
    assert exc2.value.attempts[0].error_code == "ValueError"


def test_timeout_does_not_wait_for_the_runaway_body_and_counts_as_retryable():
    def slow():
        time.sleep(0.5)
        return "late"

    started = time.perf_counter()
    with pytest.raises(NodeFailure) as exc:
        run_node(NodeSpec(name="n", timeout_s=0.05, max_retries=1), KEY, slow, sleep=lambda s: None)
    assert time.perf_counter() - started < 0.4
    assert [a.outcome for a in exc.value.attempts] == ["timeout", "failed"]
    assert exc.value.attempts[-1].error_code == "dependency_timeout"
