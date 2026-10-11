"""Asynchronous skill tasks (M3-02/04): creation with scoped idempotency, visibility, retry, and the worker step.

PostgreSQL (or the in-memory store in tests) is the source of truth. A task runs a registered Skill under the
identity it was created with, re-resolved at execution time from the principal directory (scopes may have been
revoked in between: default deny). Claiming is an atomic status transition with a lease; a lost lease makes
the task claimable again and records the attempt as `lost`. Results and errors are the public contract shapes.
"""

from __future__ import annotations

import math
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from medops.api.contracts import (
    IDEMPOTENCY_KEY_HEADER,
    TaskCreateRequest,
    TaskResponse,
    TaskResult,
    TaskResultStatus,
    TaskStatus,
)
from medops.application.audit import TraceRecord, TraceStore, record_or_fail_closed
from medops.core.canonical import canonical_hash
from medops.core.deadline import check_deadline, deadline_scope
from medops.core.errors import BusinessError, ErrorCode, ErrorResponse, InfrastructureError, MedOpsError
from medops.core.telemetry import ATTR_TASK, ATTR_TRACE, annotate, span
from medops.core.tracing import bind_trace_id, new_trace_id
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.query import resolve_query_context
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.meter import MeteredGateway
from medops.skills.registry import SkillContext, SkillRegistry, SkillRun

TASKS_ROUTE = "POST /v1/tasks"
DEFAULT_LEASE_S = 300.0
DEFAULT_MAX_ATTEMPTS = 3


def validate_lease(lease_s: float) -> None:
    if not math.isfinite(lease_s) or lease_s <= 0:
        raise ValueError("lease must be finite and positive")


class TaskLeaseLost(InfrastructureError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.dependency_unavailable, detail="task attempt lost its lease", retryable=False)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    principal: str  # pseudonym (UserContext.user_id)
    dept: Dept
    skill_name: str
    skill_version: str
    input: Mapping[str, Any]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    attempts: int = 0
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    lease_owner: str | None = None
    lease_until: datetime | None = None
    trace_id: str | None = None
    result: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None
    historical: Mapping[str, Any] | None = None


class TaskStore(Protocol):
    def find_idempotent(self, principal: str, route: str, key: str) -> tuple[str, str] | None:
        """(request_hash, task_id) for a live key, None when absent or expired."""
        ...

    def create(self, record: TaskRecord, idempotency: tuple[str, str, datetime] | None) -> None:
        """Insert the task and, when given, the (route, key, expires_at) idempotency row in the same transaction."""
        ...

    def get(self, task_id: str) -> TaskRecord | None: ...

    def requeue(self, task_id: str, now: datetime) -> TaskRecord | None: ...

    def claim_next(self, worker: str, lease_s: float, now: datetime | None = None) -> TaskRecord | None: ...

    def owns_lease(self, task_id: str, worker: str, attempt: int, now: datetime | None = None) -> bool: ...

    def record_lost(
        self, task_id: str, worker: str, attempt: int, trace_id: str, now: datetime | None = None
    ) -> bool: ...

    def complete(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str,
        result: Mapping[str, Any],
        now: datetime | None = None,
    ) -> bool: ...

    def fail(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str | None,
        error: Mapping[str, Any],
        now: datetime | None = None,
    ) -> bool: ...


# ------------------------------------------------------------------------------------ service (API side)


