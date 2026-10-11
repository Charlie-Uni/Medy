"""All production roles use bounded connection and statement timeouts."""

from types import SimpleNamespace

import psycopg
import pytest

from medops.bootstrap import connections
from medops.core.errors import ErrorCode, InfrastructureError


@pytest.mark.parametrize(
    "config,expected",
    [
        (None, {"connect_timeout": 5, "options": "-c statement_timeout=30000"}),
        (
            SimpleNamespace(db_connect_timeout_s=2, db_statement_timeout_ms=1234),
            {"connect_timeout": 2, "options": "-c statement_timeout=1234"},
        ),
    ],
)
def test_configured_or_legacy_role_connections_use_the_common_limits(monkeypatch, config, expected):
    observed = []

    def connect(dsn, **kwargs):
        observed.append(kwargs)
        raise OSError("stop before network")

    monkeypatch.setattr(connections.psycopg, "connect", connect)
    with pytest.raises(OSError):
        connections.open_connection("private-dsn", config)
    assert observed == [expected]


def test_operational_errors_preserve_the_public_error_without_connection_details(monkeypatch):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError("postgresql://private-user:private-password@private-host/db")

    monkeypatch.setattr(connections.psycopg, "connect", fail)
    with pytest.raises(InfrastructureError) as exc:
        connections.open_connection("private-dsn", None)
    assert exc.value.code is ErrorCode.dependency_unavailable and exc.value.retryable
    assert exc.value.detail == "database: OperationalError"
