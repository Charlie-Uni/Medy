"""Operational backup credentials and failure reports, using only deliberately fake secrets."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from datetime import UTC, datetime
from urllib.parse import quote, quote_plus

import pytest
from scripts import db_backup, db_restore_drill

from medops.infrastructure.db.pg_subprocess import safe_stderr

PASSWORD = "fake $() `x` /@+ 密碼"
DSN = f"postgresql://fake_admin:{quote(PASSWORD, safe='')}@localhost:5432/fake_source?sslmode=disable"


def setup_env(monkeypatch):
    monkeypatch.setenv("DATABASE_ADMIN_URL", DSN)
    monkeypatch.setenv("PGPASSWORD", "parent-value-must-remain")
    monkeypatch.setenv("DOCKER_HOST", "unix:///fake/docker.sock")


def assert_credential_boundary(cmd, kwargs):
    assert "PGPASSWORD" in cmd and all(not arg.startswith("PGPASSWORD=") for arg in cmd)
    assert PASSWORD not in repr(cmd) and DSN not in repr(cmd) and quote(PASSWORD, safe="") not in repr(cmd)
    assert kwargs["env"]["PGPASSWORD"] == PASSWORD
    assert "DATABASE_ADMIN_URL" not in kwargs["env"]
    assert kwargs["env"]["DOCKER_HOST"] == "unix:///fake/docker.sock"
    assert os.environ["PGPASSWORD"] == "parent-value-must-remain"
    assert "shell" not in kwargs


@pytest.mark.parametrize("failure", [None, "returncode", "launch"])
def test_backup_argv_environment_private_file_hash_and_failure_cleanup(monkeypatch, tmp_path, capsys, failure):
    setup_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["db_backup.py", "--out", str(tmp_path), "--container", "fake-pg"])
    calls = []

    def run(cmd, **kwargs):
        assert_credential_boundary(cmd, kwargs)
        assert cmd == [
            "docker",
            "exec",
            "-e",
            "PGPASSWORD",
            "fake-pg",
            "pg_dump",
            "-U",
            "fake_admin",
            "-h",
            "localhost",
            "-Fc",
            "fake_source",
        ]
        calls.append(cmd)
        if failure == "launch":
            raise FileNotFoundError(PASSWORD)
        kwargs["stdout"].write(b"fake-custom-dump")
        return subprocess.CompletedProcess(
            cmd, 1 if failure else 0, stderr=f"dump diagnostic {DSN} {PASSWORD}".encode()
        )

    monkeypatch.setattr(db_backup.subprocess, "run", run)
    assert db_backup.main() == (1 if failure else 0)
    assert len(calls) == 1
    captured = capsys.readouterr()
    assert PASSWORD not in captured.out + captured.err and DSN not in captured.out + captured.err
    if failure:
        assert list(tmp_path.iterdir()) == []
        assert "FileNotFoundError" in captured.err if failure == "launch" else "dump diagnostic" in captured.err
    else:
        dump = next(tmp_path.glob("*.dump"))
        assert dump.stat().st_mode & 0o777 == 0o600
        assert dump.read_bytes() == b"fake-custom-dump"
        assert (
            dump.with_suffix(".dump.sha256").read_text()
            == f"{hashlib.sha256(dump.read_bytes()).hexdigest()}  {dump.name}\n"
        )


def test_backup_never_overwrites_an_existing_dump(monkeypatch, tmp_path):
    setup_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["db_backup.py", "--out", str(tmp_path)])

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 12, tzinfo=UTC)

    monkeypatch.setattr(db_backup.dt, "datetime", FixedDatetime)
    dump = tmp_path / "fake_source-20261012T000000Z.dump"
    dump.write_bytes(b"old-dump")
    monkeypatch.setattr(db_backup.subprocess, "run", lambda *a, **k: pytest.fail("must not start a dump"))
    with pytest.raises(FileExistsError):
        db_backup.main()
    assert dump.read_bytes() == b"old-dump"


@pytest.mark.parametrize("failure", [None, "returncode", "launch"])
def test_restore_argv_redacted_report_and_only_owned_scratch_cleanup(monkeypatch, tmp_path, capsys, failure):
    setup_env(monkeypatch)
    dump = tmp_path / "test.dump"
    dump.write_bytes(b"fake-custom-dump")
    out = tmp_path / "reports"
    monkeypatch.setattr(
        sys, "argv", ["db_restore_drill.py", "--dump", str(dump), "--out", str(out), "--container", "fake-pg"]
    )
    statements = []
    inventories = []

    class Connection:
        def execute(self, statement):
            statements.append(statement.as_string())

    def inventory(dsn):
        inventories.append(dsn)
        assert dsn != DSN or not failure
        return {
            "counts": {"sample": 2},
            "tables": ["sample"],
            "alembic": "0026",
            "corpus_md5": "hash",
            "grantees": ["medops_readonly"],
            "fact_plane_id": "stable",
        }

    def run(cmd, **kwargs):
        assert_credential_boundary(cmd, kwargs)
        assert cmd[:6] == ["docker", "exec", "-i", "-e", "PGPASSWORD", "fake-pg"]
        assert cmd[6:] == [
            "pg_restore",
            "-U",
            "fake_admin",
            "-h",
            "localhost",
            "-d",
            cmd[12],
            "--no-owner",
            "--exit-on-error",
        ]
        assert kwargs["stdin"].read() == b"fake-custom-dump"
        if failure == "launch":
            raise FileNotFoundError(PASSWORD)
        return subprocess.CompletedProcess(
            cmd,
            1 if failure else 0,
            stderr=f"restore diagnostic {DSN} {PASSWORD} {quote(PASSWORD, safe='')} {quote_plus(PASSWORD)}".encode(),
        )

    monkeypatch.setattr(db_restore_drill.psycopg, "connect", lambda *a, **k: nullcontext(Connection()))
    monkeypatch.setattr(db_restore_drill, "inventory", inventory)
    monkeypatch.setattr(db_restore_drill.subprocess, "run", run)
    assert db_restore_drill.main() == (1 if failure else 0)
    report = json.loads((out / "report.json").read_text())
    assert report["scratch"].startswith("medops_restore_drill_") and report["scratch"] != "fake_source_restore_drill"
    assert statements == [f'create database "{report["scratch"]}"', f'drop database if exists "{report["scratch"]}"']
    assert report["ok"] is (failure is None) and report["scratch_dropped"] is True
    assert len(inventories) == (0 if failure else 2)
    captured = capsys.readouterr()
    text = captured.out + captured.err + (out / "report.json").read_text() + (out / "report.md").read_text()
    for secret in (DSN, PASSWORD, quote(PASSWORD, safe=""), quote_plus(PASSWORD)):
        assert secret not in text
    if failure == "launch":
        assert report["launch_error_type"] == "FileNotFoundError"
    else:
        assert "restore diagnostic" in report["pg_restore_stderr_tail"]


def test_restore_does_not_drop_an_unowned_database_when_creation_fails(monkeypatch, tmp_path):
    setup_env(monkeypatch)
    dump = tmp_path / "test.dump"
    dump.write_bytes(b"fake")
    monkeypatch.setattr(sys, "argv", ["db_restore_drill.py", "--dump", str(dump), "--out", str(tmp_path / "reports")])
    statements = []

    class Connection:
        def execute(self, statement):
            statements.append(statement.as_string())
            raise db_restore_drill.psycopg.errors.DuplicateDatabase()

    monkeypatch.setattr(db_restore_drill.psycopg, "connect", lambda *a, **k: nullcontext(Connection()))
    monkeypatch.setattr(db_restore_drill.subprocess, "run", lambda *a, **k: pytest.fail("must not start a restore"))
    with pytest.raises(db_restore_drill.psycopg.errors.DuplicateDatabase):
        db_restore_drill.main()
    assert len(statements) == 1 and statements[0].startswith("create database ")


def test_redaction_precedes_truncation_and_handles_bad_utf8():
    text = ("diagnostic " + DSN + " " + quote(PASSWORD, safe="") + " " + PASSWORD).encode() + b"\xff"
    safe = safe_stderr(text, dsn=DSN, password=PASSWORD, limit=10)
    assert safe == "redacted]�" and len(safe) == 10
