"""Progress-based supervision for allowlisted workers; no model calls or release actions.

Healthchecks alone do not restart a hung container. This parent terminates a stalled process group and exits
nonzero so the deployment restart policy can recover it. Heartbeats describe completed cycles, not live threads.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

MODULES = {
    "retrieval": "medops.worker.retrieval",
    "scores": "medops.worker.observability",
    "tasks": "medops.worker.serve",
    "maintenance": "medops.worker.maintenance",
}
_HEARTBEAT = "MEDOPS_WORKER_HEARTBEAT"
_TOKEN = "MEDOPS_WORKER_RUN_TOKEN"


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    # Never follow a previously planted temporary-file link, or expose operational state to other users.
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream)
    os.replace(temporary, path)


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open() as stream:
            result = json.loads(stream.read(2049))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def pulse() -> None:
    """Optional when run standalone. Call only after a complete cycle (including an empty successful poll)."""
    path, token = os.environ.get(_HEARTBEAT), os.environ.get(_TOKEN)
    if path and token:
        _write(Path(path), {"token": token, "pid": os.getpid(), "monotonic": time.monotonic()})


def progress(path: Path, *, token: str, pid: int, now: float) -> float | None:
    data = _read(path)
    stamp = data.get("monotonic")
    if data.get("token") != token or data.get("pid") != pid:
        return None
    if (
        not isinstance(stamp, (int, float))
        or isinstance(stamp, bool)
        or not math.isfinite(stamp)
        or not 0 <= stamp <= now
    ):
        return None
    return float(stamp)


def healthy(path: Path, *, now: float | None = None, max_age: float = 15) -> bool:
    data = _read(path)
    stamp, pid = data.get("updated_at"), data.get("pid")
    if data.get("ready") is not True or type(pid) is not int or pid < 1:
        return False
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool) or not math.isfinite(stamp):
        return False
    age = (time.time() if now is None else now) - stamp
    if not 0 <= age <= max_age:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_child(child: subprocess.Popen[Any], *, grace: float) -> bool:
    """Kill the whole session, including descendants that survived their original parent. Return forced status."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        child.wait()
        return False
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        child.poll()  # reap the direct child; descendants may still be running
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            child.wait()
            return False
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()
    return True


def supervise(
    command: list[str],
    *,
    state: Path,
    startup: float,
    stall: float,
    grace: float,
    interval: float = 0,
    stop: threading.Event,
    tick: float = 0.5,
) -> int:
    """One continuous child or sequential scheduled executions. Never overlap jobs or retry inside this parent."""
    child = None
    health_file, beat_file = state / "health.json", state / "progress.json"

    def health(ready: bool, status: str) -> None:
        _write(health_file, {"pid": os.getpid(), "ready": ready, "status": status, "updated_at": time.time()})

    try:
        while not stop.is_set():
            token = secrets.token_hex(16)
            health(False, "starting")
            child = subprocess.Popen(
                command,
                env={**os.environ, _HEARTBEAT: str(beat_file), _TOKEN: token},
                start_new_session=True,
            )
            started, last, next_write = time.monotonic(), None, 0.0
            while not stop.is_set():
                now = time.monotonic()
                beat = progress(beat_file, token=token, pid=child.pid, now=now)
                if beat is not None and beat >= started and (last is None or beat > last):
                    last = beat
                code = child.poll()
                if code is not None:
                    if interval and code == 0:
                        break
                    health(False, "child_exited")
                    print(json.dumps({"status": "child_exited", "returncode": code}), flush=True)
                    return 1  # even an unexpected clean exit requires a restart
                if now - (last if last is not None else started) > (stall if last is not None else startup):
                    health(False, "stalled")
                    print(
                        json.dumps({"status": "worker_stalled", "phase": "running" if last else "startup"}), flush=True
                    )
                    return 1
                if now >= next_write:
                    health(last is not None, "running" if last is not None else "starting")
                    next_write = now + min(5, stall / 2)
                stop.wait(tick)
            if stop.is_set():
                break
            # Reap any descendants before another scheduled job can begin. The successful exit is its heartbeat.
            stop_child(child, grace=grace)
            child = None
            due = time.monotonic() + interval
            while not stop.is_set() and time.monotonic() < due:
                health(True, "waiting")
                stop.wait(min(5, max(0, due - time.monotonic())))
        return 0
    finally:
        try:
            health(False, "stopped")
        finally:
            if child is not None:
                forced = stop_child(child, grace=grace)
                print(json.dumps({"status": "worker_stopped", "forced": forced}), flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, default=Path("/app/.worker-state"))
    ap.add_argument(
        "--check", action="store_true", help="healthcheck of completed progress, not dependency connectivity"
    )
    ap.add_argument("--kind", choices=MODULES)
    ap.add_argument("--startup", type=float, default=300)
    ap.add_argument("--stall", type=float, default=300)
    ap.add_argument("--grace", type=float, default=20)
    ap.add_argument("--interval", type=float, default=0, help="maintenance-only seconds between successful runs")
    ap.add_argument("args", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.check:
        return 0 if healthy(args.state / "health.json") else 1
    if not args.kind:
        ap.error("--kind required")
    if any(not math.isfinite(v) or v <= 0 for v in (args.startup, args.stall, args.grace)):
        ap.error("startup/stall/grace must be finite and positive")
    if not math.isfinite(args.interval) or args.interval < 0 or (args.interval and args.kind != "maintenance"):
        ap.error("nonnegative interval is only supported for maintenance")
    forwarded = args.args[1:] if args.args[:1] == ["--"] else args.args
    stop = threading.Event()
    previous = {sig: signal.signal(sig, lambda _sig, _frame: stop.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        return supervise(
            [sys.executable, "-m", MODULES[args.kind], *forwarded],
            state=args.state,
            startup=args.startup,
            stall=args.stall,
            grace=args.grace,
            interval=args.interval,
            stop=stop,
        )
    except Exception as exc:  # noqa: BLE001 - do not echo DSNs, commands, environment or payloads
        print(json.dumps({"status": "supervision_failed", "error_type": type(exc).__name__}), flush=True)
        return 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
