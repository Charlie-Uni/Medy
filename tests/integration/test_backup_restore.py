"""Real container pg_dump/pg_restore on the migrated test database, never a business database."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import psycopg
import pytest
from scripts import db_backup, db_restore_drill

from tests.service_requirements import unavailable


@pytest.mark.parametrize("invalid_dump", [False, True])
def test_native_backup_restore_and_failed_restore_cleanup(migrated, monkeypatch, tmp_path, invalid_dump):
    container = os.environ.get("MEDOPS_TEST_PG_CONTAINER", "medops-postgres")
    try:
        state = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container], capture_output=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        unavailable("backup integration requires the configured PostgreSQL Docker container")
    if state.returncode or state.stdout.strip() != b"true":
        unavailable("backup integration requires a running MEDOPS_TEST_PG_CONTAINER")
    monkeypatch.setenv("DATABASE_ADMIN_URL", migrated)
    before = db_restore_drill.inventory(migrated)
    monkeypatch.setattr(sys, "argv", ["db_backup.py", "--out", str(tmp_path / "backups"), "--container", container])
    assert db_backup.main() == 0
    dump = next((tmp_path / "backups").glob("*.dump"))
    assert dump.stat().st_mode & 0o777 == 0o600
    assert dump.with_suffix(".dump.sha256").read_text().split()[0] == hashlib.sha256(dump.read_bytes()).hexdigest()
    if invalid_dump:
        dump.write_bytes(b"not-a-postgres-dump")
    monkeypatch.setattr(
        sys,
        "argv",
        ["db_restore_drill.py", "--dump", str(dump), "--out", str(tmp_path / "reports"), "--container", container],
    )
    assert db_restore_drill.main() == (1 if invalid_dump else 0)
    report = json.loads((tmp_path / "reports/report.json").read_text())
    assert report["ok"] is (not invalid_dump) and report["scratch_dropped"] is True
    if not invalid_dump:
        for key in ("tables_match", "alembic_match", "corpus_match", "grantees_match", "fact_plane_identity_match"):
            assert report[key] is True
        assert report["row_count_mismatches"] == {}
    with psycopg.connect(migrated) as conn:
        assert (
            conn.execute("select count(*) from pg_database where datname = %s", (report["scratch"],)).fetchone()[0] == 0
        )
    assert db_restore_drill.inventory(migrated) == before
    password = unquote(urlsplit(migrated).password or "")
    # Never put a real credential into pytest assertion introspection.
    if password and password in (tmp_path / "reports/report.json").read_text():
        pytest.fail("credential leaked to restore report", pytrace=False)
