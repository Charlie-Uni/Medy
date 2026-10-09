"""Bounded worker input, explicit database targeting and safe configuration failure."""

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from medops.retrieval.maintenance import BatchResult
from medops.worker import retrieval as worker


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--database", "x/y"],
        ["--database", "db", "--batch", "0"],
        ["--database", "db", "--batch", "101"],
        ["--database", "db", "--poll", "nan"],
        ["--database", "db", "--poll", "0"],
    ],
)
def test_invalid_or_missing_explicit_target_fails_before_settings(extra, monkeypatch):
    monkeypatch.setattr(worker, "Settings", lambda: pytest.fail("configuration should not be read"))
    with pytest.raises(SystemExit) as caught:
        worker.main(["--consumer", "lexical-index", *extra])
    assert caught.value.code == 2


def test_cache_consumer_refuses_off_and_process_local_cache():
    for mode in ("off", "memory"):
        with pytest.raises(ValueError, match="shared cache"):
            worker.handler_from_settings(SimpleNamespace(retrieval_cache=mode), "retrieval-cache")


@pytest.mark.parametrize("failed", [(), (1,)])
def test_once_targets_requested_database_and_returns_failure_for_unacked_events(monkeypatch, capsys, failed):
    settings = SimpleNamespace(
        database_admin_url=SecretStr("postgresql://user:secret@localhost/old_db"),
        db_connect_timeout_s=2,
        db_statement_timeout_ms=1000,
    )
    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "handler_from_settings", lambda *args, **kwargs: "handler")
    observed = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            observed["committed"] = True

    def connect(dsn, **kwargs):
        from psycopg.conninfo import conninfo_to_dict

        observed.update(conninfo_to_dict(dsn))
        return Connection()

    monkeypatch.setattr(worker.psycopg, "connect", connect)
    monkeypatch.setattr(worker.maintenance, "consume_batch", lambda *args, **kwargs: BatchResult((), failed))
    assert worker.main(["--database", "requested_db", "--consumer", "lexical-index", "--once"]) == (1 if failed else 0)
    assert observed["dbname"] == "requested_db" and observed["committed"]
    assert "secret" not in capsys.readouterr().out


def test_configuration_error_is_sanitized(monkeypatch, capsys):
    def invalid():
        raise ValueError("a-secret-password")

    monkeypatch.setattr(worker, "Settings", invalid)
    assert worker.main(["--database", "db", "--consumer", "lexical-index", "--once"]) == 2
    output = capsys.readouterr().out
    assert "ValueError" in output and "a-secret-password" not in output


def test_dead_letter_requeue_is_explicit_and_does_not_load_the_handler(monkeypatch, capsys):
    settings = SimpleNamespace(
        database_admin_url=SecretStr("postgresql://user:secret@localhost/db"),
        db_connect_timeout_s=2,
        db_statement_timeout_ms=1000,
    )
    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "handler_from_settings", lambda *args, **kwargs: pytest.fail("handler loaded"))
    observed = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(worker.psycopg, "connect", lambda *args, **kwargs: Connection())
    monkeypatch.setattr(
        worker.outbox,
        "requeue_dead_letter",
        lambda conn, consumer, event_id, *, actor: (
            observed.update(consumer=consumer, event_id=event_id, actor=actor) or True
        ),
    )
    assert (
        worker.main(["--database", "db", "--consumer", "lexical-index", "--requeue-event", "7", "--actor", "ops-01"])
        == 0
    )
    assert observed == {"consumer": "lexical-index", "event_id": 7, "actor": "ops-01"}
    assert '"requeued": true' in capsys.readouterr().out
