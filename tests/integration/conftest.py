"""Integration fixtures: a throwaway PostgreSQL database per test session, migrated to head.

The admin DSN comes from MEDOPS_TEST_ADMIN_URL, else from the repo `.env` (DATABASE_ADMIN_URL, then
DATABASE_URL). Local services may skip; CI or MEDOPS_TEST_REQUIRED_SERVICES=1 requires explicit
PostgreSQL and Redis URLs and fails when either is absent, malformed or unreachable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from tests.service_requirements import required_services, unavailable
from tests.support.database import make_database, run_alembic, temporary_database, temporary_login_users

REPO = Path(__file__).resolve().parents[2]


def _admin_dsn() -> str | None:
    required = required_services()
    explicit = os.environ.get("MEDOPS_TEST_ADMIN_URL")
    if explicit:
        return explicit
    if required:
        return None  # CI must never accidentally use a developer's .env database.
    env_file = REPO / ".env"
    if not env_file.is_file():
        return None
    from medops.core.config import Settings

    try:
        settings = Settings(_env_file=env_file)
    except Exception:  # noqa: BLE001 - any config problem means "no integration database here"
        return None
    return (settings.database_admin_url or settings.database_url).get_secret_value()


@pytest.fixture(scope="session")
def admin_dsn() -> str:
    dsn = _admin_dsn()
    if not dsn:
        unavailable("PostgreSQL URL missing; set MEDOPS_TEST_ADMIN_URL (local mode also accepts .env)")
    error_type = None
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
    except (psycopg.Error, ValueError) as exc:
        error_type = type(exc).__name__
    if error_type:
        unavailable(f"PostgreSQL unavailable ({error_type}); start it with `make up`")
    return dsn


def _redis_url() -> str | None:
    required = required_services()
    explicit = os.environ.get("MEDOPS_TEST_REDIS_URL")
    if explicit:
        return explicit
    if required:
        return None
    env_file = REPO / ".env"
    if not env_file.is_file():
        return None
    from medops.core.config import Settings

    try:
        settings = Settings(_env_file=env_file)
    except Exception:  # noqa: BLE001 - any config problem means "no Redis here"
        return None
    return settings.redis_url.get_secret_value()


@pytest.fixture(scope="session")
def redis_url() -> str:
    """A reachable Redis for the cache-store tests: MEDOPS_TEST_REDIS_URL, else REDIS_URL from `.env`."""
    url = _redis_url()
    if not url:
        unavailable("Redis URL missing; set MEDOPS_TEST_REDIS_URL (local mode also accepts .env)")
    import redis

    error_type = None
    try:
        with redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2) as client:
            if not client.ping():
                error_type = "PingRejected"
    except (redis.RedisError, ValueError) as exc:
        error_type = type(exc).__name__
    if error_type:
        unavailable(f"Redis unavailable ({error_type}); start it with `make up`")
    return url


@pytest.fixture(scope="session")
def fresh_database(admin_dsn: str) -> Iterator[str]:
    """A brand-new database for this session, dropped afterwards."""
    with temporary_database(admin_dsn) as dsn:
        yield dsn


@pytest.fixture
def scratch_database(admin_dsn: str) -> Iterator[str]:
    """A brand-new database for one test (used for upgrade/downgrade round trips)."""
    with temporary_database(admin_dsn) as dsn:
        yield dsn


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


@pytest.fixture(scope="session")
def login_users(admin_dsn: str, migrated: str) -> Iterator[dict[str, dict[str, str]]]:
    with temporary_login_users(admin_dsn, migrated) as users:
        yield users


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    """A separate migrated fact plane and LOGIN group per requesting test module."""
    yield from make_database(admin_dsn)
