"""Knowledge-gap tickets (M4-05, record 80): the only thing the Loop does with a knowledge gap is ask for a document.

A ticket carries the question (the trace query, capped) and a one-line gap description built from the case's
attribution note; it never carries an answer, a summary or any medical content (baseline 5.8: "不能生成事实"). One
ticket per case; humans (admin role) accept / reject / fulfil it and may link the document that closed the gap.

    python -m medops.loop.tickets [--dry-run]        (DATABASE_LOOP_URL)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from medops.loop.reflect import effective_attribution

TOPIC_MAX = 500
GAP_MAX = 500


@dataclass(frozen=True)
class Ticket:
    case_id: str
    dept: str
    topic: str
    gap: str


def build_ticket(case: dict[str, Any], *, query: str) -> Ticket | None:
    """None unless the case's effective attribution is knowledge_gap."""
    if effective_attribution(case) != "knowledge_gap":
        return None
    topic = " ".join(str(query).split())[:TOPIC_MAX] or "(empty question)"
    note = str(case.get("attribution_note") or "no evidence found for the question")
    override = case.get("human_override") or {}
    if isinstance(override, dict) and override.get("note"):
        note = str(override["note"])
    gap = f"knowledge gap ({case['dept']}): {note}"[:GAP_MAX]
    return Ticket(case_id=str(case["case_id"]), dept=str(case["dept"]), topic=topic, gap=gap)


@dataclass
class TicketReport:
    scanned: int = 0
    opened: int = 0
    already_open: int = 0
    not_knowledge_gap: int = 0


_CASES_SQL = """
select c.case_id::text, c.dept::text, c.attribution, c.attribution_note, c.human_override, t.query
  from bad_cases c join traces t on t.trace_id = c.trace_id
 where c.label = 'bad' and c.status in ('attributed', 'corrected')
 order by c.opened_at, c.case_id
"""


def open_tickets(conn: Any, *, requested_by: str = "loop:tickets-v1") -> TicketReport:
    report = TicketReport()
    for case_id, dept, attribution, note, override, query in conn.execute(_CASES_SQL).fetchall():
        report.scanned += 1
        case = {
            "case_id": case_id,
            "dept": dept,
            "attribution": attribution,
            "attribution_note": note,
            "human_override": override,
        }
        ticket = build_ticket(case, query=query)
        if ticket is None:
            report.not_knowledge_gap += 1
            continue
        row = conn.execute(
            "insert into document_requests (case_id, dept, topic, gap, requested_by) values (%s::uuid, %s::dept, %s, %s, %s) "
            "on conflict (case_id) do nothing returning request_id",
            (ticket.case_id, ticket.dept, ticket.topic, ticket.gap, requested_by),
        ).fetchone()
        if row is None:
            report.already_open += 1
        else:
            report.opened += 1
    return report


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from medops.core.config import Settings

    ap = argparse.ArgumentParser(description="open document tickets for knowledge-gap cases (Loop role)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    if settings.database_loop_url is None:
        print("DATABASE_LOOP_URL is not configured", file=sys.stderr)
        return 2
    with (
        psycopg.connect(
            settings.database_loop_url.get_secret_value(),
            connect_timeout=settings.db_connect_timeout_s,
            options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
        ) as conn,
        conn.transaction(),
    ):
        report = open_tickets(conn)
        if args.dry_run:
            conn.rollback()
    print(json.dumps(asdict(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
