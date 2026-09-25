"""`python -m medops.application.payload_retention [--dry-run]`: purge expired restricted payloads (DEC-013) on the
restricted role. Deleting a row discards its DEK; traces with an open escalation are kept, closed ones for
`ESCALATION_PAYLOAD_GRACE_DAYS` after `handled_at`."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import psycopg

from medops.application.payloads import purge_expired
from medops.core.config import Settings
from medops.infrastructure.db.payloads import PgPayloadStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="medops.application.payload_retention")
    ap.add_argument("--dry-run", action="store_true", help="count the rows that would be deleted, then roll back")
    args = ap.parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    if settings.database_restricted_url is None:
        print("DATABASE_RESTRICTED_URL is required (restricted role)", file=sys.stderr)
        return 2
    with psycopg.connect(settings.database_restricted_url.get_secret_value()) as conn:
        with conn.transaction(force_rollback=args.dry_run):
            deleted = purge_expired(
                PgPayloadStore(conn),
                now=datetime.now(UTC),
                escalation_grace_days=settings.escalation_payload_grace_days,
            )
    print(f"{'would delete' if args.dry_run else 'deleted'} {deleted} expired payload rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
