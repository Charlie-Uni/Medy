"""Metadata-only Langfuse score export with a durable, destination-bound local queue.

The PostgreSQL audit remains authoritative. Export happens outside the request transaction.
Score-create events use a fixed timestamp: v4 deduplication also depends on the calendar date.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from medops.core.canonical import canonical_hash, canonical_json
from medops.core.config import check_langfuse_base_url
from medops.core.tracing import is_valid_trace_id

FORMAT = "medops-observation-score-v1"
_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_METADATA = frozenset(
    {
        "source",
        "evaluator",
        "rubric_version",
        "scoring_version",
        "dataset_version",
        "dataset_hash",
        "sample_id",
        "sample_input_sha256",
        "run_conditions_sha256",
        "attempt_id",
        "policy_version",
        "retrieval_version",
        "model_config_version",
        "feedback_id",
        "fact_plane",
        "formal_gate",
    }
)


def utc_timestamp(value: str | datetime) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("score timestamp must include a timezone")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def score_event(
    *,
    identity: str,
    trace_id: str,
    name: str,
    value: str | float | bool,
    timestamp: str | datetime,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not identity or not is_valid_trace_id(trace_id) or not int(trace_id, 16) or not _NAME.fullmatch(name):
        raise ValueError("score needs a stable identity, W3C trace id and bounded metric name")
    if set(metadata) - _METADATA or any(not isinstance(v, (str, bool)) for v in metadata.values()):
        raise ValueError("score metadata must contain only approved scalar identifiers")
    if any(isinstance(v, str) and len(v) > 300 for v in metadata.values()):
        raise ValueError("score metadata identifier too long")
    encoded: str | float | int
    if isinstance(value, bool):
        data_type, encoded = "BOOLEAN", int(value)
    elif isinstance(value, (int, float)) and math.isfinite(value):
        data_type, encoded = "NUMERIC", float(value)
    elif isinstance(value, str) and _NAME.fullmatch(value):
        data_type, encoded = "CATEGORICAL", value
    else:
        raise ValueError("score value must be finite numeric, bool or a controlled category")
    score_id = canonical_hash({"format": FORMAT, "identity": identity, "trace_id": trace_id, "name": name})
    return {
        "id": score_id,
        "type": "score-create",
        "timestamp": utc_timestamp(timestamp),
        "body": {
            "id": score_id,
            "traceId": trace_id,
            "name": name,
            "value": encoded,
            "dataType": data_type,
            "metadata": dict(metadata),
        },
    }


def validate_score_event(event: dict[str, Any]) -> None:
    try:
        body = event["body"]
        value = body["value"]
        if body["dataType"] == "BOOLEAN":
            if type(value) is not int or value not in (0, 1):
                raise ValueError("invalid boolean")
            value = bool(value)
        rebuilt = score_event(
            identity="validation",
            trace_id=body["traceId"],
            name=body["name"],
            value=value,
            timestamp=event["timestamp"],
            metadata=body["metadata"],
        )
        if not re.fullmatch(r"[0-9a-f]{64}", event["id"]):
            raise ValueError("invalid id")
        rebuilt["id"] = rebuilt["body"]["id"] = event["id"]
        if rebuilt != event:
            raise ValueError("score fields differ")
    except (TypeError, KeyError, AttributeError, ValueError):
        raise ValueError("invalid or non-allowlisted score event") from None


def feedback_event(row: Mapping[str, Any], *, fact_plane: str) -> dict[str, Any]:
    if row["signal"] not in {"up", "down", "correction"}:
        raise ValueError("unsupported feedback signal")
    return score_event(
        identity=f"feedback:{fact_plane}:{row['feedback_id']}",
        trace_id=row["trace_id"],
        name="user_feedback",
        value=row["signal"],
        timestamp=row["created_at"],
        metadata={
            "source": "authenticated_user_feedback",
            "feedback_id": str(row["feedback_id"]),
            "fact_plane": fact_plane,
            "formal_gate": False,
        },
    )


class ScoreExportError(Exception):
    """Only safe fixed codes; never attach remote response bodies or credentials."""


class ScoreQueueFull(Exception):
    """The bounded local queue needs operator attention before more scores can be accepted."""


class LangfuseScores:
    def __init__(
        self, base_url: str, public_key: str, secret_key: str, *, transport: httpx.BaseTransport | None = None
    ):
        check_langfuse_base_url(base_url)
        if not public_key or not secret_key:
            raise ValueError("score export needs both Langfuse API keys")
        self.base_url = base_url.rstrip("/")
        self.destination = canonical_hash({"base_url": self.base_url, "public_key": public_key, "format": FORMAT})
        self._client = httpx.Client(
            auth=(public_key, secret_key),
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _require_trace(self, trace_id: str) -> None:
        # Metadata only; this prevents orphan scores for old random OTel IDs or dropped/off telemetry.
        try:
            response = self._client.get(
                self.base_url + "/api/public/v2/observations",
                params={"traceId": trace_id, "fields": "core", "limit": 1},
            )
        except httpx.HTTPError:
            raise ScoreExportError("trace_lookup_transport_failure") from None
        if response.status_code != 200:
            raise ScoreExportError(f"trace_lookup_http_{response.status_code}")
        try:
            rows = response.json()["data"]
            if not isinstance(rows, list) or not rows or any(row.get("traceId") != trace_id for row in rows):
                raise ValueError("not visible")
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ScoreExportError("trace_not_visible") from None

    def send(self, event: dict[str, Any]) -> None:
        validate_score_event(event)
        self._require_trace(event["body"]["traceId"])
        # Pinned v4.54.0 compatibility path: score events remain supported in events-only mode.
        # POST /scores rebuilds the timestamp on each attempt; it cannot preserve cross-day dedup identity.
        try:
            response = self._client.post(self.base_url + "/api/public/ingestion", json={"batch": [event]})
        except httpx.HTTPError:
            raise ScoreExportError("transport_failure") from None
        if response.status_code not in {200, 207}:
            raise ScoreExportError(f"http_{response.status_code}")
        try:
            data = response.json()
            success = data.get("successes", [])
            accepted = {item["id"] for item in success}
            if (
                data.get("errors")
                or len(success) != 1
                or accepted != {event["id"]}
                or not 200 <= success[0].get("status", 200) < 300
            ):
                raise ValueError("not acknowledged")
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ScoreExportError("event_not_acknowledged") from None


class ScoreQueue:
    """Bounded SQLite at-least-once queue with retry backoff and an inspectable dead letter state.

    One local DB is bound to one backend/API-key identity. Multiple senders may duplicate delivery;
    the stable remote event identity is required. The file contains IDs/metrics only, never credentials.
    """

    def __init__(
        self,
        path: Path,
        destination: str,
        *,
        max_rows: int = 10_000,
        max_age_s: int = 30 * 24 * 3600,
        max_attempts: int = 10,
        backoff_base_s: int = 5,
        backoff_max_s: int = 3600,
        clock: Callable[[], datetime] | None = None,
    ):
        if max_rows < 1 or max_age_s < 1 or max_attempts < 1:
            raise ValueError("score queue limits must be positive")
        if backoff_base_s < 1 or backoff_max_s < backoff_base_s:
            raise ValueError("score queue backoff bounds are invalid")
        self.max_rows = max_rows
        self.max_age_s = max_age_s
        self.max_attempts = max_attempts
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self._clock = clock or (lambda: datetime.now(UTC))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self.conn = sqlite3.connect(path, timeout=5)
        self.conn.execute("pragma journal_mode=delete")
        self.conn.executescript("""
            create table if not exists settings (key text primary key, value text not null);
            create table if not exists scores (
                id text primary key, payload text not null, delivered integer not null default 0,
                attempts integer not null default 0, last_error text, updated_at text not null
            );
            create table if not exists scans (source text primary key, cursor text not null);
        """)
        columns = {row[1] for row in self.conn.execute("pragma table_info(scores)")}
        for name in ("created_at", "next_attempt_at", "dead_lettered_at"):
            if name not in columns:
                self.conn.execute(f"alter table scores add column {name} text")
        with self.conn:
            self.conn.execute("update scores set created_at=updated_at where created_at is null")
            self.conn.execute("update scores set next_attempt_at=updated_at where next_attempt_at is null")
            self.conn.execute(
                "create index if not exists scores_delivery_due "
                "on scores(delivered,dead_lettered_at,next_attempt_at,id)"
            )
        existing = self.conn.execute("select value from settings where key='destination'").fetchone()
        if existing and existing[0] != destination:
            self.conn.close()
            raise ValueError("score queue belongs to another export destination")
        with self.conn:
            self.conn.execute("insert or ignore into settings values ('destination', ?)", (destination,))
        if self.conn.execute("select value from settings where key='destination'").fetchone()[0] != destination:
            self.conn.close()
            raise ValueError("score queue destination changed concurrently")

    def close(self) -> None:
        self.conn.close()

    def enqueue(self, event: dict[str, Any]) -> bool:
        validate_score_event(event)
        payload = canonical_json(event)
        existing = self.conn.execute("select payload from scores where id=?", (event["id"],)).fetchone()
        if existing and existing[0] != payload:
            raise ValueError("immutable score identity was reused with different contents")
        if existing:
            return False
        # Delivered rows are only a local transport receipt; the PostgreSQL audit and Langfuse are authoritative.
        # Remove the oldest receipts first, then fail closed if pending/dead-letter rows fill the configured bound.
        row_count = int(self.conn.execute("select count(*) from scores").fetchone()[0])
        if row_count >= self.max_rows:
            with self.conn:
                self.conn.execute(
                    "delete from scores where id in (select id from scores where delivered=1 "
                    "order by updated_at,id limit ?)",
                    (row_count - self.max_rows + 1,),
                )
        if int(self.conn.execute("select count(*) from scores").fetchone()[0]) >= self.max_rows:
            raise ScoreQueueFull("score_queue_capacity_reached")
        now = utc_timestamp(self._clock())
        with self.conn:
            self.conn.execute(
                "insert into scores(id,payload,updated_at,created_at,next_attempt_at) values (?,?,?,?,?)",
                (event["id"], payload, now, now, now),
            )
        return True

    def requeue(self, score_id: str) -> bool:
        """Operator action after fixing the cause; payload and remote id remain immutable."""
        now = utc_timestamp(self._clock())
        with self.conn:
            cur = self.conn.execute(
                "update scores set attempts=0,last_error=null,dead_lettered_at=null,next_attempt_at=?,updated_at=? "
                "where id=? and delivered=0 and dead_lettered_at is not null",
                (now, now, score_id),
            )
        return cur.rowcount == 1

    def scan_cursor(self, source: str) -> str:
        row = self.conn.execute("select cursor from scans where source=?", (source,)).fetchone()
        return row[0] if row else "00000000-0000-0000-0000-000000000000"

    def advance_scan(self, source: str, cursor: str | None) -> None:
        # Call only after all fetched events are durably enqueued. A completed sweep resets: late
        # commits may have an older ID/timestamp and must be found on a subsequent sweep.
        with self.conn:
            self.conn.execute(
                "insert into scans values (?,?) on conflict(source) do update set cursor=excluded.cursor",
                (source, cursor or "00000000-0000-0000-0000-000000000000"),
            )

    def drain(
        self, sender: LangfuseScores, *, limit: int = 100, cancelled: Callable[[], bool] | None = None
    ) -> dict[str, int]:
        if not 1 <= limit <= 1000:
            raise ValueError("score batch must be 1..1000")
        if sender.destination != self.conn.execute("select value from settings where key='destination'").fetchone()[0]:
            raise ValueError("sender and queue destination differ")
        now_dt = self._clock().astimezone(UTC)
        now = utc_timestamp(now_dt)
        cutoff = utc_timestamp(datetime.fromtimestamp(now_dt.timestamp() - self.max_age_s, tz=UTC))
        with self.conn:
            self.conn.execute(
                "update scores set dead_lettered_at=?,last_error='max_age_exceeded',updated_at=? "
                "where delivered=0 and dead_lettered_at is null and created_at < ?",
                (now, now, cutoff),
            )
        rows = self.conn.execute(
            "select id,payload,attempts from scores where delivered=0 and dead_lettered_at is null "
            "and next_attempt_at <= ? order by next_attempt_at,id limit ?",
            (now, limit),
        ).fetchall()
        acknowledged = failed = attempted = 0
        for score_id, payload, previous_attempts in rows:
            if cancelled and cancelled():
                break
            attempted += 1
            error = None
            try:
                sender.send(json.loads(payload))
                acknowledged += 1
            except ScoreExportError as exc:
                error = str(exc)
                failed += 1
            attempts = int(previous_attempts) + 1
            dead_lettered_at = None
            next_attempt_at = now
            if error is not None:
                if attempts >= self.max_attempts:
                    dead_lettered_at = now
                else:
                    delay = min(self.backoff_max_s, self.backoff_base_s * (2 ** (attempts - 1)))
                    next_attempt_at = utc_timestamp(datetime.fromtimestamp(now_dt.timestamp() + delay, tz=UTC))
            with self.conn:
                self.conn.execute(
                    "update scores set delivered=?,attempts=?,last_error=?,updated_at=?,next_attempt_at=?,"
                    "dead_lettered_at=? where id=?",
                    (int(error is None), attempts, error, now, next_attempt_at, dead_lettered_at, score_id),
                )
        pending = int(
            self.conn.execute("select count(*) from scores where delivered=0 and dead_lettered_at is null").fetchone()[
                0
            ]
        )
        delayed = int(
            self.conn.execute(
                "select count(*) from scores where delivered=0 and dead_lettered_at is null and next_attempt_at > ?",
                (now,),
            ).fetchone()[0]
        )
        dead_lettered = int(
            self.conn.execute(
                "select count(*) from scores where delivered=0 and dead_lettered_at is not null"
            ).fetchone()[0]
        )
        return {
            "attempted": attempted,
            "acknowledged": acknowledged,
            "failed": failed,
            "pending": pending,
            "delayed": delayed,
            "dead_lettered": dead_lettered,
        }


def harvest_feedback(conn: Any, queue: ScoreQueue, *, limit: int = 100) -> dict[str, int | bool]:
    """Read only committed feedback metadata; never select correction_text, principal or query."""
    from medops.retrieval.integrity import database_identity

    if not 1 <= limit <= 1000:
        raise ValueError("feedback batch must be 1..1000")
    allowed = conn.execute(
        "select current_setting('transaction_read_only')='on', "
        "rolsuper or rolbypassrls or pg_has_role(current_user,'medops_admin_role','member') "
        "or pg_has_role(current_user,'medops_loop_role','member') from pg_roles where rolname=current_user"
    ).fetchone()
    if not allowed or not all(allowed):
        raise ValueError("feedback export requires a read-only transaction and global audit visibility")
    source = database_identity(conn)
    cursor = queue.scan_cursor(source)
    rows = conn.execute(
        "select feedback_id::text,trace_id,signal,created_at from feedback "
        "where feedback_id > %s::uuid order by feedback_id limit %s",
        (cursor, limit),
    ).fetchall()
    enqueued = 0
    for row in rows:
        event = feedback_event(
            dict(zip(("feedback_id", "trace_id", "signal", "created_at"), row, strict=True)), fact_plane=source
        )
        enqueued += queue.enqueue(event)
    queue.advance_scan(source, rows[-1][0] if rows else None)
    return {"scanned": len(rows), "enqueued": enqueued, "sweep_complete": not rows}
