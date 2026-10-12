"""Bounded durable SQLite transport queue; no feedback collection or prompt bodies."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from medops.core.canonical import canonical_json
from medops.infrastructure.observability.errors import ScoreExportError, ScoreQueueFull
from medops.infrastructure.observability.schema import utc_timestamp, validate_score_event

if TYPE_CHECKING:
    from medops.infrastructure.observability.client import LangfuseScores


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
            create table if not exists feedback_sources (
                source text primary key, namespace text not null unique
            );
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
