"""Read feedback into a local durable score queue and deliver outside API request transactions.

--database selects a fact plane explicitly; --run imports a bound main/safety run once.
Use --enqueue-only to prepare/inspect the local queue without sending anything to the backend.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import signal
import threading
from collections.abc import Sequence
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

from medops.core.config import Settings
from medops.evals.telemetry import events_from_run
from medops.infrastructure.observability import LangfuseScores, ScoreQueue, harvest_feedback


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queue", type=Path, required=True, help="local SQLite delivery ledger; keep outside Git")
    ap.add_argument("--database", help="explicit fact plane for feedback collection; no default DB")
    ap.add_argument("--run", type=Path, help="import a condition-bound main/safety run")
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--poll", type=float, default=5)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--enqueue-only", action="store_true", help="prepare one batch; never make an HTTP call")
    ap.add_argument("--requeue-score", help="operator action: requeue one dead-lettered score id and exit")
    args = ap.parse_args(argv)
    if args.database and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", args.database):
        ap.error("invalid explicit database name")
    if not 1 <= args.batch <= 1000 or not math.isfinite(args.poll) or not 0.1 <= args.poll <= 60:
        ap.error("batch must be 1..1000 and poll must be 0.1..60 seconds")
    sender = queue = None
    try:
        settings = Settings()  # type: ignore[call-arg]
        if not settings.langfuse_base_url or not settings.langfuse_public_key or not settings.langfuse_secret_key:
            raise ValueError("Langfuse configuration absent")
        sender = LangfuseScores(
            settings.langfuse_base_url,
            settings.langfuse_public_key.get_secret_value(),
            settings.langfuse_secret_key.get_secret_value(),
        )
        queue = ScoreQueue(
            args.queue,
            sender.destination,
            max_rows=settings.langfuse_score_queue_max_rows,
            max_age_s=settings.langfuse_score_queue_max_age_s,
            max_attempts=settings.langfuse_score_queue_max_attempts,
            backoff_base_s=settings.langfuse_score_queue_backoff_base_s,
            backoff_max_s=settings.langfuse_score_queue_backoff_max_s,
        )
        dsn = None
        if args.database:
            credential = settings.database_loop_url or settings.database_admin_url
            if credential is None:
                raise ValueError("feedback export needs audit visibility")
            dsn = make_conninfo(credential.get_secret_value(), dbname=args.database)
        if args.run:
            events = events_from_run(args.run)  # validate the complete file before queuing any event
            count = sum(queue.enqueue(event) for event in events)
            print(json.dumps({"imported": count, "events": len(events)}), flush=True)
    except Exception as exc:  # noqa: BLE001 - credentials/source text must not enter error output
        if queue:
            queue.close()
        if sender:
            sender.close()
        print(json.dumps({"status": "configuration_or_import_failed", "error_type": type(exc).__name__}), flush=True)
        return 2
    if args.requeue_score:
        requeued = queue.requeue(args.requeue_score)
        print(json.dumps({"score_id": args.requeue_score, "requeued": requeued}), flush=True)
        queue.close()
        sender.close()
        return 0 if requeued else 1
    stop = threading.Event()
    previous = {sig: signal.signal(sig, lambda _sig, _frame: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        while not stop.is_set():
            try:
                collected = {}
                if dsn:
                    with psycopg.connect(dsn, connect_timeout=5, options="-c statement_timeout=5000") as conn:
                        conn.read_only = True
                        collected = harvest_feedback(conn, queue, limit=args.batch)
                sent = {} if args.enqueue_only else queue.drain(sender, limit=args.batch, cancelled=stop.is_set)
                print(json.dumps({"collection": collected, "delivery": sent}), flush=True)
                if args.once or args.enqueue_only:
                    return 1 if sent.get("failed") or sent.get("dead_lettered") else 0
            except Exception as exc:  # noqa: BLE001 - retain durable queue, retry dependency failures
                print(json.dumps({"status": "cycle_failed", "error_type": type(exc).__name__}), flush=True)
                if args.once or args.enqueue_only:
                    return 1
            stop.wait(args.poll)
    finally:
        for sig, previous_handler in previous.items():
            signal.signal(sig, previous_handler)
        queue.close()
        sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
