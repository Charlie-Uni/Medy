"""Runtime connections fail fast (record 78): an unreachable database becomes `dependency_unavailable` (503,
retryable) instead of a request that hangs, and every connection carries the connect / statement timeouts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from medops.api.runtime import ProductionRuntime
from medops.core.errors import ErrorCode, InfrastructureError


def runtime() -> ProductionRuntime:
    rt = ProductionRuntime(
        settings=SimpleNamespace(db_connect_timeout_s=1, db_statement_timeout_ms=1234),  # type: ignore[arg-type]
        authenticator=None,  # type: ignore[arg-type]
        gateway=None,  # type: ignore[arg-type]
        embedding=None,
        reranker=None,
        versions=None,  # type: ignore[arg-type]
    )
    rt._dsn = "postgresql://u:p@127.0.0.1:1/db"  # nothing listens on port 1: refused immediately
    rt._admin_dsn = rt._dsn
    return rt


def test_unreachable_database_is_dependency_unavailable_and_retryable():
    with pytest.raises(InfrastructureError) as info, runtime().connection():
        pass
    assert info.value.code is ErrorCode.dependency_unavailable and info.value.retryable is True
    assert "password" not in str(info.value.detail) and "127.0.0.1" not in str(info.value.detail)
    with pytest.raises(InfrastructureError), runtime().admin_connection():
        pass


def test_connections_carry_connect_and_statement_timeouts():
    seen: dict[str, object] = {}

    def fake_connect(dsn: str, **kwargs: object) -> object:
        seen.update(kwargs)
        raise OSError("stop here")

    with patch("medops.api.runtime.psycopg.connect", fake_connect), pytest.raises(OSError):
        runtime()._open("postgresql://u:p@127.0.0.1:1/db")
    assert seen == {"connect_timeout": 1, "options": "-c statement_timeout=1234"}
