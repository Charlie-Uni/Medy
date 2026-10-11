"""Real child processes prove progress fencing, bounded kill, graceful shutdown and scheduled non-overlap."""

import json
import os
import sys
import threading
import time

import pytest

from medops.worker import supervision as s


def test_progress_requires_this_attempt_pid_and_nonfuture_clock(tmp_path):
    path = tmp_path / "beat"
    for data in (
        {"token": "old", "pid": 5, "monotonic": 10},
        {"token": "new", "pid": 6, "monotonic": 10},
        {"token": "new", "pid": 5, "monotonic": 21},
        {"token": "new", "pid": 5, "monotonic": True},
        {"token": "new", "pid": 5, "monotonic": float("nan")},
    ):
        s._write(path, data)
        assert s.progress(path, token="new", pid=5, now=20) is None
    s._write(path, {"token": "new", "pid": 5, "monotonic": 10})
    assert s.progress(path, token="new", pid=5, now=20) == 10
    path.write_text("not-json")
    assert s.progress(path, token="new", pid=5, now=20) is None


def test_health_rejects_stale_future_dead_and_unready_parent(tmp_path):
    path = tmp_path / "health"
    base = {"pid": os.getpid(), "ready": True, "updated_at": 100}
    s._write(path, base)
    assert s.healthy(path, now=110)
    assert not s.healthy(path, now=116)
    assert not s.healthy(path, now=99)
    for extra in ({"ready": False}, {"pid": -1}, {"pid": True}, {"updated_at": float("nan")}):
        s._write(path, {**base, **extra})
        assert not s.healthy(path, now=110)
    assert path.stat().st_mode & 0o777 == 0o600


def test_live_child_without_completed_cycle_is_killed_and_unhealthy(tmp_path, capsys):
    code = s.supervise(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        state=tmp_path,
        startup=0.2,
        stall=1,
        grace=0.2,
        stop=threading.Event(),
        tick=0.02,
    )
    assert code == 1 and not s.healthy(tmp_path / "health.json")
    assert '"phase": "startup"' in capsys.readouterr().out


def test_completed_progress_then_hang_forces_kill_and_reaps_child(tmp_path, capsys):
    child = "from medops.worker.supervision import pulse; import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); pulse(); time.sleep(60)"
    started = time.monotonic()
    assert (
        s.supervise(
            [sys.executable, "-c", child],
            state=tmp_path,
            startup=5,
            stall=0.2,
            grace=0.1,
            stop=threading.Event(),
            tick=0.02,
        )
        == 1
    )
    pid = json.loads((tmp_path / "progress.json").read_text())["pid"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert time.monotonic() - started < 5
    output = capsys.readouterr().out
    assert '"phase": "running"' in output and '"forced": true' in output


def test_sigterm_style_stop_allows_current_child_to_finish(tmp_path):
    marker = tmp_path / "finished"
    code = f"""import signal,time
from pathlib import Path
from medops.worker.supervision import pulse
stop=False
def done(*args):
 global stop
 stop=True
signal.signal(signal.SIGTERM,done)
pulse()
while not stop: time.sleep(.02)
Path({str(marker)!r}).write_text('committed')
"""
    stop = threading.Event()

    def observe():
        deadline = time.monotonic() + 5
        while not (tmp_path / "progress.json").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        stop.set()

    watcher = threading.Thread(target=observe)
    watcher.start()
    try:
        assert (
            s.supervise([sys.executable, "-c", code], state=tmp_path, startup=5, stall=5, grace=1, stop=stop, tick=0.02)
            == 0
        )
    finally:
        stop.set()
        watcher.join(6)
    assert marker.read_text() == "committed"
    assert not s.healthy(tmp_path / "health.json")


def test_successful_scheduled_exit_stays_healthy_while_waiting(tmp_path):
    count = tmp_path / "runs"
    child = f"from pathlib import Path; p=Path({str(count)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x')"
    stop = threading.Event()
    observations = []

    def observe():
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            data = s._read(tmp_path / "health.json")
            if data.get("status") == "waiting":
                observations.append(s.healthy(tmp_path / "health.json"))
                if count.read_text() == "xx":
                    break
            time.sleep(0.02)
        stop.set()

    watcher = threading.Thread(target=observe)
    watcher.start()
    try:
        assert (
            s.supervise(
                [sys.executable, "-c", child],
                state=tmp_path,
                startup=5,
                stall=5,
                grace=0.1,
                interval=0.2,
                stop=stop,
                tick=0.02,
            )
            == 0
        )
    finally:
        stop.set()
        watcher.join(6)
    assert count.read_text() == "xx" and observations and all(observations)


@pytest.mark.parametrize(
    "options",
    [["--kind", "scores", "--interval", "1"], ["--kind", "retrieval", "--stall", "nan"], ["--kind", "unknown"], []],
)
def test_invalid_profiles_never_spawn(options, monkeypatch):
    monkeypatch.setattr(s.subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    with pytest.raises(SystemExit) as caught:
        s.main(options)
    assert caught.value.code == 2
