"""Asynchronous skill tasks (M3-02/04): creation with scoped idempotency, visibility, retry, and the worker step.

PostgreSQL (or the in-memory store in tests) is the source of truth. A task runs a registered Skill under the
identity it was created with, re-resolved at execution time from the principal directory (scopes may have been
revoked in between: default deny). Claiming is an atomic status transition with a lease; a lost lease makes
the task claimable again and records the attempt as `lost`. Results and errors are the public contract shapes.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

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
from medops.core.errors import BusinessError, ErrorCode, ErrorResponse, MedOpsError
from medops.core.telemetry import ATTR_TASK, ATTR_TRACE, annotate, span
from medops.core.tracing import bind_trace_id, new_trace_id
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.infrastructure.llm.meter import MeteredGateway
from medops.skills.registry import SkillContext, SkillRegistry

TASKS_ROUTE = "POST /v1/tasks"
DEFAULT_LEASE_S = 300.0
DEFAULT_MAX_ATTEMPTS = 3


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

    def claim_next(self, worker: str, lease_s: float, now: datetime) -> TaskRecord | None: ...

    def complete(
        self, task_id: str, worker: str, attempt: int, trace_id: str, result: Mapping[str, Any], now: datetime
    ) -> bool: ...

    def fail(
        self, task_id: str, worker: str, attempt: int, trace_id: str | None, error: Mapping[str, Any], now: datetime
    ) -> bool: ...


# ------------------------------------------------------------------------------------ service (API side)


@dataclass
class TaskService:
    store: TaskStore
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    idempotency_ttl_s: int = 7 * 24 * 3600
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def create(self, user: UserContext, request: TaskCreateRequest, idempotency_key: str | None) -> TaskRecord:
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


@dataclass
class TaskRunner:
    env: WorkerEnvironment
    registry: SkillRegistry
    worker_id: str = field(default_factory=lambda: f"worker-{uuid.uuid4().hex[:8]}")
    lease_s: float = DEFAULT_LEASE_S
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def run_once(self) -> TaskRecord | None:
        """Claim one task, execute it, persist the outcome. Returns the claimed task or None when idle."""
        with self.env.connection() as conn:
            claimed = self.env.task_store(conn).claim_next(self.worker_id, self.lease_s, self.clock())
        if claimed is None:
            return None
        trace_id = new_trace_id()
        attempt = claimed.attempts
        with (
            bind_trace_id(trace_id),
            span(
                "worker.task",
                **{ATTR_TASK: claimed.task_id, ATTR_TRACE: trace_id, "skill": claimed.skill_name, "attempt": attempt},
            ) as current,
        ):
            record = self._execute(claimed, trace_id, attempt)
            annotate(current, status=record.status.value if record else "unknown")
        return record

    def _execute(self, claimed: TaskRecord, trace_id: str, attempt: int) -> TaskRecord | None:
        try:
            with self.env.connection() as conn:
                user = self.env.resolve_user(conn, claimed.principal)
                if user is None or user.dept is not claimed.dept:
                    raise BusinessError(
                        ErrorCode.forbidden, "task principal is no longer provisioned for this department"
                    )
                self.env.bind_identity(conn, user)
                ctx = self.env.skill_context(conn, user, trace_id, claimed.historical)
                started = time.perf_counter()
                run = self.registry.execute(claimed.skill_name, claimed.skill_version, claimed.input, context=ctx)
                gateway = ctx.deps.gateway
                meter = gateway if isinstance(gateway, MeteredGateway) else None
                record_or_fail_closed(
                    self.env.trace_store(conn),
                    TraceRecord(
                        trace_id=trace_id,
                        run_id=trace_id,
                        kind="task",
                        principal=claimed.principal,
                        dept=claimed.dept,
                        query=f"{claimed.skill_name}@{claimed.skill_version}",
                        outcome=run.output.status.value,
                        reason_codes=tuple(c.value for c in run.output.reason_codes),
                        versions=ctx.versions.model_dump(mode="json"),
                        evidence_chunk_ids=(),
                        cited_chunk_ids=(),
                        flagged_chunk_ids=(),
                        model_calls=meter.calls if meter else 0,
                        tokens=meter.tokens if meter else 0,
                        cost_usd=meter.cost_usd if meter else 0.0,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        spans=run.attempts,
                        task_id=claimed.task_id,
                    ),
                    None,
                )
                result = TaskResult(
                    skill=run.spec.version_tag,
                    status=TaskResultStatus(run.output.status.value),
                    reason_codes=run.output.reason_codes,
                    output=run.output.model_dump(mode="json", exclude={"status", "reason_codes", "detail"}),
                    versions=ctx.versions,
                ).model_dump(mode="json")
                self.env.task_store(conn).complete(
                    claimed.task_id, self.worker_id, attempt, trace_id, result, self.clock()
                )
        except MedOpsError as exc:
            error = ErrorResponse(
                code=exc.code, message=exc.message, trace_id=trace_id, retryable=exc.retryable
            ).model_dump(mode="json")
            with self.env.connection() as conn:
                self.env.task_store(conn).fail(claimed.task_id, self.worker_id, attempt, trace_id, error, self.clock())
        except Exception:  # noqa: BLE001 - a crash inside the skill is a failed attempt, never a silent loss
            error = ErrorResponse(
                code=ErrorCode.internal_error, message="服务暂时不可用，请稍后重试", trace_id=trace_id, retryable=False
            ).model_dump(mode="json")
            with self.env.connection() as conn:
                self.env.task_store(conn).fail(claimed.task_id, self.worker_id, attempt, trace_id, error, self.clock())
        with self.env.connection() as conn:
            final = self.env.task_store(conn).get(claimed.task_id)
        return final or replace(claimed, trace_id=trace_id)


# ------------------------------------------------------------------------------------ in-memory store (tests)


@dataclass
class InMemoryTaskStore:
    tasks: dict[str, TaskRecord] = field(default_factory=dict)
    idempotency: dict[tuple[str, str, str], tuple[str, str, datetime]] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def find_idempotent(self, principal: str, route: str, key: str) -> tuple[str, str] | None:
        row = self.idempotency.get((principal, route, key))
        if row is None or row[2] <= self.clock():
            return None
        return row[0], row[1]

    def create(self, record: TaskRecord, idempotency: tuple[str, str, datetime] | None) -> None:
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
        return self.tasks.get(task_id)

    def requeue(self, task_id: str, now: datetime) -> TaskRecord | None:
        record = self.tasks.get(task_id)
        if record is None or record.status is not TaskStatus.failed:
            return None
        record = replace(
            record, status=TaskStatus.queued, error=None, lease_owner=None, lease_until=None, updated_at=now
        )
        self.tasks[task_id] = record
        return record

    def claim_next(self, worker: str, lease_s: float, now: datetime) -> TaskRecord | None:
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
                    {"task_id": record.task_id, "attempt": claimed.attempts, "outcome": "running", "worker": worker}
                )
                return claimed
        return None

    def _finish(
        self, task_id: str, worker: str, attempt: int, trace_id: str | None, now: datetime, **fields: Any
    ) -> bool:
        record = self.tasks.get(task_id)
        if (
            record is None
            or record.status is not TaskStatus.running
            or record.lease_owner != worker
            or record.attempts != attempt
        ):
            return False  # the lease was lost: another worker owns the task now
        self.tasks[task_id] = replace(
            record, lease_owner=None, lease_until=None, trace_id=trace_id, updated_at=now, **fields
        )
        for a in self.attempts:
            if a["task_id"] == task_id and a["attempt"] == attempt and a["outcome"] == "running":
                a["outcome"] = "completed" if "result" in fields else "failed"
        return True

    def complete(
        self, task_id: str, worker: str, attempt: int, trace_id: str, result: Mapping[str, Any], now: datetime
    ) -> bool:
        return self._finish(
            task_id, worker, attempt, trace_id, now, status=TaskStatus.completed, result=dict(result), error=None
        )

    def fail(
        self, task_id: str, worker: str, attempt: int, trace_id: str | None, error: Mapping[str, Any], now: datetime
    ) -> bool:
        return self._finish(
            task_id, worker, attempt, trace_id, now, status=TaskStatus.failed, error=dict(error), result=None
        )
