"""Allowlisted free maintenance jobs, with explicit database and separate role credentials.

Only Observe collects Loop signals automatically. Candidate generation/evaluation/activation are not scheduled.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

from medops.application.payloads import purge_expired
from medops.application.retention import purge
from medops.core.config import Settings
from medops.infrastructure.db.payloads import PgPayloadStore
from medops.loop.observe import PgCaseStore, PgSignalSource, observe
from medops.worker.supervision import pulse

JOBS = {
    "payload-retention": "database_restricted_url",
    "audit-retention": "database_admin_url",
    "loop-observe": "database_loop_url",
}


def execute(conn: Any, settings: Settings, *, job: str, since: datetime | None, dry_run: bool) -> dict[str, Any]:
    # Duplicate schedules serialize by database/job; no role switch and no lock held while sleeping.
    if not conn.execute(
        "select pg_try_advisory_xact_lock(hashtextextended(%s,0))", (f"medops-maintenance:{job}",)
    ).fetchone()[0]:
        return {"status": "already_running"}
    if job == "payload-retention":
        return {
            "deleted": purge_expired(
                PgPayloadStore(conn),
                now=datetime.now(UTC),
                escalation_grace_days=settings.escalation_payload_grace_days,
            )
        }
    if job == "audit-retention":
        return asdict(purge(conn, days=settings.trace_retention_days, dry_run=dry_run))
    if job == "loop-observe" and since is not None:
        return asdict(observe(PgSignalSource(conn), PgCaseStore(conn), since=since))
    raise ValueError("job or observation boundary invalid")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", required=True)
    ap.add_argument("--job", required=True, choices=JOBS)
    ap.add_argument("--since", help="fixed UTC scan boundary for Observe; include retained traces with late feedback")
    ap.add_argument("--dry-run", action="store_true", help="execute and roll back all database changes")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", args.database):
        ap.error("invalid explicit database name")
    since = None
    if args.job == "loop-observe":
        try:
            since = datetime.fromisoformat(args.since) if args.since else None
            if since is None:
                raise ValueError("boundary required")
            since = since.replace(tzinfo=UTC) if since.tzinfo is None else since.astimezone(UTC)
        except ValueError:
            ap.error("loop-observe requires a valid --since UTC date/datetime")
    elif args.since:
        ap.error("--since only applies to loop-observe")
    try:
        settings = Settings()  # type: ignore[call-arg]
        credential = getattr(settings, JOBS[args.job])
        if credential is None:
            raise ValueError("maintenance role credential required")
        dsn = make_conninfo(credential.get_secret_value(), dbname=args.database)
        with psycopg.connect(
            dsn,
            connect_timeout=settings.db_connect_timeout_s,
            options=f"-c statement_timeout={settings.db_statement_timeout_ms} -c lock_timeout=5000",
        ) as conn:
            with conn.transaction(force_rollback=args.dry_run):
                result = execute(conn, settings, job=args.job, since=since, dry_run=args.dry_run)
        pulse()
        print(json.dumps({"job": args.job, "dry_run": args.dry_run, **result}), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 - safe deployment diagnostics only
        print(json.dumps({"job": args.job, "status": "job_failed", "error_type": type(exc).__name__}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