@dataclass
class TaskService:
    store: TaskStore
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    idempotency_ttl_s: int = 7 * 24 * 3600
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def create(self, user: UserContext, request: TaskCreateRequest, idempotency_key: str | None) -> TaskRecord:
        resolve_query_context(request.historical.model_dump() if request.historical else None)
        payload_hash = canonical_hash(request.model_dump(mode="json"))
        if idempotency_key is not None:
            key = idempotency_key.strip()
            if not key or len(key) > 255:
                raise BusinessError(ErrorCode.invalid_request, f"{IDEMPOTENCY_KEY_HEADER} must be 1-255 characters")
            existing = self.store.find_idempotent(user.user_id, TASKS_ROUTE, key)
            if existing is not None:
                stored_hash, task_id = existing
                if stored_hash != payload_hash:
                    raise BusinessError(
                        ErrorCode.idempotency_payload_mismatch, "same Idempotency-Key with a different payload"
                    )
                original = self.store.get(task_id)
                if original is None:
                    raise BusinessError(ErrorCode.not_found, "task not found")
                return original
        now = self.clock()
        record = TaskRecord(
            task_id=str(uuid.uuid4()),
            principal=user.user_id,
            dept=user.dept,
            skill_name=request.skill_name,
            skill_version=request.skill_version,
            input=dict(request.input),
            status=TaskStatus.queued,
            created_at=now,
            updated_at=now,
            max_attempts=self.max_attempts,
            historical=request.historical.model_dump(mode="json") if request.historical is not None else None,
        )
        idem = None
        if idempotency_key is not None:
            idem = (TASKS_ROUTE, idempotency_key.strip(), now + timedelta(seconds=self.idempotency_ttl_s))
        try:
            self.store.create(record, idem)
        except IdempotencyRace:
            # a concurrent request with the same key won the insert: return its task (contract: never 409)
            existing = self.store.find_idempotent(user.user_id, TASKS_ROUTE, idempotency_key.strip())  # type: ignore[union-attr]
            if existing is None or existing[0] != payload_hash:
                raise BusinessError(
                    ErrorCode.idempotency_payload_mismatch, "same Idempotency-Key with a different payload"
                ) from None
            original = self.store.get(existing[1])
            assert original is not None
            return original
        return record

    def get(self, user: UserContext, task_id: str) -> TaskRecord:
        record = self.store.get(task_id)
        if record is None or record.principal != user.user_id:
            raise BusinessError(ErrorCode.not_found, "task not found")  # visibility: the creating principal only
        return record

    def retry(self, user: UserContext, task_id: str) -> TaskRecord:
        record = self.get(user, task_id)
        retryable = bool((record.error or {}).get("retryable"))
        if record.status is not TaskStatus.failed or not retryable:
            raise BusinessError(ErrorCode.task_not_retryable, "only failed tasks with a retryable error can be retried")
        requeued = self.store.requeue(task_id, self.clock())
        if requeued is None:
            raise BusinessError(ErrorCode.task_not_retryable, "task changed state concurrently")
        return requeued


class IdempotencyRace(Exception):
    """Raised by a store when another transaction inserted the same idempotency key first."""


def to_response(record: TaskRecord) -> TaskResponse:
    return TaskResponse(
        task_id=record.task_id,
        status=record.status,
        trace_id=record.trace_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        result=TaskResult.model_validate(record.result) if record.result is not None else None,
        error=ErrorResponse.model_validate(record.error) if record.error is not None else None,
    )


# ------------------------------------------------------------------------------------ worker step


class WorkerEnvironment(Protocol):
    """What one worker step needs from the process: a transaction, the directory, and a Skill context."""

    def connection(self) -> Any: ...

    def resolve_user(self, conn: Any, principal: str) -> UserContext | None: ...

    def bind_identity(self, conn: Any, user: UserContext) -> None: ...

    def task_store(self, conn: Any) -> TaskStore: ...

    def trace_store(self, conn: Any) -> TraceStore: ...

    def skill_context(
        self, conn: Any, user: UserContext, trace_id: str, historical: Mapping[str, Any] | None
    ) -> SkillContext: ...


@dataclass(frozen=True)
class TaskExecution:
    """This worker's report, distinct from the task currently visible through the API."""

    task_id: str
    attempt: int
    trace_id: str
    outcome: Literal["completed", "failed", "lost"]
    record: TaskRecord | None = None


