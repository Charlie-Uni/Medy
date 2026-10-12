"""Bounded production database connections shared by process entry points."""

from typing import Any, Protocol

import psycopg

from medops.core.config import Settings
from medops.core.errors import ErrorCode, InfrastructureError


class ConnectionSettings(Protocol):
    @property
    def db_connect_timeout_s(self) -> int: ...

    @property
    def db_statement_timeout_ms(self) -> int: ...


def open_connection(dsn: str, settings: ConnectionSettings | None) -> psycopg.Connection[Any]:
    """Every runtime connection fails fast (record 78): a connect timeout and a per-statement timeout, and an
    unreachable database is `dependency_unavailable` (503, retryable) rather than a request that hangs until the
    client gives up."""
    # Older callers may omit settings/fields. Only this compatibility boundary supplies defaults,
    # directly from Settings; production callers carry the explicit fields above.
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=getattr(
                settings, "db_connect_timeout_s", Settings.model_fields["db_connect_timeout_s"].default
            ),
            options=f"-c statement_timeout={getattr(settings, 'db_statement_timeout_ms', Settings.model_fields['db_statement_timeout_ms'].default)}",
        )
    except psycopg.OperationalError as exc:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable, detail=f"database: {type(exc).__name__}", retryable=True
        ) from None
