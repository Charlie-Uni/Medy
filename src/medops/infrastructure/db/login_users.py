"""Create or rotate the environment's LOGIN users for the group roles of migration 0002 (M1-08).

    python -m medops.infrastructure.db.login_users [--prefix medops]

Creates `<prefix>_app_user`, `<prefix>_readonly_user` and `<prefix>_admin_user` as LOGIN NOSUPERUSER
NOBYPASSRLS NOCREATEDB NOCREATEROLE INHERIT members of `medops_app`, `medops_readonly` and
`medops_admin_role`. Passwords come from `Settings` (DB_APP_PASSWORD, DB_READONLY_PASSWORD,
DB_ADMIN_PASSWORD in `.env` or the environment) and are never printed. Running again rotates the
passwords and re-asserts the attributes, so a role that was tampered with is repaired. The admin
connection is MEDOPS_MIGRATION_URL when set, else DATABASE_ADMIN_URL / DATABASE_URL, the same order
as migrations/env.py.

The password travels inside the SQL statement; keep `log_statement` below `all` on the server, or
rotate afterwards, as with any `ALTER ROLE ... PASSWORD`.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping

import psycopg
from psycopg import sql

from medops.core.config import Settings

GROUPS: Mapping[str, str] = {
    "app": "medops_app",
    "readonly": "medops_readonly",
    "admin": "medops_admin_role",
    "restricted": "medops_restricted_role",  # DEC-013 payload reader; optional (skipped without a password)
}
OPTIONAL_GROUPS = frozenset({"restricted"})
ATTRIBUTES = "login nosuperuser nobypassrls nocreatedb nocreaterole noreplication inherit"


class MissingGroupRoleError(RuntimeError):
    """Migration 0002 has not been applied on this cluster."""


def username(prefix: str, kind: str) -> str:
    return f"{prefix}_{kind}_user"


def provision(conn: psycopg.Connection, *, prefix: str, passwords: Mapping[str, str]) -> dict[str, str]:
    """Create or update the three login users inside the caller's transaction. Returns {kind: username}."""
    for kind in GROUPS:
        if not passwords.get(kind) and kind not in OPTIONAL_GROUPS:
            raise ValueError(f"no password for the {kind} user")
    wanted = {kind: group for kind, group in GROUPS.items() if passwords.get(kind)}
    present = {
        r[0] for r in conn.execute("select rolname from pg_roles where rolname = any(%s)", (list(wanted.values()),))
    }
    missing = sorted(set(wanted.values()) - present)
    if missing:
        raise MissingGroupRoleError(f"group roles missing, run migrations first: {missing}")
    created: dict[str, str] = {}
    for kind, group in wanted.items():
        name = username(prefix, kind)
        exists = conn.execute("select 1 from pg_roles where rolname = %s", (name,)).fetchone() is not None
        verb = "alter role" if exists else "create role"
        conn.execute(
            sql.SQL("{verb} {name} with " + ATTRIBUTES + " password {password}").format(
                verb=sql.SQL(verb), name=sql.Identifier(name), password=sql.Literal(passwords[kind])
            )
        )
        conn.execute(sql.SQL("grant {group} to {name}").format(group=sql.Identifier(group), name=sql.Identifier(name)))
        created[kind] = name
    return created


def drop_users(conn: psycopg.Connection, *, prefix: str) -> None:
    """Remove the login users (used by tests and by environment teardown). Group roles stay."""
    for kind in GROUPS:
        conn.execute(sql.SQL("drop role if exists {name}").format(name=sql.Identifier(username(prefix, kind))))


def _settings() -> Settings:
    # every field is filled from the environment / .env by pydantic-settings; mypy only sees the model signature
    return Settings()  # type: ignore[call-arg]


def _admin_url() -> str:
    explicit = os.environ.get("MEDOPS_MIGRATION_URL")
    if explicit:
        return explicit
    return (_settings().database_admin_url or _settings().database_url).get_secret_value()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medops.infrastructure.db.login_users")
    parser.add_argument("--prefix", default="medops", help="user name prefix (default medops)")
    args = parser.parse_args(argv)
    settings = _settings()
    passwords = {
        "app": settings.db_app_password.get_secret_value() if settings.db_app_password else "",
        "readonly": settings.db_readonly_password.get_secret_value() if settings.db_readonly_password else "",
        "admin": settings.db_admin_password.get_secret_value() if settings.db_admin_password else "",
        "restricted": settings.db_restricted_password.get_secret_value() if settings.db_restricted_password else "",
    }
    empty = [k for k, v in passwords.items() if not v]
    if empty:
        print(f"missing passwords for: {empty} (set DB_APP_PASSWORD / DB_READONLY_PASSWORD / DB_ADMIN_PASSWORD)")
        return 2
    with psycopg.connect(_admin_url()) as conn:
        try:
            users = provision(conn, prefix=args.prefix, passwords=passwords)
        except MissingGroupRoleError as exc:
            print(f"REFUSED: {exc}")
            return 2
        conn.commit()
    for kind, name in users.items():
        print(f"{kind}: {name} (member of {GROUPS[kind]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
