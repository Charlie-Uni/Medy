"""Logical backup of one MedOps database (M5-06, record 87).

    python scripts/db_backup.py [--db medops] [--out backups/] [--container medops-postgres]

`pg_dump` runs inside the Postgres container (the host has no client tools), custom format. Owner and privilege
statements are kept: the group roles are cluster-wide and exist on any restore target that ran the 0002 migration
and `make db-users`. The dump is written next to a `.sha256` file; the DSN comes from DATABASE_ADMIN_URL in the
environment and never reaches stdout. RPO of this P0 flow is the dump interval; continuous archiving is P1
(baseline 7.1).

The password reaches Docker through the child environment, not command arguments. Host/container administrators
can still inspect environments; this is not a secret store. Install the project before running this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import pathlib
import subprocess
import sys
import urllib.parse

from medops.infrastructure.db.pg_subprocess import pg_environment, safe_stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="database name (default: the one in DATABASE_ADMIN_URL)")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("backups"))
    ap.add_argument("--container", default=os.environ.get("MEDOPS_PG_CONTAINER", "medops-postgres"))
    args = ap.parse_args()
    dsn = os.environ.get("DATABASE_ADMIN_URL")
    if not dsn:
        print("DATABASE_ADMIN_URL is required", file=sys.stderr)
        return 2
    u = urllib.parse.urlsplit(dsn)
    db = args.db or u.path.lstrip("/")
    user = urllib.parse.unquote(u.username or "")
    password = urllib.parse.unquote(u.password or "")
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    target = args.out / f"{db}-{stamp}.dump"
    cmd = [
        "docker",
        "exec",
        "-e",
        "PGPASSWORD",
        args.container,
        "pg_dump",
        "-U",
        user,
        "-h",
        "localhost",
        "-Fc",
        db,
    ]
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        try:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, env=pg_environment(password))
        except OSError as exc:
            target.unlink(missing_ok=True)
            print(f"pg_dump launch failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    if proc.returncode != 0:
        target.unlink(missing_ok=True)
        print(f"pg_dump failed: {safe_stderr(proc.stderr, dsn=dsn, password=password, limit=300)}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".dump.sha256").write_text(f"{digest}  {target.name}\n")
    print(f"{target} {target.stat().st_size} bytes sha256={digest[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
