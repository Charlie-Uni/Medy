"""Retention purge for the audit tables (M5-06, record 87; decision 86 item 4: traces and escalations 365 days).

The tables are append-only for every role; migration 0019 opens one controlled path: inside a transaction that sets
`medops.retention_purge = on` and `medops.retention_days = N` (floor 90), the admin role may delete rows older than N
days. This module is that transaction. It never touches `payload_access_log` (who read a payload and why) or
`document_requests` (tickets), and it keeps every trace that still has an open escalation or a case with a ticket.

Deletion order follows the foreign keys: payloads -> cases -> replays -> feedback -> escalations -> spans -> traces.

    python -m medops.application.retention [--days 365] [--dry-run]        (DATABASE_ADMIN_URL)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

MIN_DAYS = 90

_OLD_TRACES = """
create temporary table retention_old on commit drop as
select t.trace_id
  from traces t
 where t.created_at < now() - make_interval(days => %(days)s)
   and not exists (select 1 from escalations e where e.trace_id = t.trace_id and e.status <> 'closed')
   and not exists (
        select 1 from bad_cases c join document_requests d on d.case_id = c.case_id where c.trace_id = t.trace_id)
   and not exists (
        select 1 from replays r join traces rt on rt.trace_id = r.replay_trace_id
         where r.source_trace_id = t.trace_id and rt.created_at >= now() - make_interval(days => %(days)s))
"""

_STEPS: tuple[tuple[str, str], ...] = (
    ("trace_payloads", "delete from trace_payloads where trace_id in (select trace_id from retention_old)"),
    ("bad_cases", "delete from bad_cases where trace_id in (select trace_id from retention_old)"),
    (
        "replays",
        "delete from replays where source_trace_id in (select trace_id from retention_old) "
        "or replay_trace_id in (select trace_id from retention_old)",
    ),
    ("feedback", "delete from feedback where trace_id in (select trace_id from retention_old)"),
    ("escalations", "delete from escalations where trace_id in (select trace_id from retention_old)"),
    ("trace_spans", "delete from trace_spans where trace_id in (select trace_id from retention_old)"),
    ("traces", "delete from traces where trace_id in (select trace_id from retention_old)"),
)


@dataclass
class PurgeReport:
    days: int
    dry_run: bool
    candidates: int = 0
    deleted: dict[str, int] = field(default_factory=dict)


def purge(conn: Any, *, days: int, dry_run: bool = False) -> PurgeReport:
    """Runs inside the caller's transaction on the admin role; the caller commits or rolls back (`dry_run` is recorded
    in the report only)."""
    if days < MIN_DAYS:
        raise ValueError(f"retention must be at least {MIN_DAYS} days")
    conn.execute("select set_config('medops.retention_purge', 'on', true)")
    conn.execute("select set_config('medops.retention_days', %s, true)", (str(days),))
    conn.execute(_OLD_TRACES, {"days": days})
    report = PurgeReport(days=days, dry_run=dry_run)
    report.candidates = int(conn.execute("select count(*) from retention_old").fetchone()[0])
    for table, sql in _STEPS:
        report.deleted[table] = conn.execute(sql).rowcount
    return report  # the caller commits, or rolls back for a dry run


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from medops.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    ap = argparse.ArgumentParser(description="retention purge of audit rows older than N days (admin role)")
    ap.add_argument("--days", type=int, default=settings.trace_retention_days)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if settings.database_admin_url is None:
        print("DATABASE_ADMIN_URL is not configured", file=sys.stderr)
        return 2
    conn = psycopg.connect(
        settings.database_admin_url.get_secret_value(),
        connect_timeout=settings.db_connect_timeout_s,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    )
    try:
        report = purge(conn, days=args.days, dry_run=args.dry_run)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()
    print(json.dumps(asdict(report), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
