"""Bounded production database connections shared by process entry points."""

from typing import Any

import psycopg

from medops.core.config import Settings
from medops.core.errors import ErrorCode, InfrastructureError


def open_connection(dsn: str, settings: Any) -> psycopg.Connection[Any]:
    """Every runtime connection fails fast (record 78): a connect timeout and a per-statement timeout, and an
    unreachable database is `dependency_unavailable` (503, retryable) rather than a request that hangs until the
    client gives up."""
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
