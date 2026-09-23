"""Migration 0009 `principals` on the real schema: the application role can only read it, the admin role
manages it, the read-only role has no access, rows are deactivated rather than deleted, identity columns are
immutable, and `PgDirectory` resolves a pseudonym to department, roles and scopes."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from psycopg.errors import CheckViolation, InsufficientPrivilege, RestrictViolation

from medops.api.auth import PgDirectory, pseudonym
from medops.domain.common import Dept
from tests.integration.lexical_adapter_suite import make_database

KEY = b"integration-pseudonym-key"


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


def test_admin_provisions_app_reads_readonly_denied(db):
    pid = pseudonym("user-42", KEY)
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute(
            "insert into principals (sub_pseudonym, dept, roles, scopes, created_by) values (%s, 'PV', %s, %s, 'test')",
            (pid, ["analyst"], ["PV:read", "PV:export"]),
        )
        admin.commit()
    with psycopg.connect(db["users"]["app"]) as app:
        principal = PgDirectory(app).resolve(pid)
        assert (
            principal is not None
            and principal.dept is Dept.PV
            and principal.scopes == frozenset({"PV:read", "PV:export"})
        )
        assert PgDirectory(app).resolve(pseudonym("nobody", KEY)) is None
        with pytest.raises(InsufficientPrivilege):
            app.execute("update principals set active = false where sub_pseudonym = %s", (pid,))
        app.rollback()
    with psycopg.connect(db["users"]["readonly"]) as ro:
        with pytest.raises(InsufficientPrivilege):
            ro.execute("select count(*) from principals")


def test_rows_are_deactivated_not_deleted_and_identity_is_immutable(db):
    pid = pseudonym("user-43", KEY)
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute("insert into principals (sub_pseudonym, dept, created_by) values (%s, 'MA', 'test')", (pid,))
        admin.commit()
        with pytest.raises(
            (RestrictViolation, InsufficientPrivilege)
        ):  # no DELETE grant, and the trigger refuses anyway
            admin.execute("delete from principals where sub_pseudonym = %s", (pid,))
        admin.rollback()
        with pytest.raises(RestrictViolation):
            admin.execute(
                "update principals set sub_pseudonym = %s where sub_pseudonym = %s", (pseudonym("x", KEY), pid)
            )
        admin.rollback()
        admin.execute("update principals set active = false where sub_pseudonym = %s", (pid,))
        admin.commit()
    with psycopg.connect(db["users"]["app"]) as app:
        principal = PgDirectory(app).resolve(pid)
        assert principal is not None and principal.active is False


def test_scopes_and_pseudonym_shape_are_checked(db):
    with psycopg.connect(db["users"]["admin"]) as admin:
        with pytest.raises(CheckViolation):
            admin.execute(
                "insert into principals (sub_pseudonym, dept, scopes, created_by) values (%s, 'CO', %s, 'test')",
                (pseudonym("u", KEY), ["everyone:read"]),
            )
        admin.rollback()
        with pytest.raises(CheckViolation):
            admin.execute(
                "insert into principals (sub_pseudonym, dept, created_by) values ('raw-subject', 'CO', 'test')"
            )
        admin.rollback()
