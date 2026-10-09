"""Bootstrap and verify the local metadata-only Langfuse deployment.

The smoke paths never call a model. They emit synthetic OpenTelemetry spans, attach one
controlled score, and verify that the real Langfuse APIs can read both back. The optional
outage exercise also proves that the durable local queue retains and retries a score.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from medops.core import telemetry
from medops.core.config import Settings
from medops.infrastructure.observability import LangfuseScores, ScoreQueue, feedback_event, score_event

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = ROOT / "deploy" / "langfuse"
DEPLOY_ENV = DEPLOY_DIR / ".env"
APP_ENV = ROOT / ".env"
COMPOSE = DEPLOY_DIR / "docker-compose.yml"
QUEUE = ROOT / ".local" / "langfuse-smoke-scores.db"

_REQUIRED = frozenset(
    {
        "LANGFUSE_POSTGRES_USER",
        "LANGFUSE_POSTGRES_PASSWORD",
        "LANGFUSE_POSTGRES_DB",
        "LANGFUSE_SALT",
        "LANGFUSE_ENCRYPTION_KEY",
        "LANGFUSE_NEXTAUTH_SECRET",
        "LANGFUSE_CLICKHOUSE_USER",
        "LANGFUSE_CLICKHOUSE_PASSWORD",
        "LANGFUSE_REDIS_PASSWORD",
        "LANGFUSE_MINIO_USER",
        "LANGFUSE_MINIO_PASSWORD",
        "LANGFUSE_INIT_ORG_ID",
        "LANGFUSE_INIT_PROJECT_ID",
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY",
        "LANGFUSE_INIT_PROJECT_SECRET_KEY",
        "LANGFUSE_INIT_USER_EMAIL",
        "LANGFUSE_INIT_USER_PASSWORD",
    }
)


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def _generated_env() -> dict[str, str]:
    token = lambda: secrets.token_urlsafe(32)  # noqa: E731 - compact secret factory
    return {
        "LANGFUSE_POSTGRES_USER": "langfuse",
        "LANGFUSE_POSTGRES_PASSWORD": token(),
        "LANGFUSE_POSTGRES_DB": "langfuse",
        "LANGFUSE_SALT": token(),
        "LANGFUSE_ENCRYPTION_KEY": secrets.token_hex(32),
        "LANGFUSE_NEXTAUTH_SECRET": token(),
        "LANGFUSE_CLICKHOUSE_USER": "clickhouse",
        "LANGFUSE_CLICKHOUSE_PASSWORD": token(),
        "LANGFUSE_REDIS_PASSWORD": token(),
        "LANGFUSE_MINIO_USER": "minio",
        "LANGFUSE_MINIO_PASSWORD": token(),
        "LANGFUSE_INIT_ORG_ID": str(uuid.uuid4()),
        "LANGFUSE_INIT_PROJECT_ID": str(uuid.uuid4()),
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": "pk-lf-" + token(),
        "LANGFUSE_INIT_PROJECT_SECRET_KEY": "sk-lf-" + token(),
        "LANGFUSE_INIT_USER_EMAIL": "admin@medy.local",
        "LANGFUSE_INIT_USER_PASSWORD": token(),
    }


def _sync_app_env(values: dict[str, str]) -> None:
    if not APP_ENV.exists():
        raise RuntimeError("root .env is missing; create it from .env.example first")
    updates = {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "",
        "OTEL_EXPORTER_OTLP_HEADERS": "",
        "LANGFUSE_BASE_URL": "http://127.0.0.1:3000",
        "LANGFUSE_PUBLIC_KEY": values["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"],
        "LANGFUSE_SECRET_KEY": values["LANGFUSE_INIT_PROJECT_SECRET_KEY"],
    }
    found: set[str] = set()
    output: list[str] = []
    for raw in APP_ENV.read_text(encoding="utf-8").splitlines():
        stripped = raw.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in raw:
            output.append(raw)
            continue
        key = raw.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            found.add(key)
        else:
            output.append(raw)
    if found != set(updates):
        output.extend([f"{key}={value}" for key, value in updates.items() if key not in found])
    _write_private(APP_ENV, "\n".join(output) + "\n")


def init() -> dict[str, Any]:
    created = not DEPLOY_ENV.exists()
    values = _generated_env() if created else _read_env(DEPLOY_ENV)
    missing = sorted(key for key in _REQUIRED if not values.get(key))
    if missing:
        raise RuntimeError("Langfuse environment is incomplete: " + ",".join(missing))
    if created:
        _write_private(DEPLOY_ENV, "\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    else:
        os.chmod(DEPLOY_ENV, 0o600)
    _sync_app_env(values)
    # Parse the application configuration now, before containers are started. This catches conflicting
    # manual OTLP targets and proves the exact credentials/endpoint path the runtime will use.
    settings = Settings()
    if settings.langfuse_base_url != "http://127.0.0.1:3000":
        raise RuntimeError("application Langfuse target was not activated")
    return {"created": created, "app_configuration": "active", "secrets_printed": False}


def _client(settings: Settings) -> httpx.Client:
    assert settings.langfuse_public_key is not None and settings.langfuse_secret_key is not None
    return httpx.Client(
        base_url=settings.langfuse_base_url,
        auth=(settings.langfuse_public_key.get_secret_value(), settings.langfuse_secret_key.get_secret_value()),
        timeout=10,
        trust_env=False,
    )


def _wait_for(
    action: Callable[[], Any], predicate: Callable[[Any], bool], *, timeout_s: float = 90, interval_s: float = 1
) -> Any:
    deadline = time.monotonic() + timeout_s
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = action()
            if predicate(last):
                return last
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            pass
        time.sleep(interval_s)
    raise RuntimeError(f"Langfuse state did not converge within {timeout_s:g}s")


def check() -> dict[str, Any]:
    settings = Settings()
    if not settings.langfuse_base_url:
        raise RuntimeError("application Langfuse configuration is absent")
    with _client(settings) as client:
        health = client.get("/api/public/health")
        observations = client.get("/api/public/v2/observations", params={"fields": "core", "limit": 1})
    return {
        "health_http": health.status_code,
        "project_auth_http": observations.status_code,
        "ready": health.status_code == observations.status_code == 200,
    }


def _emit_trace(settings: Settings) -> str:
    trace_id = secrets.token_hex(16)
    options = telemetry.telemetry_options(settings)
    provider = telemetry.configure_telemetry(**options)
    if provider is None:
        raise RuntimeError("telemetry exporter is disabled")
    try:
        versions = {
            "policy_version": "fixture-policy-v1",
            "retrieval_version": "fixture-retrieval-v1",
            "model_config_version": "fixture-model-v1",
            "skill_version_set": ["fixture-skill-v1"],
        }
        with telemetry.run_metadata(trace_id, versions, kind="deployment_smoke"):
            with telemetry.span("harness.run", fixture=True):
                with telemetry.span("retrieval.fixture", candidate_count=2):
                    pass
                with telemetry.span("verifier.fixture", verdict="supported"):
                    pass
        telemetry.flush()
    finally:
        provider.shutdown()
        telemetry.set_tracer_provider(None)
    return trace_id


def _observations(client: httpx.Client, trace_id: str) -> list[dict[str, Any]]:
    response = client.get(
        "/api/public/v2/observations",
        params={"traceId": trace_id, "fields": "core", "limit": 50},
    )
    if response.status_code != 200:
        return []
    data = response.json().get("data")
    return data if isinstance(data, list) else []


def _scores(client: httpx.Client, trace_id: str, score_id: str) -> list[dict[str, Any]]:
    response = client.get(
        "/api/public/v3/scores",
        params=[("traceId", trace_id), ("id", score_id), ("limit", "10")],
    )
    if response.status_code != 200:
        return []
    data = response.json().get("data")
    return data if isinstance(data, list) else []


def _sender(settings: Settings) -> LangfuseScores:
    assert settings.langfuse_base_url and settings.langfuse_public_key and settings.langfuse_secret_key
    return LangfuseScores(
        settings.langfuse_base_url,
        settings.langfuse_public_key.get_secret_value(),
        settings.langfuse_secret_key.get_secret_value(),
    )


def _event(trace_id: str, suffix: str) -> dict[str, Any]:
    return score_event(
        identity=f"langfuse-smoke:{trace_id}:{suffix}",
        trace_id=trace_id,
        name="deployment_smoke",
        value=True,
        timestamp=datetime.now(UTC),
        metadata={
            "source": "synthetic_fixture",
            "evaluator": "langfuse_local.py",
            "rubric_version": "deployment-smoke-v1",
            "formal_gate": False,
        },
    )


def _wait_trace(settings: Settings, trace_id: str) -> list[dict[str, Any]]:
    with _client(settings) as client:
        return _wait_for(
            lambda: _observations(client, trace_id),
            lambda rows: len(rows) == 3 and all(row.get("traceId") == trace_id for row in rows),
        )


def _wait_score(settings: Settings, trace_id: str, score_id: str) -> list[dict[str, Any]]:
    with _client(settings) as client:
        return _wait_for(
            lambda: _scores(client, trace_id, score_id),
            lambda rows: len(rows) == 1 and rows[0].get("id") == score_id,
        )


def smoke() -> dict[str, Any]:
    settings = Settings()
    trace_id = _emit_trace(settings)
    observations = _wait_trace(settings, trace_id)
    event = _event(trace_id, "direct")
    feedback = feedback_event(
        {
            "feedback_id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "signal": "up",
            "created_at": datetime.now(UTC),
        },
        fact_plane="synthetic-fixture",
    )
    sender = _sender(settings)
    queue = ScoreQueue(QUEUE, sender.destination)
    try:
        queue.enqueue(event)
        queue.enqueue(feedback)
        delivery = queue.drain(sender)
        if delivery["acknowledged"] != 2 or delivery["failed"]:
            raise RuntimeError("synthetic scores were not acknowledged")
    finally:
        queue.close()
        sender.close()
    scores = _wait_score(settings, trace_id, event["id"])
    feedback_scores = _wait_score(settings, trace_id, feedback["id"])
    return {
        "model_calls": 0,
        "trace_id": trace_id,
        "observations": len(observations),
        "score_id": event["id"],
        "scores": len(scores) + len(feedback_scores),
        "feedback_linked": len(feedback_scores) == 1,
        "linked": True,
    }


def _compose(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", "--env-file", str(DEPLOY_ENV), "-f", str(COMPOSE), *args],
        cwd=ROOT,
        check=True,
    )


def outage_recovery() -> dict[str, Any]:
    settings = Settings()
    trace_id = _emit_trace(settings)
    observations = _wait_trace(settings, trace_id)
    event = _event(trace_id, "outage")
    initial = _sender(settings)
    queue = ScoreQueue(QUEUE, initial.destination)
    queue.enqueue(event)
    initial.close()

    _compose("stop", "langfuse-web")
    failed: dict[str, int]
    try:
        unavailable = _sender(settings)
        try:
            failed = queue.drain(unavailable)
        finally:
            unavailable.close()
        if failed["failed"] != 1 or failed["pending"] < 1 or failed["dead_lettered"]:
            raise RuntimeError("score queue did not retain the event during outage")
    finally:
        _compose("up", "-d", "--wait", "langfuse-web")

    # The first failure schedules the next attempt five seconds later.
    time.sleep(settings.langfuse_score_queue_backoff_base_s + 0.5)
    recovered_sender = _sender(settings)
    try:
        recovered = queue.drain(recovered_sender)
        duplicate_drain = queue.drain(recovered_sender)
    finally:
        recovered_sender.close()
        queue.close()
    if recovered["acknowledged"] != 1 or duplicate_drain["attempted"]:
        raise RuntimeError("score was not recovered exactly once")
    scores = _wait_score(settings, trace_id, event["id"])
    return {
        "model_calls": 0,
        "trace_id": trace_id,
        "observations": len(observations),
        "failure": failed,
        "recovery": recovered,
        "second_drain_attempts": duplicate_drain["attempted"],
        "remote_scores": len(scores),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "check", "smoke", "outage-recovery"))
    args = parser.parse_args()
    actions = {"init": init, "check": check, "smoke": smoke, "outage-recovery": outage_recovery}
    try:
        result = actions[args.action]()
    except Exception as exc:  # noqa: BLE001 - never print response bodies, URLs, or secrets from dependency errors
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
