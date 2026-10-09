"""Date and engine continuity across ordinary and historical evaluation queries (record 126).

Fake database/model adapters keep the real Plane and shared retrieval assembly under test, without model calls.
"""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.evals import runtime
from medops.harness import assembly


@pytest.mark.parametrize("candidate", [False, True], ids=["production", "candidate"])
def test_historical_queries_keep_the_engine_and_apply_the_date_to_both_channels(monkeypatch, candidate):
    class Connection:
        read_only = False

        def __init__(self):
            self.queries = []

        @contextmanager
        def transaction(self):
            yield

        def execute(self, sql, params=None):
            self.queries.append((sql, params))

        def rollback(self):
            pass

    connections = []

    def connect(_url, **kwargs):
        conn = Connection()
        connections.append(conn)
        return conn

    monkeypatch.setattr(runtime.psycopg, "connect", connect)
    coverage = []
    monkeypatch.setattr(
        "medops.retrieval.integrity.require_retrieval_integrity",
        lambda conn, *, plane, **kwargs: coverage.append((conn, plane)),
    )
    monkeypatch.setattr("medops.evals.run_conditions.fact_snapshot", lambda conn: {"sha256": "fixture"})
    monkeypatch.setattr(assembly, "production_lexical_versions", lambda: "production-pin")
    monkeypatch.setattr(assembly, "production_lexical_retriever", lambda conn, *, as_of: ("production", conn, as_of))
    monkeypatch.setattr(
        assembly, "production_vector_retriever", lambda conn, provider, *, as_of: ("vector", conn, as_of)
    )

    def candidate_factory(conn, *, as_of):
        return "candidate", conn, as_of

    today, historical = date(2026, 10, 7), date(2025, 1, 1)
    plane = runtime.Plane(
        "fixture",
        "postgresql://localhost/fixture",
        SimpleNamespace(spec="fixture-spec"),
        SimpleNamespace(score=lambda query, texts: []),
        object(),
        today,
        lexical_factory=candidate_factory if candidate else None,
        admin_url="postgresql://localhost/fixture",
    )
    assert connections[1].read_only
    assert coverage == [(connections[1], "fixture")]
    user = UserContext(user_id="reviewer", dept=Dept.PV, roles=("analyst",), acl_scopes=frozenset({"PV:read"}))
    # Rebuilding a historical retriever must not overwrite the normal retriever's effective date.
    historical_retrieval = plane.retrieval_for(historical)
    for counted, effective in ((historical_retrieval, historical), (plane.retrieval, today)):
        port = counted._inner
        with port._conn_for_user(user) as conn:
            assert conn is connections[0]
            assert port._lexical_factory(conn) == ("candidate" if candidate else "production", conn, effective)
            assert port._vector_factory(conn) == ("vector", conn, effective)
        assert port._lv == (None if candidate else "production-pin")
    assert all(params == ("PV",) for _, params in connections[0].queries)


def test_database_selection_preserves_connection_options():
    assert runtime.with_database("postgresql://localhost/old?sslmode=require", "new") == (
        "postgresql://localhost/new?sslmode=require"
    )


@pytest.mark.parametrize("failure", ["connect", "preflight"])
def test_failed_plane_setup_closes_already_opened_connections(monkeypatch, failure):
    from medops.retrieval.production import IndexCoverageError

    connections, closed = [], []

    def connect(url, **kwargs):
        if failure == "connect" and connections:
            raise runtime.psycopg.OperationalError("fixture")
        conn = SimpleNamespace(
            close=lambda: closed.append(url),
            execute=lambda *args: None,
        )
        connections.append(conn)
        return conn

    def refuse(*args, **kwargs):
        raise IndexCoverageError("fixture incomplete")

    monkeypatch.setattr(runtime.psycopg, "connect", connect)
    monkeypatch.setattr("medops.retrieval.integrity.require_retrieval_integrity", refuse)
    with pytest.raises((runtime.psycopg.OperationalError, IndexCoverageError)):
        runtime.Plane(
            "fixture",
            "postgresql://localhost/fixture",
            SimpleNamespace(spec="test"),
            None,
            None,
            date(2026, 10, 8),
            admin_url="postgresql://localhost/fixture",
        )
    assert len(closed) == len(connections)
