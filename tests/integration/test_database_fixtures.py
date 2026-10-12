"""Real PostgreSQL cleanup during setup failure, body failure and overlapping fixture lifetimes."""

from contextlib import ExitStack, closing
from urllib.parse import urlsplit

import psycopg
import pytest

from medops.infrastructure.db.login_users import GROUPS, username
from tests.support import database
from tests.support.documents import source_object


@pytest.fixture
def owned_resources(monkeypatch):
    """Track this test's generated names; parallel suites must not affect its assertions."""
    databases, users = set(), set()
    original_database = database.with_database
    original_username = database.username

    def track_database(dsn, name):
        databases.add(name)
        return original_database(dsn, name)

    def track_username(prefix, kind):
        value = original_username(prefix, kind)
        users.add(value)
        return value

    monkeypatch.setattr(database, "with_database", track_database)
    monkeypatch.setattr(database, "username", track_username)
    return databases, users


def resources(admin_dsn, owned):
    with psycopg.connect(admin_dsn) as conn:
        databases = {
            r[0] for r in conn.execute("select datname from pg_database where datname = any(%s)", (list(owned[0]),))
        }
        users = {r[0] for r in conn.execute("select rolname from pg_roles where rolname = any(%s)", (list(owned[1]),))}
        return databases, users


def test_two_live_databases_and_login_groups_are_isolated_and_cleaned(admin_dsn, owned_resources):
    before = resources(admin_dsn, owned_resources)
    with ExitStack() as stack:
        first = next(stack.enter_context(closing(database.make_database(admin_dsn))))
        second = next(stack.enter_context(closing(database.make_database(admin_dsn))))
        assert first["owner"] != second["owner"] and set(first["users"]) == set(second["users"]) == set(GROUPS)
        first_names = {urlsplit(dsn).username for dsn in first["users"].values()}
        second_names = {urlsplit(dsn).username for dsn in second["users"].values()}
        assert first_names.isdisjoint(second_names)
        with psycopg.connect(first["owner"]) as conn:
            source_object(conn, 941301)
        with psycopg.connect(second["owner"]) as conn:
            assert conn.execute("select count(*) from source_objects").fetchone()[0] == 0
        # An unclosed LOGIN connection is terminated by resource cleanup.
        live = psycopg.connect(first["users"]["app"])
    try:
        assert resources(admin_dsn, owned_resources) == before
        with pytest.raises(psycopg.Error):
            live.execute("select 1")
    finally:
        live.close()


@pytest.mark.parametrize("fault", ["migration", "provision", "dsn", "body"])
def test_setup_and_body_failures_remove_all_owned_resources(admin_dsn, monkeypatch, fault, owned_resources):
    before = resources(admin_dsn, owned_resources)

    def fail(*args, **kwargs):
        raise RuntimeError("injected fixture setup failure")

    if fault == "migration":
        monkeypatch.setattr(database, "run_alembic", fail)
    elif fault == "provision":
        original = database.provision

        def partial(conn, **kwargs):
            original(conn, **kwargs)
            fail()

        monkeypatch.setattr(database, "provision", partial)
    elif fault == "dsn":
        monkeypatch.setattr(database, "user_dsn", fail)
    with pytest.raises(RuntimeError, match="injected fixture setup failure"):
        with closing(database.make_database(admin_dsn)) as generated:
            next(generated)
            fail()
    assert resources(admin_dsn, owned_resources) == before


def test_database_cleanup_still_runs_when_login_teardown_fails(admin_dsn, monkeypatch, owned_resources):
    before_databases, before_users = resources(admin_dsn, owned_resources)
    original = database.drop_users
    prefixes = []

    def fail_drop(conn, *, prefix):
        prefixes.append(prefix)
        raise RuntimeError("injected role cleanup failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(database, "drop_users", fail_drop)
            with pytest.raises(RuntimeError, match="injected role cleanup failure"):
                with closing(database.make_database(admin_dsn)) as generated:
                    next(generated)
        after_databases, after_users = resources(admin_dsn, owned_resources)
        assert after_databases == before_databases
        assert len(prefixes) == 1
        assert after_users - before_users == {username(prefixes[0], kind) for kind in GROUPS}
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            for prefix in prefixes:
                original(conn, prefix=prefix)
    assert resources(admin_dsn, owned_resources) == (before_databases, before_users)


db_other = database.database_fixture("admin_dsn")


def test_factory_and_default_fixture_keep_variant_databases_separate(db, db_other):
    assert db["owner"] != db_other["owner"]
    with psycopg.connect(db["owner"]) as conn:
        source_object(conn, 941302)
    with psycopg.connect(db_other["owner"]) as conn:
        assert conn.execute("select count(*) from source_objects").fetchone()[0] == 0
