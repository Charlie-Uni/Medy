"""Read-only committed feedback collection; no user query or correction body selection."""

from __future__ import annotations

from typing import Any

from medops.infrastructure.observability.queue import ScoreQueue
from medops.infrastructure.observability.schema import feedback_event


def harvest_feedback(
    conn: Any,
    queue: ScoreQueue,
    *,
    limit: int = 100,
    expected_fact_plane: str | None = None,
    legacy_source: str | None = None,
) -> dict[str, int | bool]:
    """Read only committed feedback metadata; never select correction_text, principal or query."""
    from medops.infrastructure.db.fact_plane import fact_plane_identity
    from medops.infrastructure.feedback_identity import feedback_namespace

    if not 1 <= limit <= 1000:
        raise ValueError("feedback batch must be 1..1000")
    allowed = conn.execute(
        "select current_setting('transaction_read_only')='on', "
        "rolsuper or rolbypassrls or pg_has_role(current_user,'medops_admin_role','member') "
        "or pg_has_role(current_user,'medops_loop_role','member') from pg_roles where rolname=current_user"
    ).fetchone()
    if not allowed or not all(allowed):
        raise ValueError("feedback export requires a read-only transaction and global audit visibility")
    source = fact_plane_identity(conn, expected=expected_fact_plane)
    namespace = feedback_namespace(queue.conn, source, legacy_source=legacy_source)
    cursor = queue.scan_cursor(source)
    rows = conn.execute(
        "select feedback_id::text,trace_id,signal,created_at from feedback "
        "where feedback_id > %s::uuid order by feedback_id limit %s",
        (cursor, limit),
    ).fetchall()
    enqueued = 0
    for row in rows:
        event = feedback_event(
            dict(zip(("feedback_id", "trace_id", "signal", "created_at"), row, strict=True)), fact_plane=namespace
        )
        enqueued += queue.enqueue(event)
    queue.advance_scan(source, rows[-1][0] if rows else None)
    return {"scanned": len(rows), "enqueued": enqueued, "sweep_complete": not rows}
