"""`python -m medops.worker.serve [--poll 2.0] [--lease 300] [--once] [--device cpu|mps]`: the task worker over
the production runtime. PostgreSQL is the queue and the source of truth (baseline 5.7); polling is bounded and
idle-friendly. `--lease` is how long a claimed task stays this worker's before another worker may take it over
(record 59); fault drills shorten it, production keeps the default."""

from __future__ import annotations

import argparse
import signal
import sys
import time

from medops.api.runtime import ProductionRuntime
from medops.application.tasks import DEFAULT_LEASE_S, TaskRunner
from medops.core.config import Settings, safe_config_errors
from medops.core.errors import InfrastructureError
from medops.core.logging import configure_logging, get_logger
from medops.core.telemetry import configure_telemetry
from medops.core.telemetry import shutdown as shutdown_telemetry
from medops.skills.catalog import default_registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll", type=float, default=2.0, help="seconds to sleep when no task is claimable")
    ap.add_argument("--lease", type=float, default=DEFAULT_LEASE_S, help="seconds a claimed task is leased")
    ap.add_argument("--once", action="store_true", help="process at most one task and exit")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args(argv)
    if args.lease <= 0:
        ap.error("--lease must be positive")
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - configuration errors are reported in their safe form only
        from pydantic import ValidationError

        detail = safe_config_errors(exc) if isinstance(exc, ValidationError) else [{"msg": type(exc).__name__}]
        print(f"configuration invalid: {detail}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    configure_telemetry(
        endpoint=settings.otel_exporter_otlp_endpoint,
        service_name=settings.otel_service_name,
        headers=settings.otel_exporter_otlp_headers.get_secret_value() if settings.otel_exporter_otlp_headers else None,
    )
    log = get_logger(__name__)
    runtime = ProductionRuntime.from_settings(settings, device=args.device)
    runner = TaskRunner(env=runtime, registry=default_registry(), lease_s=args.lease)
    stop = False

    def _stop(signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True  # finish the current task, then exit (graceful stop)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker starting", extra={"worker_id": runner.worker_id, "device": args.device, "lease_s": args.lease})
    while not stop:
        try:
            done = runner.run_once()
        except InfrastructureError as exc:  # database unreachable: keep polling instead of dying (record 78)
            log.warning(
                "worker: dependency unavailable, retrying", extra={"code": exc.code.value, "detail": exc.detail}
            )
            if args.once:
                return 1
            time.sleep(args.poll)
            continue
        if done is not None:
            log.info(
                "task finished", extra={"task_id": done.task_id, "status": done.status.value, "trace_id": done.trace_id}
            )
            if args.once:
                break
            continue
        if args.once:
            break
        time.sleep(args.poll)
    log.info("worker stopped", extra={"worker_id": runner.worker_id})
    shutdown_telemetry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
