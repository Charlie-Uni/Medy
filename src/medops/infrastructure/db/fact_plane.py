"""Persistent audit identity and an explicit, privileged independent-clone operation.

python -m medops.infrastructure.db.fact_plane --database NAME
prints metadata only. --rotate-clone --expected-id UUID changes only the explicitly
selected clone's identity; never use this on a disaster-recovery replacement.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

from medops.core.config import Settings


def canonical_fact_plane_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("invalid fact-plane UUID") from None
    if not parsed.int or str(parsed) != value:
        raise ValueError("invalid fact-plane UUID")
    return value


def fact_plane_identity(conn: psycopg.Connection[Any], *, expected: str | None = None) -> str:
    """Fail closed if migration/identity is absent; never fall back to address or uptime."""
    if expected is not None:
        canonical_fact_plane_id(expected)
    row = conn.execute("select fact_plane_id::text from fact_plane_identity where singleton").fetchone()
    if row is None:
        raise ValueError("fact-plane identity unavailable")
    identity = canonical_fact_plane_id(row[0])
    if expected is not None and identity != expected:
        raise ValueError("fact-plane identity does not match the deployment binding")
    return identity


def rotate_clone_identity(conn: psycopg.Connection[Any], *, expected: str) -> str:
    """CAS under a row lock; normal app/admin/loop roles have no identity write privilege."""
    canonical_fact_plane_id(expected)
    row = conn.execute(
        "select (rolsuper or rolbypassrls) and "
        "pg_has_role(current_user, (select relowner from pg_class "
        "where oid='fact_plane_identity'::regclass), 'USAGE') "
        "from pg_roles where rolname=current_user"
    ).fetchone()
    if not row or not row[0]:
        raise ValueError("clone rotation requires the migration owner with RLS bypass")
    conn.execute("select singleton from fact_plane_identity where singleton for update").fetchone()
    fact_plane_identity(conn, expected=expected)
    new_id = str(uuid.uuid4())
    conn.execute("update fact_plane_identity set fact_plane_id=%s,created_at=now() where singleton", (new_id,))
    return new_id


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", required=True, help="explicit database; no implicit default")
    ap.add_argument("--rotate-clone", action="store_true", help="independent clone only; do not rotate a recovery")
    ap.add_argument("--expected-id", help="deployment UUID; required for clone rotation")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", args.database):
        ap.error("invalid explicit database name")
    if args.rotate_clone and not args.expected_id:
        ap.error("clone rotation requires --expected-id")
    try:
        settings = Settings()  # type: ignore[call-arg]
        if settings.database_admin_url is None:
            raise ValueError("database administration configuration absent")
        dsn = make_conninfo(settings.database_admin_url.get_secret_value(), dbname=args.database)
        with psycopg.connect(dsn, connect_timeout=5, options="-c statement_timeout=5000") as conn:
            conn.read_only = not args.rotate_clone
            identity = (
                rotate_clone_identity(conn, expected=args.expected_id)
                if args.rotate_clone
                else fact_plane_identity(conn, expected=args.expected_id)
            )
        print(
            json.dumps(
                {
                    "fact_plane_id": identity,
                    "rotated_clone": args.rotate_clone,
                    "previous_id": args.expected_id if args.rotate_clone else None,
                }
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - never print DSNs, database bodies or credentials
        print(json.dumps({"status": "identity_operation_failed", "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
