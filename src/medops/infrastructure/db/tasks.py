"""PostgreSQL task store (migration 0010) for `medops.application.tasks`: atomic claims with `for update skip
locked`, lease expiry, attempt rows, and the idempotency table written in the caller's transaction."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from medops.api.contracts import TaskStatus
from medops.application.tasks import IdempotencyRace, TaskRecord, validate_lease
from medops.core.canonical import canonical_hash
from medops.domain.common import Dept

_COLUMNS = (
    "task_id::text, principal, dept::text, skill_name, skill_version, input, historical, status, attempts, max_attempts, "
    "lease_owner, lease_until, trace_id, result, error, created_at, updated_at"
)


def _record(row: tuple[Any, ...]) -> TaskRecord:
    (
        tid,
        principal,
        dept,
        name,
        version,
        inp,
        hist,
        status,
        attempts,
        max_attempts,
        owner,
        until,
        trace,
        result,
        error,
        created,
        updated,
    ) = row
    return TaskRecord(
        task_id=tid,
        principal=principal,
        dept=Dept(dept),
        skill_name=name,
        skill_version=version,
        input=inp,
        historical=hist,
        status=TaskStatus(status),
        attempts=attempts,
        max_attempts=max_attempts,
        lease_owner=owner,
        lease_until=until,
        trace_id=trace,
        result=result,
        error=error,
        created_at=created,
        updated_at=updated,
    )


class PgTaskStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def find_idempotent(self, principal: str, route: str, key: str) -> tuple[str, str] | None:
        row = self._conn.execute(
            "select request_hash, task_id::text from idempotency_keys where principal = %s and route = %s and key = %s and expires_at > now()",
            (principal, route, key),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def create(self, record: TaskRecord, idempotency: tuple[str, str, datetime] | None) -> None:
        from medops.api.contracts import HistoricalRequest, TaskCreateRequest

        if idempotency is not None:
            route, key, expires = idempotency
            request = TaskCreateRequest(
                skill_name=record.skill_name,
                skill_version=record.skill_version,
                input=dict(record.input),
                historical=HistoricalRequest.model_validate(record.historical) if record.historical else None,
            )
            try:
                with self._conn.transaction():  # savepoint: a losing race leaves the outer transaction usable
                    self._insert_task(record)  # the task first: the idempotency row references it
                    self._conn.execute(
                        "insert into idempotency_keys (principal, route, key, request_hash, task_id, expires_at) values (%s, %s, %s, %s, %s, %s)",
                        (
                            record.principal,
                            route,
                            key,
                            canonical_hash(request.model_dump(mode="json")),
                            record.task_id,
                            expires,
                        ),
                    )
            except UniqueViolation:
                raise IdempotencyRace() from None
            return
        self._insert_task(record)

    def _insert_task(self, record: TaskRecord) -> None:
        self._conn.execute(
            """
            insert into tasks (task_id, principal, dept, skill_name, skill_version, input, historical, status, attempts, max_attempts, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.task_id,
                record.principal,
                record.dept.value,
                record.skill_name,
                record.skill_version,
                Jsonb(dict(record.input)),
                Jsonb(dict(record.historical)) if record.historical else None,
                record.status.value,
                record.attempts,
                record.max_attempts,
                record.created_at,
                record.updated_at,
            ),
        )

    def get(self, task_id: str) -> TaskRecord | None:
        row = self._conn.execute(f"select {_COLUMNS} from tasks where task_id = %s", (task_id,)).fetchone()
        return _record(row) if row else None

    def requeue(self, task_id: str, now: datetime) -> TaskRecord | None:
        row = self._conn.execute(
            f"update tasks set status = 'queued', error = null, lease_owner = null, lease_until = null where task_id = %s and status = 'failed' returning {_COLUMNS}",
            (task_id,),
        ).fetchone()
        return _record(row) if row else None

    def claim_next(self, worker: str, lease_s: float, now: datetime | None = None) -> TaskRecord | None:
        validate_lease(lease_s)
        # Lock the task before touching its attempt; unrelated expired/locked tasks cannot block polling.
        while True:
            row = self._conn.execute(
                f"""select {_COLUMNS}, coalesce(%(now)s::timestamptz, clock_timestamp())
                    from tasks where status = 'queued'
                       or (status = 'running' and lease_until <= coalesce(%(now)s::timestamptz, clock_timestamp()))
                    order by created_at for update skip locked limit 1""",
                {"now": now},
            ).fetchone()
            if row is None:
                return None
            record, claimed_at = _record(row[:-1]), row[-1]
            if record.status is TaskStatus.running:
                self._conn.execute(
                    "update task_attempts set outcome = 'lost', finished_at = %s where task_id = %s and attempt = %s and outcome = 'running'",
                    (claimed_at, record.task_id, record.attempts),
                )
            if record.attempts >= record.max_attempts:
                self._conn.execute(
                    "update tasks set status = 'failed', lease_owner = null, lease_until = null, error = %s where task_id = %s",
                    (
                        Jsonb(
                            {
                                "code": "dependency_unavailable",
                                "message": "服务暂时不可用，请稍后重试",
                                "trace_id": None,
                                "retryable": False,
                            }
                        ),
                        record.task_id,
                    ),
                )
                continue
            row = self._conn.execute(
                f"""update tasks set status = 'running', attempts = attempts + 1,
                     lease_owner = %s, lease_until = %s where task_id = %s returning {_COLUMNS}""",
                (worker, claimed_at + timedelta(seconds=lease_s), record.task_id),
            ).fetchone()
            claimed = _record(row)
            self._conn.execute(
                "insert into task_attempts (task_id, attempt, worker, started_at) values (%s, %s, %s, %s)",
                (claimed.task_id, claimed.attempts, worker, claimed_at),
            )
            return claimed

    def owns_lease(self, task_id: str, worker: str, attempt: int, now: datetime | None = None) -> bool:
        row = self._conn.execute(
            """select exists(select 1 from tasks where task_id = %s and status = 'running'
                    and lease_owner = %s and attempts = %s
                    and lease_until > coalesce(%s::timestamptz, clock_timestamp()))""",
            (task_id, worker, attempt, now),
        ).fetchone()
        return bool(row[0])

    def record_lost(self, task_id: str, worker: str, attempt: int, trace_id: str, now: datetime | None = None) -> bool:
        # The task may belong to someone else now; update only this worker's old attempt, never the task.
        row = self._conn.execute(
            """update task_attempts a set outcome = 'lost',
                    finished_at = coalesce(a.finished_at, %(now)s::timestamptz, clock_timestamp()),
                    trace_id = %(trace)s, error_code = 'dependency_unavailable'
                where a.task_id = %(id)s and a.attempt = %(attempt)s and a.worker = %(worker)s
                  and a.outcome in ('running', 'lost') and (a.trace_id is null or a.trace_id = %(trace)s)
                  and not exists(select 1 from tasks t where t.task_id = a.task_id
                      and t.status = 'running' and t.lease_owner = %(worker)s and t.attempts = %(attempt)s
                      and t.lease_until > coalesce(%(now)s::timestamptz, clock_timestamp()))
                returning a.attempt_id""",
            {"id": task_id, "worker": worker, "attempt": attempt, "trace": trace_id, "now": now},
        ).fetchone()
        return row is not None

    def _finish(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str | None,
        now: datetime | None,
        *,
        status: str,
        result: Mapping[str, Any] | None,
        error: Mapping[str, Any] | None,
    ) -> bool:
        # Acquire the row before checking the clock. An UPDATE predicate can otherwise be evaluated
        # before waiting for an unchanged, locked tuple, and admit a report after the lease expires.
        owned = self._conn.execute(
            "select task_id from tasks where task_id = %s and status = 'running' and lease_owner = %s and attempts = %s for update",
            (task_id, worker, attempt),
        ).fetchone()
        if owned is None:
            return False
        row = self._conn.execute(
            """
            update tasks set status = %(status)s, result = %(result)s, error = %(error)s, trace_id = %(trace)s,
                   lease_owner = null, lease_until = null
             where task_id = %(id)s and status = 'running' and lease_owner = %(worker)s and attempts = %(attempt)s
               and lease_until > coalesce(%(now)s::timestamptz, clock_timestamp())
            returning task_id
            """,
            {
                "status": status,
                "result": Jsonb(dict(result)) if result is not None else None,
                "error": Jsonb(dict(error)) if error is not None else None,
                "trace": trace_id,
                "id": task_id,
                "worker": worker,
                "attempt": attempt,
                "now": now,
            },
        ).fetchone()
        if row is None:
            return False
        self._conn.execute(
            "update task_attempts set outcome = %s, finished_at = coalesce(%s::timestamptz, clock_timestamp()), trace_id = %s, error_code = %s where task_id = %s and attempt = %s",
            (status, now, trace_id, (error or {}).get("code"), task_id, attempt),
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
        return self._finish(task_id, worker, attempt, trace_id, now, status="completed", result=result, error=None)

    def fail(
        self,
        task_id: str,
        worker: str,
        attempt: int,
        trace_id: str | None,
        error: Mapping[str, Any],
        now: datetime | None = None,
    ) -> bool:
        return self._finish(task_id, worker, attempt, trace_id, now, status="failed", result=None, error=error)