@dataclass
class TaskRunner:
    env: WorkerEnvironment
    registry: SkillRegistry
    worker_id: str = field(default_factory=lambda: f"worker-{uuid.uuid4().hex[:8]}")
    lease_s: float = DEFAULT_LEASE_S
    # Production uses the task store's database clock; explicit clocks are for deterministic tests.
    clock: Callable[[], datetime] | None = None

    def __post_init__(self) -> None:
        validate_lease(self.lease_s)

    def _now(self) -> datetime | None:
        return self.clock() if self.clock else None

    def run_once(self) -> TaskExecution | None:
        """Claim one task and report only this attempt; None means the queue was idle."""
        claim_started = time.monotonic()
        with self.env.connection() as conn:
            claimed = self.env.task_store(conn).claim_next(self.worker_id, self.lease_s, self._now())
        if claimed is None:
            return None
        # Start before the claim transaction, so connection/lock/commit delays cannot extend the lease.
        reserve_s = min(5.0, self.lease_s * 0.1)
        body_until = claim_started + self.lease_s - reserve_s
        try:
            skill_timeout_s = self.registry.get(claimed.skill_name, claimed.skill_version).spec.timeout_s
        except BusinessError:
            pass  # unknown Skills still go through the identity-first error path below
        else:
            body_until = min(body_until, claim_started + skill_timeout_s)
        trace_id = new_trace_id()
        with (
            bind_trace_id(trace_id),
            call_scope(
                run_id=trace_id,
                attempt_id=f"task:{claimed.task_id}:{claimed.attempts}",
                before_call=lambda: self._check_lease(claimed),
            ),
            span(
                "worker.task",
                **{
                    ATTR_TASK: claimed.task_id,
                    ATTR_TRACE: trace_id,
                    "skill": claimed.skill_name,
                    "attempt": claimed.attempts,
                },
            ) as current,
        ):
            execution = self._execute(claimed, trace_id, body_until, claim_started)
            annotate(current, status=execution.outcome, lease_lost=execution.outcome == "lost")
        return execution

    def _check_lease(self, claimed: TaskRecord) -> None:
        # Never use the long business transaction's snapshot or share its connection with a child thread.
        with self.env.connection() as conn:
            owns = self.env.task_store(DeadlineConnection(conn)).owns_lease(
                claimed.task_id, self.worker_id, claimed.attempts, self._now()
            )
        check_deadline()
        if not owns:
            raise TaskLeaseLost()

    @staticmethod
    def _error(exc: Exception, trace_id: str) -> dict[str, Any]:
        if isinstance(exc, MedOpsError):
            return ErrorResponse(
                code=exc.code, message=exc.message, trace_id=trace_id, retryable=exc.retryable
            ).model_dump(mode="json")
        return ErrorResponse(
            code=ErrorCode.internal_error, message="服务暂时不可用，请稍后重试", trace_id=trace_id, retryable=False
        ).model_dump(mode="json")

    def _execute(self, claimed: TaskRecord, trace_id: str, body_until: float, claim_started: float) -> TaskExecution:
        ctx: SkillContext | None = None
        run: SkillRun | None = None
        started = time.perf_counter()
        try:
            with self.env.connection() as conn:
                with deadline_scope(body_until - time.monotonic()):
                    check_deadline()
                    self._check_lease(claimed)
                    guarded = DeadlineConnection(conn)
                    user = self.env.resolve_user(guarded, claimed.principal)
                    if user is None or user.dept is not claimed.dept:
                        raise BusinessError(
                            ErrorCode.forbidden, "task principal is no longer provisioned for this department"
                        )
                    self.env.bind_identity(guarded, user)
                    ctx = self.env.skill_context(guarded, user, trace_id, claimed.historical)
                    if not isinstance(ctx.deps.gateway, MeteredGateway):
                        ctx = replace(ctx, deps=replace(ctx.deps, gateway=MeteredGateway(ctx.deps.gateway)))
                    profile_until = body_until
                    if ctx.deps.execution_limits is not None:
                        profile_until = min(profile_until, claim_started + ctx.deps.execution_limits.timeout_s)
                    with deadline_scope(profile_until - time.monotonic()):
                        run = self.registry.execute(
                            claimed.skill_name, claimed.skill_version, claimed.input, context=ctx
                        )
                        # Infrastructure escalation does not bypass the task's time/ownership fence.
                        self._check_lease(claimed)
                return self._report(conn, claimed, trace_id, ctx, run, None, started)
        except Exception as exc:  # noqa: BLE001 - crashes fail closed; cancellation still propagates
            # The business transaction has rolled back. Report with a fresh, usable connection.
            with self.env.connection() as conn:
                return self._report(conn, claimed, trace_id, ctx, run, self._error(exc, trace_id), started)

    def _report(
        self,
        conn: Any,
        claimed: TaskRecord,
        trace_id: str,
        ctx: SkillContext | None,
        run: SkillRun | None,
        error: Mapping[str, Any] | None,
        started: float,
    ) -> TaskExecution:
        store = self.env.task_store(conn)
        if error is None:
            assert run is not None and ctx is not None
            result = TaskResult(
                skill=run.spec.version_tag,
                status=TaskResultStatus(run.output.status.value),
                reason_codes=run.output.reason_codes,
                output=run.output.model_dump(mode="json", exclude={"status", "reason_codes", "detail"}),
                versions=ctx.versions,
            ).model_dump(mode="json")
            accepted = store.complete(claimed.task_id, self.worker_id, claimed.attempts, trace_id, result, self._now())
        else:
            accepted = store.fail(claimed.task_id, self.worker_id, claimed.attempts, trace_id, error, self._now())
        outcome: Literal["completed", "failed", "lost"] = (
            ("completed" if error is None else "failed") if accepted else "lost"
        )
        if not accepted and not store.record_lost(
            claimed.task_id, self.worker_id, claimed.attempts, trace_id, self._now()
        ):
            raise InfrastructureError(
                ErrorCode.audit_unavailable, detail="task attempt loss could not be recorded", retryable=False
            )
        if ctx is not None:
            meter = ctx.deps.gateway
            assert isinstance(meter, MeteredGateway)
            trace_outcome = "escalated"
            reason_codes: tuple[str, ...] = ("system_failure",)
            if outcome == "completed":
                assert run is not None
                trace_outcome = run.output.status.value
                reason_codes = tuple(c.value for c in run.output.reason_codes)
            record_or_fail_closed(
                self.env.trace_store(conn),
                TraceRecord(
                    trace_id=trace_id,
                    run_id=trace_id,
                    kind="task",
                    principal=claimed.principal,
                    dept=claimed.dept,
                    query=f"{claimed.skill_name}@{claimed.skill_version}",
                    outcome=trace_outcome,
                    reason_codes=reason_codes,
                    versions=ctx.versions.model_dump(mode="json"),
                    evidence_chunk_ids=(),
                    cited_chunk_ids=(),
                    flagged_chunk_ids=(),
                    model_calls=meter.calls,
                    tokens=meter.tokens,
                    cost_usd=meter.cost_usd,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    spans=run.attempts if run else (),
                    task_id=claimed.task_id,
                    query_context=ctx.query_context,
                ),
                None,
            )
        # A lost attempt must not return the replacement worker's result as its own.
        final = store.get(claimed.task_id) if accepted else None
        return TaskExecution(claimed.task_id, claimed.attempts, trace_id, outcome, final)


