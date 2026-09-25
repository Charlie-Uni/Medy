"""Observe (M4-01, record 79): turn the signals attached to a trace into a Loop case.

The signals are what `trace_signals` (migration 0016) joins onto each trace: user feedback (down votes and
corrections), verifier failures, safety flags, the escalation and its human resolution, and replay drift. Execute
writes the traces; Observe reads this one view, so both sides share a single data source (baseline 5.8).

Labels are deliberately narrow:

- `bad`: any negative signal — a down vote or correction, a verifier failure, a safety flag, an evidence-based
  escalation of a question (a knowledge-gap or retrieval candidate), a resolved escalation (either a confirmed issue or
  an over-strict false alarm: both are Loop material) or a replay that no longer matches;
- `good`: an answered trace with an explicit up vote and no negative signal;
- otherwise no case: an answered trace nobody reacted to is not evidence of anything, and `system_failure`
  escalations are infrastructure, not Loop material.

Replay and MCP traces never open cases (they are diagnostics / read-only tool calls). Opening a case is idempotent per
trace; the snapshot of the signals that opened it is frozen on the case (the 0016 guard makes it immutable).

    python -m medops.loop.observe --since 2026-09-25 [--dept MA] [--dry-run]   (runs on DATABASE_LOOP_URL)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

Label = Literal["bad", "good"]

CASE_KINDS = frozenset({"ask", "task"})
NON_LOOP_ESCALATION_CODES = frozenset({"system_failure", "budget_exceeded"})


@dataclass(frozen=True)
class TraceSignals:
    """One row of `trace_signals` (only the columns Observe reasons about)."""

    trace_id: str
    kind: str
    dept: str
    outcome: str
    reason_codes: tuple[str, ...]
    created_at: datetime
    feedback_up: int = 0
    feedback_down: int = 0
    feedback_corrections: int = 0
    escalation_status: str | None = None
    escalation_reason_codes: tuple[str, ...] = ()
    escalation_resolution: str | None = None
    verifier_failed: bool = False
    safety_flagged: bool = False
    replay_count: int = 0
    replay_changed: bool = False


@dataclass(frozen=True)
class Case:
    trace_id: str
    dept: str
    label: Label
    reasons: tuple[str, ...]
    signals: dict[str, Any]
    opened_at: datetime


@dataclass
class ObserveReport:
    scanned: int = 0
    opened: int = 0
    already_open: int = 0
    skipped_no_signal: int = 0
    skipped_kind: int = 0
    by_label: dict[str, int] = field(default_factory=dict)
    by_reason: dict[str, int] = field(default_factory=dict)


def classify(s: TraceSignals) -> tuple[Label | None, tuple[str, ...]]:
    """The labelling rules, in one place and pure (unit-tested as a table)."""
    if s.kind not in CASE_KINDS:
        return None, ()
    reasons: list[str] = []
    if s.feedback_down:
        reasons.append("feedback_down")
    if s.feedback_corrections:
        reasons.append("feedback_correction")
    if s.verifier_failed:
        reasons.append("verifier_failed")
    if s.safety_flagged:
        reasons.append("safety_flagged")
    if s.escalation_status is not None:
        codes = set(s.escalation_reason_codes)
        if s.escalation_resolution == "confirmed_issue":
            reasons.append("escalation_confirmed_issue")
        elif s.escalation_resolution == "false_alarm":
            reasons.append("escalation_false_alarm")
        elif "insufficient_evidence" in codes and s.kind == "ask" and not codes & NON_LOOP_ESCALATION_CODES:
            reasons.append("escalated_insufficient_evidence")
    if s.replay_changed:
        reasons.append("replay_drift")
    if reasons:
        return "bad", tuple(reasons)
    if s.outcome == "answered" and s.feedback_up:
        return "good", ("feedback_up",)
    return None, ()


def snapshot(s: TraceSignals) -> dict[str, Any]:
    d = asdict(s)
    d["created_at"] = s.created_at.isoformat()
    d["reason_codes"] = list(s.reason_codes)
    d["escalation_reason_codes"] = list(s.escalation_reason_codes)
    return d


class SignalSource(Protocol):
    def since(self, start: datetime, *, dept: str | None = None) -> Sequence[TraceSignals]: ...


class CaseStore(Protocol):
    def open(self, case: Case) -> bool:
        """Insert the case unless one exists for the trace; True when inserted."""
        ...


def observe(
    source: SignalSource, store: CaseStore, *, since: datetime, dept: str | None = None, now: datetime | None = None
) -> ObserveReport:
    now = now or datetime.now(UTC)
    report = ObserveReport()
    for s in source.since(since, dept=dept):
        report.scanned += 1
        if s.kind not in CASE_KINDS:
            report.skipped_kind += 1
            continue
        label, reasons = classify(s)
        if label is None:
            report.skipped_no_signal += 1
            continue
        case = Case(trace_id=s.trace_id, dept=s.dept, label=label, reasons=reasons, signals=snapshot(s), opened_at=now)
        if store.open(case):
            report.opened += 1
            report.by_label[label] = report.by_label.get(label, 0) + 1
            for r in reasons:
                report.by_reason[r] = report.by_reason.get(r, 0) + 1
        else:
            report.already_open += 1
    return report


# ------------------------------------------------------------------------------------------ PostgreSQL

_COLUMNS = (
    "trace_id, kind, dept::text, outcome, reason_codes, created_at, feedback_up, feedback_down, feedback_corrections, "
    "escalation_status, escalation_reason_codes, escalation_resolution, verifier_failed, safety_flagged, "
    "replay_count, replay_changed"
)


def _row(r: Sequence[Any]) -> TraceSignals:
    return TraceSignals(
        trace_id=r[0],
        kind=r[1],
        dept=r[2],
        outcome=r[3],
        reason_codes=tuple(r[4] or ()),
        created_at=r[5],
        feedback_up=int(r[6] or 0),
        feedback_down=int(r[7] or 0),
        feedback_corrections=int(r[8] or 0),
        escalation_status=r[9],
        escalation_reason_codes=tuple(r[10] or ()),
        escalation_resolution=r[11],
        verifier_failed=bool(r[12]),
        safety_flagged=bool(r[13]),
        replay_count=int(r[14] or 0),
        replay_changed=bool(r[15]),
    )


class PgSignalSource:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def since(self, start: datetime, *, dept: str | None = None) -> list[TraceSignals]:
        sql = f"select {_COLUMNS} from trace_signals where created_at >= %(start)s"
        params: dict[str, Any] = {"start": start}
        if dept is not None:
            sql += " and dept = %(dept)s::dept"
            params["dept"] = dept
        sql += " order by created_at, trace_id"
        return [_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def for_trace(self, trace_id: str) -> TraceSignals | None:
        row = self._conn.execute(f"select {_COLUMNS} from trace_signals where trace_id = %s", (trace_id,)).fetchone()
        return _row(row) if row else None


class PgCaseStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def open(self, case: Case) -> bool:
        from psycopg.types.json import Jsonb

        row = self._conn.execute(
            """
            insert into bad_cases (trace_id, dept, opened_at, signals, label, reasons)
            values (%s, %s::dept, %s, %s, %s, %s)
            on conflict (trace_id) do nothing
            returning case_id
            """,
            (case.trace_id, case.dept, case.opened_at, Jsonb(case.signals), case.label, list(case.reasons)),
        ).fetchone()
        return row is not None

    def list(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = (
            "select case_id::text, trace_id, dept::text, opened_at, label, reasons, attribution, confidence, "
            "attributed_by, status from bad_cases"
        )
        params: list[Any] = []
        if status is not None:
            sql += " where status = %s"
            params.append(status)
        sql += " order by opened_at desc limit %s"
        params.append(limit)
        cols = (
            "case_id",
            "trace_id",
            "dept",
            "opened_at",
            "label",
            "reasons",
            "attribution",
            "confidence",
            "attributed_by",
            "status",
        )
        return [dict(zip(cols, r, strict=True)) for r in self._conn.execute(sql, params).fetchall()]


class InMemoryCaseStore:
    def __init__(self) -> None:
        self.cases: dict[str, Case] = {}

    def open(self, case: Case) -> bool:
        if case.trace_id in self.cases:
            return False
        self.cases[case.trace_id] = case
        return True


class StaticSignalSource:
    def __init__(self, rows: Iterable[TraceSignals]) -> None:
        self._rows = list(rows)

    def since(self, start: datetime, *, dept: str | None = None) -> list[TraceSignals]:
        return [r for r in self._rows if r.created_at >= start and (dept is None or r.dept == dept)]


# ------------------------------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from medops.core.config import Settings

    ap = argparse.ArgumentParser(description="Observe: open Loop cases from trace signals (Loop database role)")
    ap.add_argument("--since", required=True, help="ISO date or datetime (UTC) from which traces are scanned")
    ap.add_argument("--dept", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    if settings.database_loop_url is None:
        print("DATABASE_LOOP_URL is not configured", file=sys.stderr)
        return 2
    since = datetime.fromisoformat(args.since)  # a bare date parses as midnight
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    with psycopg.connect(
        settings.database_loop_url.get_secret_value(),
        connect_timeout=settings.db_connect_timeout_s,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    ) as conn:
        with conn.transaction():
            report = observe(PgSignalSource(conn), PgCaseStore(conn), since=since, dept=args.dept)
            if args.dry_run:
                conn.rollback()
    print(json.dumps(asdict(report), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
