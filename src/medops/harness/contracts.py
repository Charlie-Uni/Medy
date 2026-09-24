"""Node contracts (M2-02): spec, attempt record and the execution policy every node runs under.

- timeout per node (INV-HAR-04): the body runs in a worker thread; when the deadline passes the node fails
  with `dependency_timeout` and the runaway thread is abandoned (asyncio cancellation propagation arrives
  with the M3 executor; this policy never waits past the deadline);
- retries: only retryable infrastructure errors and timeouts, exponential backoff, at most 2 (baseline 3.2);
- business errors and unexpected exceptions never retry; every attempt is recorded with its operation key;
- degradation is a node decision (baseline 5.3): a degraded retrieval is accepted only if the evidence
  threshold still holds, otherwise the run escalates.
"""

from __future__ import annotations

import contextvars
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from typing import Literal, TypeVar

from pydantic import Field

from medops.core.errors import ErrorCode, InfrastructureError, MedOpsError
from medops.core.telemetry import annotate, span
from medops.domain.common import DomainModel, NonEmptyStr

MAX_RETRIES = 2  # baseline 3.2
T = TypeVar("T")


class NodeSpec(DomainModel):
    name: NonEmptyStr
    timeout_s: float = Field(gt=0, le=120)
    max_retries: int = Field(default=MAX_RETRIES, ge=0, le=MAX_RETRIES)
    backoff_base_s: float = Field(default=0.2, ge=0)
    min_evidence_when_degraded: int = Field(default=1, ge=1)


class NodeAttempt(DomainModel):
    node: NonEmptyStr
    attempt: int = Field(ge=1)
    operation_key: NonEmptyStr
    started_at: datetime
    duration_ms: float = Field(ge=0)
    outcome: Literal["ok", "retry", "failed", "timeout"]
    error_code: str | None = None
    detail: str = ""


class NodeTimeout(InfrastructureError):
    def __init__(self, node: str, timeout_s: float) -> None:
        super().__init__(ErrorCode.dependency_timeout, detail=f"node {node} exceeded {timeout_s}s", retryable=True)


class NodeFailure(Exception):
    """Final failure of a node after its retry budget; carries the attempts for the trace."""

    def __init__(self, node: str, error: BaseException, attempts: list[NodeAttempt]) -> None:
        super().__init__(f"node {node} failed: {type(error).__name__}")
        self.node = node
        self.error = error
        self.attempts = attempts


def run_node(
    spec: NodeSpec,
    operation_key: str,
    body: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] | None = None,
) -> tuple[T, list[NodeAttempt]]:
    now = clock or (lambda: datetime.now(UTC))
    attempts: list[NodeAttempt] = []
    for attempt in range(1, spec.max_retries + 2):
        started = now()
        t0 = time.perf_counter()
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"node-{spec.name}")
        error: BaseException
        outcome: Literal["retry", "failed", "timeout"]
        with span("harness.node", node=spec.name, attempt=attempt, operation_key=operation_key) as current:
            try:
                future = pool.submit(contextvars.copy_context().run, body)  # trace id + OTel context follow the body
                try:
                    result = future.result(timeout=spec.timeout_s)
                except FutureTimeout:
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise NodeTimeout(spec.name, spec.timeout_s) from None
                pool.shutdown(wait=True)
                attempts.append(_attempt(spec, attempt, operation_key, started, t0, "ok", None, ""))
                annotate(current, outcome="ok")
                return result, attempts
            except NodeTimeout as exc:
                error, retryable, outcome = exc, True, "timeout"
            except InfrastructureError as exc:
                pool.shutdown(wait=False, cancel_futures=True)
                error, retryable, outcome = exc, exc.retryable, "retry"
            except MedOpsError as exc:
                pool.shutdown(wait=False, cancel_futures=True)
                error, retryable, outcome = exc, False, "failed"
            except Exception as exc:  # noqa: BLE001 - recorded as a failed attempt and re-raised as NodeFailure below
                pool.shutdown(wait=False, cancel_futures=True)
                error, retryable, outcome = exc, False, "failed"
            code = error.code.value if isinstance(error, MedOpsError) else type(error).__name__
            last = attempt > spec.max_retries or not retryable
            annotate(current, outcome="failed" if last else outcome, error_code=code)
        attempts.append(
            _attempt(spec, attempt, operation_key, started, t0, "failed" if last else outcome, code, str(error)[:200])
        )
        if last:
            raise NodeFailure(spec.name, error, attempts)
        sleep(spec.backoff_base_s * (2 ** (attempt - 1)))
    raise AssertionError("unreachable")


def _attempt(
    spec: NodeSpec,
    attempt: int,
    operation_key: str,
    started: datetime,
    t0: float,
    outcome: Literal["ok", "retry", "failed", "timeout"],
    code: str | None,
    detail: str,
) -> NodeAttempt:
    return NodeAttempt(
        node=spec.name,
        attempt=attempt,
        operation_key=operation_key,
        started_at=started,
        duration_ms=(time.perf_counter() - t0) * 1000,
        outcome=outcome,
        error_code=code,
        detail=detail,
    )
