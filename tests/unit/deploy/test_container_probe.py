"""Published port may reset/close before uvicorn is listening; readiness polling must wait."""

from http.client import RemoteDisconnected
from urllib.error import HTTPError

import pytest
from deploy.ci import http_probe
from deploy.ci.test_container_boot import container_dsn


@pytest.mark.parametrize("error", [RemoteDisconnected("synthetic"), ConnectionResetError(), TimeoutError()])
def test_unbound_api_port_is_pending(monkeypatch, error):
    def not_listening(*args, **kwargs):
        raise error

    monkeypatch.setattr(http_probe, "urlopen", not_listening)
    assert http_probe.status("http://127.0.0.1:1/healthz") is None


def test_real_not_ready_status_is_preserved(monkeypatch):
    def unavailable(*args, **kwargs):
        raise HTTPError("http://127.0.0.1:1/readyz", 503, "not ready", {}, None)

    monkeypatch.setattr(http_probe, "urlopen", unavailable)
    assert http_probe.status("http://127.0.0.1:1/readyz") == 503


def test_container_database_does_not_use_random_host_port():
    assert container_dsn("postgresql://ci:synthetic@127.0.0.1:53941/test_db?sslmode=disable", "ci-postgres") == (
        "postgresql://ci:synthetic@ci-postgres:5432/test_db?sslmode=disable"
    )
