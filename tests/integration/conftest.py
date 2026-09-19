"""Integration fixtures: a throwaway PostgreSQL database per test session, migrated to head.

The admin DSN comes from MEDOPS_TEST_ADMIN_URL, else from the repo `.env` (DATABASE_ADMIN_URL, then
DATABASE_URL). Without a reachable PostgreSQL the whole directory is skipped with an explicit reason;
CI provides a pgvector service so these tests always run there.
"""

from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from medops.infrastructure.db.login_users import GROUPS, drop_users, provision

REPO = Path(__file__).resolve().parents[2]


def _admin_dsn() -> str | None:
    explicit = os.environ.get("MEDOPS_TEST_ADMIN_URL")
    if explicit:
        return explicit
    env_file = REPO / ".env"
    if not env_file.is_file():
        return None
    from medops.core.config import Settings

    try:
        settings = Settings(_env_file=env_file)
    except Exception:  # noqa: BLE001 - any config problem means "no integration database here"
        return None
    return (settings.database_admin_url or settings.database_url).get_secret_value()


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


@pytest.fixture(scope="session")
def admin_dsn() -> str:
    dsn = _admin_dsn()
    if not dsn:
        pytest.skip("integration: no MEDOPS_TEST_ADMIN_URL and no usable .env (DATABASE_ADMIN_URL)")
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
    except psycopg.Error as exc:
        pytest.skip(f"integration: PostgreSQL unreachable ({type(exc).__name__}); start it with `make up`")
    return dsn


@pytest.fixture(scope="session")
def fresh_database(admin_dsn: str) -> Iterator[str]:
    """A brand-new database for this session, dropped afterwards."""
    yield from _temporary_database(admin_dsn)


@pytest.fixture
def scratch_database(admin_dsn: str) -> Iterator[str]:
    """A brand-new database for one test (used for upgrade/downgrade round trips)."""
    yield from _temporary_database(admin_dsn)


def _temporary_database(admin_dsn: str) -> Iterator[str]:
    name = f"medops_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'create database "{name}"')
    dsn = _with_database(admin_dsn, name)
    try:
        yield dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'drop database "{name}" with (force)')


def _with_database(url: str, name: str) -> str:
    """Same URL (user, password, host, port, options), different database name."""
    parts = urlsplit(url)
    if not parts.scheme.startswith("postgres"):
        raise ValueError("admin DSN must be a postgresql:// URL")
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


@pytest.fixture(scope="session")
def migrated(fresh_database: str) -> str:
    run_alembic(fresh_database, "upgrade", "head")
    return fresh_database


@pytest.fixture
def conn(migrated: str) -> Iterator[psycopg.Connection]:
    """One transaction per test, always rolled back: tests never leak rows into each other."""
    with psycopg.connect(migrated) as connection:
        yield connection
        connection.rollback()


def user_dsn(admin_dsn: str, user: str, password: str, dbname: str) -> str:
    """The admin URL rewritten to connect as `user` to `dbname` (host, port and options kept)."""
    parts = urlsplit(admin_dsn)
    hostport = (parts.hostname or "localhost") + (f":{parts.port}" if parts.port else "")
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{hostport}"
    return urlunsplit((parts.scheme, netloc, "/" + dbname, parts.query, parts.fragment))


@pytest.fixture(scope="session")
def login_users(admin_dsn: str, migrated: str) -> Iterator[dict[str, dict[str, str]]]:
    """Three LOGIN users provisioned through the real script and attached to the migrated database;
    their sessions are terminated and the users dropped at the end (group roles stay, see 0002)."""
    prefix = f"mt{secrets.token_hex(3)}"
    passwords = {kind: secrets.token_urlsafe(18) for kind in GROUPS}
    with psycopg.connect(admin_dsn) as conn:
        names = provision(conn, prefix=prefix, passwords=passwords)
        conn.commit()
    dbname = urlsplit(migrated).path.lstrip("/")
    users = {
        kind: {
            "name": names[kind],
            "password": passwords[kind],
            "dsn": user_dsn(admin_dsn, names[kind], passwords[kind], dbname),
        }
        for kind in GROUPS
    }
    try:
        yield users
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where usename = any(%s) and pid <> pg_backend_pid()",
                (list(names.values()),),
            )
            drop_users(conn, prefix=prefix)
