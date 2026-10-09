"""API readiness checks actual indexes and the same database as requests, without leaking diagnostics."""

from types import SimpleNamespace

import psycopg
import pytest

from medops.api import runtime as mod
from medops.retrieval import integrity
from tests.unit.harness._fixtures import versions


@pytest.fixture
def setup(monkeypatch):
    calls, checks, clock = [], [], [0.0]
    status = {"ready": True, "database_identity": "same-db", "coverage": {"missing_embedding": 0}}
    rt = mod.ProductionRuntime(
        settings=SimpleNamespace(),
        authenticator=None,
        gateway=None,
        embedding=SimpleNamespace(spec="test-spec"),
        reranker=None,
        versions=versions(),
    )
    rt._dsn, rt._admin_dsn = "app-secret", "admin-secret"

    class Connection:
        read_only = False

        def __init__(self, dsn):
            self.dsn = dsn

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def connect(dsn, **kwargs):
        calls.append((dsn, kwargs))
        return Connection(dsn)

    def inspect(conn, *, embedding):
        assert conn.read_only and embedding == "test-spec"
        checks.append(conn.dsn)
        return dict(status)

    monkeypatch.setattr(mod.psycopg, "connect", connect)
    monkeypatch.setattr(integrity, "inspect_retrieval", inspect)  # reached through inspect_readiness
    monkeypatch.setattr(mod, "database_identity", lambda conn: "same-db")
    monkeypatch.setattr(mod, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    return rt, status, calls, checks, clock


def test_coverage_cache_is_bounded_and_missing_indexes_turn_ready_false(setup):
    rt, status, calls, checks, clock = setup
    assert rt.ready()
    status["ready"] = False
    clock[0] = 4.9
    assert rt.ready() and len(checks) == 1
    clock[0] = 5.0
    assert not rt.ready() and len(checks) == 2
    assert all(c[1] == {"connect_timeout": 2, "options": "-c statement_timeout=1000"} for c in calls)


def test_app_and_admin_connections_cannot_report_on_different_databases(setup, monkeypatch):
    rt, *_ = setup
    monkeypatch.setattr(mod, "database_identity", lambda conn: "another-db")
    assert not rt.ready()


def test_missing_monitor_connection_and_stalled_model_fail_closed(setup):
    rt, _, calls, *_ = setup
    rt._admin_dsn = None
    assert not rt.ready() and not calls
    assert rt.retrieval_integrity()["problems"] == ["integrity_connection_not_configured"]
    rt._pinned = SimpleNamespace(stalled=True)
    assert not rt.ready() and not calls


def test_database_errors_do_not_disclose_secrets_or_return_ready(setup, monkeypatch):
    rt, *_ = setup

    def fail(*args, **kwargs):
        raise psycopg.OperationalError("private connection detail")

    monkeypatch.setattr(mod.psycopg, "connect", fail)
    assert not rt.ready()
    assert rt.retrieval_integrity() == {"ready": False, "problems": ["integrity_check_unavailable"]}
