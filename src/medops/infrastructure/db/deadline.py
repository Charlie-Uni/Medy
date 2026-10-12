"""Deadline-aware facade for an existing identity-bound PostgreSQL transaction.

No new connection or identity is introduced. Each guarded statement uses the current remaining
time and a savepoint so its cancellation cannot abort the outer audit transaction. Timeout settings
are restored before the caller continues. Auditing outside the body keeps its usual database timeout.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.pq import TransactionStatus

from medops.core.deadline import CURRENT_DEADLINE, check_deadline
from medops.core.errors import ErrorCode, InfrastructureError


class DeadlineConnection:
    def __init__(self, conn: Any) -> None:
        self._conn: Any = conn._conn if isinstance(conn, DeadlineConnection) else conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def cursor(self, *args: Any, **kwargs: Any) -> DeadlineCursor:
        check_deadline()
        return DeadlineCursor(self._conn, self._conn.cursor(*args, **kwargs))

    def execute(self, *args: Any, **kwargs: Any) -> DeadlineCursor:
        return self.cursor().execute(*args, **kwargs)


class DeadlineCursor:
    def __init__(self, conn: Any, cursor: Any) -> None:
        self._conn, self._cursor = conn, cursor

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    def __enter__(self) -> DeadlineCursor:
        self._cursor.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        return self._cursor.__exit__(*args)

    def __iter__(self) -> DeadlineCursor:
        return self

    def __next__(self) -> Any:
        check_deadline()
        return next(self._cursor)

    def execute(self, *args: Any, **kwargs: Any) -> DeadlineCursor:
        self._execute("execute", *args, **kwargs)
        return self

    def executemany(self, *args: Any, **kwargs: Any) -> None:
        self._execute("executemany", *args, **kwargs)

    def _execute(self, method: str, *args: Any, **kwargs: Any) -> None:
        deadline = CURRENT_DEADLINE.get()
        if deadline is None:
            getattr(self._cursor, method)(*args, **kwargs)
            return
        check_deadline()  # before any SQL, including the savepoint/settings queries
        # A normal `with psycopg.connect(...)` commits on exit but begins lazily.
        # Without BEGIN here, transaction() around the first guarded statement
        # is top-level and commits it, rather than creating the intended savepoint.
        # Preserve caller ownership; never commit business/audit fragments here.
        if getattr(getattr(self._conn, "info", None), "transaction_status", None) == TransactionStatus.IDLE:
            if self._conn.autocommit:
                raise InfrastructureError(
                    ErrorCode.internal_error, detail="deadline SQL requires a caller-owned transaction", retryable=False
                )
            self._conn.execute("begin")
        try:
            with self._conn.transaction():
                old = self._conn.execute("select current_setting('statement_timeout')").fetchone()[0]
                milliseconds = max(1, int(deadline.remaining() * 1000))
                self._conn.execute(
                    "select set_config('statement_timeout', least(extract(epoch from %s::interval) * 1000, %s)::bigint::text, true)",
                    (old if old != "0" else f"{milliseconds} milliseconds", milliseconds),
                )
                getattr(self._cursor, method)(*args, **kwargs)
                self._conn.execute("select set_config('statement_timeout', %s, true)", (old,))
        except psycopg.errors.QueryCanceled:
            check_deadline()
            raise InfrastructureError(
                ErrorCode.dependency_timeout, detail="database statement timed out", retryable=True
            ) from None
        check_deadline()
