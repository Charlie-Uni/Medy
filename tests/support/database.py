"""Owned PostgreSQL test resources, including cleanup when setup or teardown fails.

No fixtures or collected tests live here. Integration conftest controls scopes;
lexical candidates explicitly select their own optional server.
"""

from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from alembic import command
from alembic.config import Config

from medops.evals.safety_data import with_database
from medops.infrastructure.db.login_users import GROUPS, drop_users, provision, username

REPO = Path(__file__).resolve().parents[2]


def alembic_config(dsn: str) -> Config:
    cfg = Config(str(REPO / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO / "migrations"))
    cfg.attributes["dsn"] = dsn
    return cfg


def run_alembic(dsn: str, action: str, target: str) -> None:
    """Run `alembic <action> <target>` against `dsn` through the same env.py the CLI uses."""
    previous = os.environ.get("MEDOPS_MIGRATION_URL")
    os.environ["MEDOPS_MIGRATION_URL"] = dsn
    try:
        getattr(command, action)(alembic_config(dsn), target)
    finally:
        if previous is None:
            os.environ.pop("MEDOPS_MIGRATION_URL", None)
        else:
            os.environ["MEDOPS_MIGRATION_URL"] = previous


def user_dsn(admin_dsn: str, user: str, password: str, dbname: str) -> str:
    """The admin URL rewritten to connect as `user` to `dbname` (host, port and options kept)."""
    parts = urlsplit(admin_dsn)
    hostport = (parts.hostname or "localhost") + (f":{parts.port}" if parts.port else "")
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{hostport}"
    return urlunsplit((parts.scheme, netloc, "/" + dbname, parts.query, parts.fragment))


@contextmanager
def temporary_database(admin_dsn: str) -> Iterator[str]:
    """One owned empty database, force-dropped even if its consumer fails during setup."""
    name = f"medops_test_{uuid.uuid4().hex[:12]}"
    dsn = with_database(admin_dsn, name)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'create database "{name}"')
    try:
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'drop database "{name}" with (force)')


@contextmanager
def temporary_login_users(admin_dsn: str, migrated: str) -> Iterator[dict[str, dict[str, str]]]:
    """Own a unique LOGIN group; register cleanup before provisioning/DSN construction."""
    prefix = f"mt{uuid.uuid4().hex[:12]}"
    passwords = {kind: secrets.token_urlsafe(18) for kind in GROUPS}
    names = {kind: username(prefix, kind) for kind in GROUPS}
    try:
        with psycopg.connect(admin_dsn) as conn:
            provision(conn, prefix=prefix, passwords=passwords)
            conn.commit()
        dbname = urlsplit(migrated).path.lstrip("/")
        yield {
            kind: {
                "name": names[kind],
                "password": passwords[kind],
                "dsn": user_dsn(admin_dsn, names[kind], passwords[kind], dbname),
            }
            for kind in GROUPS
        }
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where usename = any(%s) and pid <> pg_backend_pid()",
                (list(names.values()),),
            )
            drop_users(conn, prefix=prefix)


def make_database(admin_dsn: str) -> Iterator[dict]:
    """Isolated, migrated database + five least-privilege LOGINs; preserve generator callers."""
    with temporary_database(admin_dsn) as dsn:
        run_alembic(dsn, "upgrade", "head")
        with temporary_login_users(admin_dsn, dsn) as users:
            yield {"owner": dsn, "users": {kind: user["dsn"] for kind, user in users.items()}}


def database_fixture(dsn_fixture: str, *, scope: str = "module"):
    """Declare a distinct database with the caller's original module/function scope.

    Call once per exported fixture (B and B2 must never share one database).
    Required/optional availability remains the selected DSN fixture's responsibility.
    """
    import pytest

    if scope not in ("module", "function"):
        raise ValueError("database fixture scope must be module or function")

    @pytest.fixture(scope=scope)
    def isolated(request):
        yield from make_database(request.getfixturevalue(dsn_fixture))

    return isolated


def container_dsn(dsn, host):
    p = urlsplit(dsn)
    credentials = p.netloc.rsplit("@", 1)[0]
    # The test PostgreSQL container listens on 5432; a random host-published port is not its network port.
    return urlunsplit((p.scheme, f"{credentials}@{host}:5432", p.path, p.query, p.fragment))
