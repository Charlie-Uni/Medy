"""`medops.mcp.serve --transport stdio` must keep stdout for JSON-RPC: structured logs go to stderr (record 67)."""

import logging
import sys
from types import SimpleNamespace

import pytest

from medops.mcp import serve as serve_mod


class _Server:
    def __init__(self):
        self.ran_with = None

    def run(self, transport):
        self.ran_with = transport


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:pw@localhost:5432/db")
    monkeypatch.setenv("DATABASE_READONLY_URL", "postgresql://ro:pw@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    root = logging.getLogger()
    saved = (list(root.handlers), root.level)
    yield
    root.handlers, _ = saved
    root.setLevel(saved[1])


def test_stdio_transport_logs_to_stderr_and_runs_the_server(_env, monkeypatch):
    seen: dict = {}
    server = _Server()
    monkeypatch.setattr(serve_mod, "configure_logging", lambda level, stream=None: seen.setdefault("stream", stream))
    monkeypatch.setattr(serve_mod, "configure_telemetry", lambda **kw: None)
    monkeypatch.setattr(serve_mod, "_searcher_factory", lambda device, settings: object())
    monkeypatch.setattr(serve_mod, "McpProductionRuntime", lambda **kw: seen.setdefault("runtime", kw))
    monkeypatch.setattr(serve_mod, "build_server", lambda runtime, **kw: server)
    assert serve_mod.main(["--transport", "stdio", "--dev-dept", "MA"]) == 0
    assert seen["stream"] is sys.stderr
    assert server.ran_with == "stdio"
    assert seen["runtime"]["dev_identity"].dept.value == "MA" and seen["runtime"]["authenticator"] is None


def test_stdio_transport_needs_a_dev_dept(_env, monkeypatch, capsys):
    monkeypatch.setattr(serve_mod, "configure_logging", lambda level, stream=None: None)
    monkeypatch.setattr(serve_mod, "configure_telemetry", lambda **kw: None)
    assert serve_mod.main(["--transport", "stdio"]) == 2
    assert "--dev-dept" in capsys.readouterr().err


@pytest.mark.parametrize("close_fails", [False, True])
def test_server_failure_closes_owned_resources_and_telemetry_even_when_cleanup_fails(_env, monkeypatch, close_fails):
    events = []

    def run(_transport):
        events.append("run")
        raise RuntimeError("server failed")

    def close():
        events.append("close")
        if close_fails:
            raise ValueError("cleanup failed")

    monkeypatch.setattr(serve_mod, "configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(serve_mod, "configure_telemetry", lambda **kwargs: None)
    monkeypatch.setattr(serve_mod, "shutdown_telemetry", lambda: events.append("telemetry"))
    monkeypatch.setattr(serve_mod, "_searcher_factory", lambda *args: SimpleNamespace(close=close))
    monkeypatch.setattr(serve_mod, "McpProductionRuntime", lambda **kwargs: object())
    monkeypatch.setattr(serve_mod, "build_server", lambda *args, **kwargs: SimpleNamespace(run=run))
    with pytest.raises(ValueError if close_fails else RuntimeError):
        serve_mod.main(["--transport", "stdio", "--dev-dept", "MA"])
    assert events == ["run", "close", "telemetry"]
