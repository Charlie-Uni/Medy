"""Operational metrics (M3-10 first slice) computed from the audit and task tables, exposed in the Prometheus
text format. Labels are low-cardinality only (kind, outcome, reason code, status); trace ids and principals
never become labels (baseline 5.10). Numbers are windowed aggregates over PostgreSQL, so every API replica
reports the same values and nothing is lost on restart."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

WINDOW_MINUTES = 60


@dataclass(frozen=True)
class MetricsSnapshot:
    window_minutes: int
    requests: Mapping[tuple[str, str], int]  # (kind, outcome) -> count in window
    escalations: Mapping[str, int]  # reason code -> count in window
    open_escalations: int
    duration_ms_quantiles: Mapping[tuple[str, str], float]  # (kind, quantile) -> ms in window
    model_calls: int
    tokens: int
    cost_usd_window: float
    cost_usd_month: float
    tasks_by_status: Mapping[str, int]
    oldest_queued_age_s: float
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    retrieval_integrity: Mapping[str, Any] | None = None


class MetricsSource(Protocol):
    def snapshot(self, *, window_minutes: int, now: datetime) -> MetricsSnapshot: ...


class PgMetricsSource:
    def __init__(self, conn: Any, *, retrieval_integrity: Callable[[], Mapping[str, Any]] | None = None) -> None:
        self._conn = conn
        self._retrieval_integrity = retrieval_integrity

    def snapshot(self, *, window_minutes: int = WINDOW_MINUTES, now: datetime | None = None) -> MetricsSnapshot:
        now = now or datetime.now(UTC)
        params = {"now": now, "mins": window_minutes}
        req = self._conn.execute(
            "select kind, outcome, count(*) from traces where created_at > %(now)s - make_interval(mins => %(mins)s) group by 1, 2",
            params,
        ).fetchall()
        esc = self._conn.execute(
            "select c, count(*) from escalations, unnest(reason_codes) c where created_at > %(now)s - make_interval(mins => %(mins)s) group by 1",
            params,
        ).fetchall()
        open_esc = self._conn.execute("select count(*) from escalations where status = 'open'").fetchone()[0]
        quant = self._conn.execute(
            """
            select kind, percentile_cont(0.5) within group (order by duration_ms), percentile_cont(0.95) within group (order by duration_ms)
              from traces where created_at > %(now)s - make_interval(mins => %(mins)s) group by kind
            """,
            params,
        ).fetchall()
        usage = self._conn.execute(
            "select coalesce(sum(model_calls), 0), coalesce(sum(tokens), 0), coalesce(sum(cost_usd), 0) from traces where created_at > %(now)s - make_interval(mins => %(mins)s)",
            params,
        ).fetchone()
        month = self._conn.execute(
            "select coalesce(sum(cost_usd), 0) from traces where created_at >= date_trunc('month', %(now)s::timestamptz)",
            params,
        ).fetchone()[0]
        tasks = self._conn.execute("select status, count(*) from tasks group by 1").fetchall()
        oldest = self._conn.execute(
            "select coalesce(extract(epoch from (%(now)s::timestamptz - min(created_at))), 0) from tasks where status = 'queued'",
            params,
        ).fetchone()[0]
        dq: dict[tuple[str, str], float] = {}
        for kind, p50, p95 in quant:
            dq[(kind, "0.5")] = float(p50 or 0.0)
            dq[(kind, "0.95")] = float(p95 or 0.0)
        return MetricsSnapshot(
            window_minutes=window_minutes,
            requests={(k, o): int(c) for k, o, c in req},
            escalations={str(c): int(n) for c, n in esc},
            open_escalations=int(open_esc),
            duration_ms_quantiles=dq,
            model_calls=int(usage[0]),
            tokens=int(usage[1]),
            cost_usd_window=float(usage[2]),
            cost_usd_month=float(month),
            tasks_by_status={str(s): int(n) for s, n in tasks},
            oldest_queued_age_s=float(oldest or 0.0),
            generated_at=now,
            retrieval_integrity=self._retrieval_integrity() if self._retrieval_integrity else None,
        )


def _line(name: str, value: float | int, labels: Mapping[str, str] | None = None) -> str:
    if labels:
        body = ",".join(f'{k}="{str(v).replace(chr(34), chr(39))}"' for k, v in sorted(labels.items()))
        return f"{name}{{{body}}} {value}"
    return f"{name} {value}"


def render_prometheus(snapshot: MetricsSnapshot, *, monthly_cap_usd: float | None = None) -> str:
    """Prometheus text exposition (gauges over the window; no high-cardinality labels)."""
    out: list[str] = []

    def header(name: str, kind: str, help_text: str) -> None:
        out.append(f"# HELP {name} {help_text}")
        out.append(f"# TYPE {name} {kind}")

    w = snapshot.window_minutes
    header("medops_requests_window", "gauge", f"Requests finished in the last {w} minutes by kind and outcome")
    for (kind, outcome), n in sorted(snapshot.requests.items()):
        out.append(_line("medops_requests_window", n, {"kind": kind, "outcome": outcome}))
    header("medops_escalations_window", "gauge", f"Escalation reason codes recorded in the last {w} minutes")
    for code, n in sorted(snapshot.escalations.items()):
        out.append(_line("medops_escalations_window", n, {"reason_code": code}))
    header("medops_escalations_open", "gauge", "Escalations awaiting a human")
    out.append(_line("medops_escalations_open", snapshot.open_escalations))
    header("medops_request_duration_ms", "gauge", f"Request duration quantiles over the last {w} minutes")
    for (kind, q), ms in sorted(snapshot.duration_ms_quantiles.items()):
        out.append(_line("medops_request_duration_ms", round(ms, 1), {"kind": kind, "quantile": q}))
    header("medops_model_calls_window", "gauge", f"Model calls in the last {w} minutes")
    out.append(_line("medops_model_calls_window", snapshot.model_calls))
    header("medops_model_tokens_window", "gauge", f"Model tokens in the last {w} minutes")
    out.append(_line("medops_model_tokens_window", snapshot.tokens))
    header("medops_model_cost_usd_window", "gauge", f"Model spend in USD in the last {w} minutes")
    out.append(_line("medops_model_cost_usd_window", round(snapshot.cost_usd_window, 6)))
    header("medops_model_cost_usd_month", "gauge", "Model spend in USD since the start of the month")
    out.append(_line("medops_model_cost_usd_month", round(snapshot.cost_usd_month, 6)))
    if monthly_cap_usd is not None:
        header("medops_model_budget_usd_cap", "gauge", "Configured monthly model budget in USD (ADR-0010)")
        out.append(_line("medops_model_budget_usd_cap", monthly_cap_usd))
    header("medops_tasks", "gauge", "Tasks by status")
    for status, n in sorted(snapshot.tasks_by_status.items()):
        out.append(_line("medops_tasks", n, {"status": status}))
    header("medops_task_queue_oldest_age_seconds", "gauge", "Age of the oldest queued task")
    out.append(_line("medops_task_queue_oldest_age_seconds", round(snapshot.oldest_queued_age_s, 1)))
    if snapshot.retrieval_integrity is not None:
        health = snapshot.retrieval_integrity
        header("medops_retrieval_indexes_ready", "gauge", "Production index coverage and version checks passed")
        out.append(_line("medops_retrieval_indexes_ready", int(bool(health["ready"]))))
        for key in (
            "active_documents",
            "active_documents_without_chunks",
            "active_chunks",
            "missing_lexical",
            "missing_embedding",
            "documents_not_fully_indexed",
        ):
            if key in health.get("coverage", {}):
                name = f"medops_index_{key}"
                header(name, "gauge", "Global production index coverage count")
                out.append(_line(name, health["coverage"][key]))
        header("medops_outbox_pending", "gauge", "Unacknowledged events per retrieval consumer")
        header("medops_outbox_oldest_age_seconds", "gauge", "Oldest unacknowledged retrieval event age")
        header("medops_outbox_dead_lettered", "gauge", "Dead-lettered events per retrieval consumer")
        for consumer in ("lexical-index", "vector-index", "retrieval-cache"):
            entry = health.get("outbox", {}).get(consumer)
            if entry is not None:
                out.append(_line("medops_outbox_pending", entry["pending"], {"consumer": consumer}))
                out.append(
                    _line("medops_outbox_oldest_age_seconds", round(entry["oldest_age_s"], 1), {"consumer": consumer})
                )
                out.append(_line("medops_outbox_dead_lettered", entry.get("dead_lettered", 0), {"consumer": consumer}))
    return "\n".join(out) + "\n"


def has_role(roles: Sequence[str], *allowed: str) -> bool:
    return any(r in allowed for r in roles)