# ------------------------------------------------------------------------------------ in-memory store (tests)


@dataclass
class InMemoryTaskStore:
    tasks: dict[str, TaskRecord] = field(default_factory=dict)
    idempotency: dict[tuple[str, str, str], tuple[str, str, datetime]] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    _lock: Any = field(default_factory=threading.RLock, repr=False)

    def find_idempotent(self, principal: str, route: str, key: str) -> tuple[str, str] | None:
        with self._lock:
            row = self.idempotency.get((principal, route, key))
            if row is None or row[2] <= self.clock():
                return None
            return row[0], row[1]

    def create(self, record: TaskRecord, idempotency: tuple[str, str, datetime] | None) -> None:
        with self._lock:
            if idempotency is not None:
                route, key, expires = idempotency
                slot = (record.principal, route, key)
                if slot in self.idempotency and self.idempotency[slot][2] > self.clock():
                    raise IdempotencyRace()
                from medops.api.contracts import HistoricalRequest  # local import to keep the module light

                request = TaskCreateRequest(
                    skill_name=record.skill_name,
                    skill_version=record.skill_version,
                    input=dict(record.input),
                    historical=HistoricalRequest.model_validate(record.historical) if record.historical else None,
                )
                self.idempotency[slot] = (canonical_hash(request.model_dump(mode="json")), record.task_id, expires)
            self.tasks[record.task_id] = record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self.tasks.get(task_id)

    def requeue(self, task_id: str, now: datetime) -> TaskRecord | None:
        with self._lock:
            record = self.tasks.get(task_id)
            if record is None or record.status is not TaskStatus.failed:
                return None
            record = replace(
                record, status=TaskStatus.queued, error=None, lease_owner=None, lease_until=None, updated_at=now
            )
            self.tasks[task_id] = record
            return record

    def claim_next(self, worker: str, lease_s: float, now: datetime | None = None) -> TaskRecord | None:
        with self._lock:
            validate_lease(lease_s)
            now = now or self.clock()
            for record in sorted(self.tasks.values(), key=lambda r: r.created_at):
                expired = (
                    record.status is TaskStatus.running and record.lease_until is not None and record.lease_until <= now
                )
                if record.status is TaskStatus.queued or expired:
                    if expired:
                        for a in self.attempts:  # the running attempt of the dead worker is recorded as lost
                            if (
                                a["task_id"] == record.task_id
                                and a["attempt"] == record.attempts
                                and a["outcome"] == "running"
                            ):
                                a["outcome"] = "lost"
                                a["finished_at"] = now
                    if record.attempts >= record.max_attempts:
                        failed = replace(
                            record,
                            status=TaskStatus.failed,
                            lease_owner=None,
                            lease_until=None,
                            updated_at=now,
                            error={
                                "code": "dependency_unavailable",
                                "message": "服务暂时不可用，请稍后重试",
                                "trace_id": None,
                                "retryable": False,
                            },
                        )
                        self.tasks[record.task_id] = failed
                        continue
                    claimed = replace(
                        record,
                        status=TaskStatus.running,
                        attempts=record.attempts + 1,
                        lease_owner=worker,
                        lease_until=now + timedelta(seconds=lease_s),
                        updated_at=now,
                    )
                    self.tasks[record.task_id] = claimed
                    self.attempts.append(
                        {
                            "task_id": record.task_id,
                            "attempt": claimed.attempts,
                            "outcome": "running",
                            "worker": worker,
                            "started_at": now,
                        }
                    )
                    return claimed
            return None

    def owns_lease(self, task_id: str, worker: str, attempt: int, now: datetime | None = None) -> bool:
        with self._lock:
            record = self.tasks.get(task_id)
            return bool(
                record is not None
                and record.status is TaskStatus.running
                and record.lease_owner == worker
                and record.attempts == attempt
                and record.lease_until is not None
                and record.lease_until > (now or self.clock())
            )

    def record_lost(self, task_id: str, worker: str, attempt: int, trace_id: str, now: datetime | None = None) -> bool:
        with self._lock:
            now = now or self.clock()
            if self.owns_lease(task_id, worker, attempt, now):
                return False
            for row in self.attempts:
                if (
                    row["task_id"] == task_id
                    and row["attempt"] == attempt
                    and row["worker"] == worker
                    and row["outcome"] in {"running", "lost"}
                ):
                    if row.get("trace_id") not in {None, trace_id}:
                        return False
                    row.update(outcome="lost", trace_id=trace_id, error_code="dependency_unavailable")
                    row.setdefault("finished_at", now)
                    return True
            return False

    def _finish(
        self, task_id: str, worker: str, attempt: int, trace_id: str | None, now: datetime | None, **fields: Any
    ) -> bool:
        with self._lock:
            now = now or self.clock()
            if not self.owns_lease(task_id, worker, attempt, now):
                return False
            record = self.tasks[task_id]
            self.tasks[task_id] = replace(
                record, lease_owner=None, lease_until=None, trace_id=trace_id, updated_at=now, **fields
            )
            for row in self.attempts:
                if (
                    row["task_id"] == task_id
                    and row["attempt"] == attempt
                    and row["worker"] == worker
                    and row["outcome"] == "running"
                ):
                    row.update(
                        outcome=fields["status"].value,
                        trace_id=trace_id,
                        finished_at=now,
                        error_code=(fields.get("error") or {}).get("code"),
                    )
            return True

    def complete(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str,
        result: Mapping[str, Any],
        now: datetime | None = None,
    ) -> bool:
        with self._lock:
            return self._finish(
                task_id, worker, attempt, trace_id, now, status=TaskStatus.completed, result=dict(result), error=None
            )

    def fail(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str | None,
        error: Mapping[str, Any],
        now: datetime | None = None,
    ) -> bool:
        with self._lock:
            return self._finish(
                task_id, worker, attempt, trace_id, now, status=TaskStatus.failed, error=dict(error), result=None
            )
