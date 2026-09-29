"""`--dry-run` on the Loop CLIs must roll the transaction back the psycopg way (raise `Rollback` inside the
`transaction()` block); an explicit `conn.rollback()` there raises ProgrammingError and the run crashes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
import pytest

from medops.loop import observe, reflect, tickets


class FakeConn:
    """Mimics psycopg's transaction() contract: swallows Rollback, forbids explicit rollback()."""

    def __init__(self) -> None:
        self.outcome: str | None = None

    @contextmanager
    def transaction(self):
        try:
            yield self
        except psycopg.Rollback:
            self.outcome = "rolled back"
        else:
            self.outcome = "committed"

    def rollback(self) -> None:
        raise psycopg.ProgrammingError("Explicit rollback() forbidden within a Transaction context.")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@dataclass
class Report:
    opened: int = 0


@pytest.fixture
def conn(monkeypatch):
    fake = FakeConn()
    monkeypatch.setenv("DATABASE_LOOP_URL", "postgresql://loop:pw@localhost:5432/db")
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: fake)
    monkeypatch.setattr(reflect, "_connect", lambda url, settings: fake)
    monkeypatch.setattr(observe, "observe", lambda *a, **k: Report())
    monkeypatch.setattr(observe, "PgSignalSource", lambda c: c)
    monkeypatch.setattr(observe, "PgCaseStore", lambda c: c)
    monkeypatch.setattr(tickets, "open_tickets", lambda c: Report())
    monkeypatch.setattr(reflect, "reflect", lambda c: Report())
    return fake


@pytest.mark.parametrize(
    ("main", "argv"),
    [
        (observe.main, ["--since", "2026-09-24"]),
        (tickets.main, []),
        (reflect.main, ["run"]),
    ],
)
def test_dry_run_rolls_back_and_a_real_run_commits(conn, capsys, main, argv):
    assert main([*argv, "--dry-run"]) == 0
    assert conn.outcome == "rolled back"
    assert main(argv) == 0
    assert conn.outcome == "committed"
    assert capsys.readouterr().out.count('"opened": 0') == 2
