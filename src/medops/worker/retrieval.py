"""Continuous lexical/vector/cache outbox consumer. An explicit target database is mandatory.

Example: python -m medops.worker.retrieval --database medops_v2 --consumer lexical-index --once
No LLM API is used. The vector consumer loads the pinned local embedding model on its single worker thread.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import signal
import threading
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

from medops.core.config import Settings
from medops.ingestion import outbox
from medops.retrieval import cache_consumer, maintenance


def handler_from_settings(settings: Settings, consumer: str, *, device: str = "cpu") -> Any:
    if consumer == "lexical-index":
        return maintenance.lexical_handler()
    if consumer == "vector-index":
        from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

        return maintenance.vector_handler(BgeM3EmbeddingProvider(device=device))
    if consumer == "retrieval-cache":
        if settings.retrieval_cache != "redis":
            raise ValueError("a shared cache consumer requires RETRIEVAL_CACHE=redis")
        from medops.infrastructure.cache import RedisCandidateCacheStore
        from medops.retrieval.cache import CandidateCache

        return cache_consumer.handler_for(
            CandidateCache(
                RedisCandidateCacheStore.from_settings(settings), ttl_seconds=settings.retrieval_cache_ttl_seconds
            )
        )
    raise ValueError("unknown retrieval consumer")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database", required=True, help="explicit database name; never inferred from the default DSN")
    ap.add_argument("--consumer", required=True, choices=maintenance.CONSUMERS)
    ap.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    ap.add_argument("--batch", type=int, default=10, help="events per transaction, 1..100")
    ap.add_argument("--poll", type=float, default=2.0, help="idle/failure polling delay, 0.1..60 seconds")
    ap.add_argument("--once", action="store_true", help="consume at most one batch; nonzero on failure")
    ap.add_argument("--requeue-event", type=int, help="operator action: requeue one dead-lettered event and exit")
    ap.add_argument("--actor", help="operator identity required with --requeue-event")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", args.database):
        ap.error("--database must be an unquoted PostgreSQL database name")
    if not 1 <= args.batch <= 100 or not math.isfinite(args.poll) or not 0.1 <= args.poll <= 60:
        ap.error("--batch must be 1..100 and --poll must be 0.1..60 seconds")
    if (args.requeue_event is None) != (args.actor is None) or (
        args.requeue_event is not None and args.requeue_event < 1
    ):
        ap.error("--requeue-event needs a positive id and --actor")
    try:
        settings = Settings()  # type: ignore[call-arg]
        if settings.database_admin_url is None:
            raise ValueError("administrative connection required")
        dsn = make_conninfo(settings.database_admin_url.get_secret_value(), dbname=args.database)
        handler = (
            None
            if args.requeue_event is not None
            else handler_from_settings(settings, args.consumer, device=args.device)
        )
    except Exception as exc:  # noqa: BLE001 - never print configuration or model loader exception text
        print(json.dumps({"status": "configuration_failed", "error_type": type(exc).__name__}), flush=True)
        return 2
    stop = threading.Event()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, lambda _sig, _frame: stop.set())
    try:
        if args.requeue_event is not None:
            with psycopg.connect(
                dsn,
                connect_timeout=settings.db_connect_timeout_s,
                options=f"-c statement_timeout={settings.db_statement_timeout_ms} -c lock_timeout=5000",
            ) as conn:
                requeued = outbox.requeue_dead_letter(conn, args.consumer, args.requeue_event, actor=args.actor)
            print(
                json.dumps({"consumer": args.consumer, "event_id": args.requeue_event, "requeued": requeued}),
                flush=True,
            )
            return 0 if requeued else 1
        assert handler is not None
        while not stop.is_set():
            try:
                with psycopg.connect(
                    dsn,
                    connect_timeout=settings.db_connect_timeout_s,
                    options=f"-c statement_timeout={settings.db_statement_timeout_ms} -c lock_timeout=5000",
                ) as conn:
                    result = maintenance.consume_batch(
                        conn,
                        args.consumer,
                        handler,
                        limit=args.batch,
                        max_attempts=getattr(settings, "outbox_max_attempts", 10),
                        backoff_base_s=getattr(settings, "outbox_backoff_base_s", 5),
                        backoff_max_s=getattr(settings, "outbox_backoff_max_s", 3600),
                    )
                    conn.commit()
                # Continuous consumers stay silent while idle: at a two-second poll interval, logging every empty
                # batch would add about 43,000 lines/day. One-shot operator calls always print their result.
                if args.once or result.acknowledged or result.failed or result.dead_lettered:
                    print(json.dumps({"consumer": args.consumer, **asdict(result)}), flush=True)
                if args.once:
                    return 1 if result.failed else 0
                if not result.acknowledged or result.failed:
                    stop.wait(args.poll)
            except Exception as exc:  # noqa: BLE001 - dependency recovery; no SQL/DSN/contents in logs
                print(
                    json.dumps({"consumer": args.consumer, "status": "batch_failed", "error_type": type(exc).__name__}),
                    flush=True,
                )
                if args.once:
                    return 1
                stop.wait(args.poll)
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
