"""Role separation, explicit target, rollback and UTC boundaries in the scheduled maintenance adapter."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr

from medops.worker import maintenance as m


@pytest.mark.parametrize("job,credential", list(m.JOBS.items()))
def test_job_uses_only_required_role_and_requested_database(job, credential, monkeypatch, capsys):
    settings = SimpleNamespace(
        **{name: SecretStr(f"postgresql://{name}:private@localhost/old") for name in m.JOBS.values()},
        db_connect_timeout_s=2,
        db_statement_timeout_ms=1000,
    )
    monkeypatch.setattr(m, "Settings", lambda: settings)
    observed = {}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def transaction(self, **kwargs):
            observed.update(kwargs)
            return self

    def connect(dsn, **kwargs):
        observed.update(conninfo_to_dict(dsn))
        observed.update(kwargs)
        return Connection()

    monkeypatch.setattr(m.psycopg, "connect", connect)
    monkeypatch.setattr(m, "execute", lambda conn, settings, **kwargs: observed.update(kwargs) or {"count": 0})
    monkeypatch.setattr(m, "pulse", lambda: observed.update(pulsed=True))
    args = ["--job", job, "--database", "requested", "--dry-run"]
    if job == "loop-observe":
        args += ["--since", "2026-10-11T08:00:00+10:00"]
    assert m.main(args) == 0
    assert observed["user"] == credential and observed["dbname"] == "requested"
    assert observed["force_rollback"] is True and observed["pulsed"] is True
    if job == "loop-observe":
        assert observed["since"] == datetime(2026, 10, 10, 22, tzinfo=UTC)
    assert "private" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "args",
    [
        ["--job", "loop-observe", "--database", "x"],
        ["--job", "audit-retention", "--database", "x/y"],
        ["--job", "audit-retention", "--database", "x", "--since", "2026-01-01"],
    ],
)
def test_invalid_input_never_reads_credentials(args, monkeypatch):
    monkeypatch.setattr(m, "Settings", lambda: pytest.fail("settings read"))
    with pytest.raises(SystemExit) as caught:
        m.main(args)
    assert caught.value.code == 2


def test_missing_loop_role_never_falls_back_to_admin_or_pulses(monkeypatch, capsys):
    monkeypatch.setattr(
        m, "Settings", lambda: SimpleNamespace(database_loop_url=None, database_admin_url=SecretStr("private"))
    )
    monkeypatch.setattr(m.psycopg, "connect", lambda *a, **k: pytest.fail("connected"))
    monkeypatch.setattr(m, "pulse", lambda: pytest.fail("pulsed"))
    assert m.main(["--job", "loop-observe", "--database", "db", "--since", "1970-01-01"]) == 1
    assert '"error_type": "ValueError"' in capsys.readouterr().out


def test_duplicate_schedule_skips_work_when_lock_is_held(monkeypatch):
    conn = SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: (False,)))
    monkeypatch.setattr(m, "purge", lambda *a, **k: pytest.fail("purged"))
    assert m.execute(conn, None, job="audit-retention", since=None, dry_run=False) == {"status": "already_running"}
