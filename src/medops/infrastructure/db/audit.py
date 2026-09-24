"""PostgreSQL trace store (migration 0011) for `medops.application.audit`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from medops.application.audit import (
    EscalationRecord,
    FeedbackRecord,
    IdempotencyRace,
    ReplayRecord,
    TraceRecord,
    TraceSummary,
)
from medops.domain.common import Dept


class PgTraceStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def record(self, trace: TraceRecord, escalation: EscalationRecord | None) -> None:
        self._conn.execute(
            """
            insert into traces (trace_id, run_id, kind, task_id, principal, dept, query, outcome, reason_codes, versions,
                                evidence_chunk_ids, cited_chunk_ids, flagged_chunk_ids, model_calls, tokens, cost_usd, duration_ms)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trace.trace_id,
                trace.run_id,
                trace.kind,
                trace.task_id,
                trace.principal,
                trace.dept.value,
                trace.query,
                trace.outcome,
                list(trace.reason_codes),
                Jsonb(dict(trace.versions)),
                list(trace.evidence_chunk_ids),
                list(trace.cited_chunk_ids),
                list(trace.flagged_chunk_ids),
                trace.model_calls,
                trace.tokens,
                round(trace.cost_usd, 6),
                trace.duration_ms,
            ),
        )
        if trace.spans:
            with self._conn.cursor() as cur:
                cur.executemany(
                    "insert into trace_spans (trace_id, node, attempt, operation_key, outcome, error_code, started_at, duration_ms) values (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (
                            trace.trace_id,
                            a.node,
                            a.attempt,
                            a.operation_key,
                            a.outcome,
                            a.error_code,
                            a.started_at,
                            a.duration_ms,
                        )
                        for a in trace.spans
                    ],
                )
        if escalation is not None:
            self._conn.execute(
                """
                insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, evidence_chunk_ids,
                                         verify_result, safety_result, policy_version, detail)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    escalation.escalation_id,
                    escalation.trace_id,
                    escalation.principal,
                    escalation.dept.value,
                    list(escalation.reason_codes),
                    escalation.query,
                    list(escalation.evidence_chunk_ids),
                    Jsonb(dict(escalation.verify_result)) if escalation.verify_result is not None else None,
                    Jsonb(dict(escalation.safety_result)) if escalation.safety_result is not None else None,
                    escalation.policy_version,
                    escalation.detail,
                ),
            )

    def trace_principal(self, trace_id: str) -> str | None:
        row = self._conn.execute("select principal from traces where trace_id = %s", (trace_id,)).fetchone()
        return row[0] if row else None

    def read_trace(self, trace_id: str) -> TraceSummary | None:
        row = self._conn.execute(
            "select trace_id, run_id, kind, principal, dept::text, query, outcome, reason_codes, versions, evidence_chunk_ids, cited_chunk_ids from traces where trace_id = %s",
            (trace_id,),
        ).fetchone()
        if row is None:
            return None
        return TraceSummary(
            trace_id=row[0],
            run_id=row[1],
            kind=row[2],
            principal=row[3],
            dept=Dept(row[4]),
            query=row[5],
            outcome=row[6],
            reason_codes=tuple(row[7]),
            versions=row[8],
            evidence_chunk_ids=tuple(row[9]),
            cited_chunk_ids=tuple(row[10]),
        )

    def record_replay(self, record: ReplayRecord) -> None:
        self._conn.execute(
            "insert into replays (replay_id, source_trace_id, replay_trace_id, replay_run_id, requested_by, reason, versions_match, changed, report) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                record.replay_id,
                record.source_trace_id,
                record.replay_trace_id,
                record.replay_run_id,
                record.requested_by,
                record.reason,
                record.versions_match,
                list(record.changed),
                Jsonb(dict(record.report)),
            ),
        )

    def find_receipt(self, principal: str, route: str, key: str) -> tuple[str, Mapping[str, Any]] | None:
        row = self._conn.execute(
            "select request_hash, receipt from idempotency_keys where principal = %s and route = %s and key = %s and expires_at > now() and receipt is not null",
            (principal, route, key),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def add_feedback(
        self, record: FeedbackRecord, idempotency: tuple[str, str, str, datetime, Mapping[str, Any]] | None
    ) -> None:
        try:
            with self._conn.transaction():
                self._conn.execute(
                    "insert into feedback (feedback_id, trace_id, principal, signal, correction_text, created_at) values (%s, %s, %s, %s, %s, %s)",
                    (
                        record.feedback_id,
                        record.trace_id,
                        record.principal,
                        record.signal,
                        record.correction_text,
                        record.created_at,
                    ),
                )
                if idempotency is not None:
                    route, key, request_hash, expires, receipt = idempotency
                    self._conn.execute(
                        "insert into idempotency_keys (principal, route, key, request_hash, receipt, expires_at) values (%s, %s, %s, %s, %s, %s)",
                        (record.principal, route, key, request_hash, Jsonb(dict(receipt)), expires),
                    )
        except UniqueViolation:
            raise IdempotencyRace() from None
