"""Render Compose with synthetic config to check isolation, process supervision and container resources."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.service_requirements import required_services, unavailable

ROOT = Path(__file__).resolve().parents[3]


def configuration(tmp_path, *, payload=False):
    required_services()  # Validate the mode even when Docker is healthy.
    if not shutil.which("docker"):
        unavailable("Docker Compose unavailable")
    env = dict(os.environ)
    # Compose interpolation uses process values before --env-file. No real local DSN/key is needed here.
    for name in (
        "DATABASE_URL",
        "DATABASE_ADMIN_URL",
        "DATABASE_READONLY_URL",
        "DATABASE_LOOP_URL",
        "DATABASE_RESTRICTED_URL",
        "REDIS_URL",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "RETRIEVAL_CACHE_DATABASE",
    ):
        env.pop(name, None)
        env.pop(name + "_DOCKER", None)
    # Render from an isolated directory containing public inputs only. This
    # avoids reading a developer's optional .env without depending on the newer
    # --no-env-resolution flag, which is absent from some CI Compose versions.
    manifest = tmp_path / "compose-input"
    manifest.mkdir(exist_ok=True)
    for name in (".env.example", "docker-compose.yml", "docker-compose.payload.yml"):
        shutil.copyfile(ROOT / name, manifest / name)
    # Services declare env_file: .env. Some Compose releases still require the
    # file with --no-env-resolution; CI has no private .env. Supply public test
    # defaults in the isolated directory, never copy the developer's file.
    shutil.copyfile(manifest / ".env.example", manifest / ".env")
    cmd = [
        "docker",
        "compose",
        "--env-file",
        str(manifest / ".env.example"),
        "-f",
        str(manifest / "docker-compose.yml"),
    ]
    if payload:
        key = tmp_path / "synthetic-kek.json"
        key.write_text("{}")  # no decryption attempted; config render needs a mount source only
        key.chmod(0o600)
        env["PAYLOAD_KEY_FILE"] = str(key)
        cmd += ["-f", str(manifest / "docker-compose.payload.yml")]
    for profile in ("app", "score-sync", "maintenance", "loop-observe"):
        cmd += ["--profile", profile]
    version = subprocess.run(["docker", "compose", "version"], env=env, capture_output=True, timeout=10)
    if version.returncode:
        unavailable("Docker Compose plugin unavailable")
    result = subprocess.run(
        [*cmd, "config", "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, "Compose render failed (raw output withheld: it may contain environment secrets)"
    return json.loads(result.stdout)


def test_supervised_workers_have_correct_database_deadlines_and_health(tmp_path):
    config = configuration(tmp_path)
    services = config["services"]
    expected = {
        "lexical-index-worker": "lexical-index",
        "vector-index-worker": "vector-index",
        "retrieval-cache-worker": "retrieval-cache",
    }
    for name, consumer in expected.items():
        service = services[name]
        command = service["command"]
        assert command[2] == "medops.worker.supervision"
        assert command[command.index("--database") + 1] == "medops"
        assert command[command.index("--consumer") + 1] == consumer
    for name in (*expected, "worker", "score-sync-worker", "payload-retention", "audit-retention", "loop-observe"):
        service = services[name]
        assert service["init"] is True and service["restart"] == "unless-stopped"
        assert int(service["mem_limit"]) > 0 and service["cpus"] > 0 and service["pids_limit"] > 0
        assert service["healthcheck"]["test"][-1] == "--check"
    task = services["worker"]
    grace = float(task["command"][task["command"].index("--grace") + 1])
    stop_seconds = sum(
        float(n) * {"h": 3600, "m": 60, "s": 1}[unit]
        for n, unit in re.findall(r"(\d+(?:\.\d+)?)([hms])", task["stop_grace_period"])
    )
    assert stop_seconds > grace >= 120
    assert "8001" in services["mcp"]["healthcheck"]["test"][-1]
    for name in ("api", "worker", "mcp"):
        assert services[name]["environment"]["GLOSSARY_DIR"] == "/app/glossary"
    assert any(v["target"] == "/queue" and v["type"] == "volume" for v in services["score-sync-worker"]["volumes"])
    loop = services["loop-observe"]["command"]
    assert loop[loop.index("--job") + 1] == "loop-observe"
    assert loop[loop.index("--since") + 1] == "1970-01-01"


def test_payload_overlay_mounts_secret_only_in_writing_runtimes(tmp_path):
    services = configuration(tmp_path, payload=True)["services"]
    for name in ("api", "worker"):
        assert services[name]["environment"]["PAYLOAD_KEY_FILE"] == "/run/secrets/payload-kek"
        assert services[name]["secrets"][0]["source"] == "payload-kek"
    for name in ("mcp", "payload-retention", "loop-observe", "score-sync-worker"):
        assert not services[name].get("secrets")


def test_manifest_render_does_not_require_a_private_dotenv(tmp_path, monkeypatch):
    for name in (".env.example", "docker-compose.yml", "docker-compose.payload.yml"):
        shutil.copy2(ROOT / name, tmp_path / name)
    monkeypatch.setattr(__import__(__name__, fromlist=["ROOT"]), "ROOT", tmp_path)
    assert not (tmp_path / ".env").exists()
    assert configuration(tmp_path)["services"]["api"]["environment"]["GLOSSARY_DIR"] == "/app/glossary"


def test_manifest_render_never_reads_a_private_dotenv(tmp_path, monkeypatch):
    for name in (".env.example", "docker-compose.yml", "docker-compose.payload.yml"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    # Invalid syntax is deliberate: reading it would fail, even if an otherwise
    # valid private environment happened to have the same public settings.
    (tmp_path / ".env").write_text('BROKEN="unterminated\n')
    monkeypatch.setattr(__import__(__name__, fromlist=["ROOT"]), "ROOT", tmp_path)
    assert configuration(tmp_path)["services"]["api"]["environment"]["GLOSSARY_DIR"] == "/app/glossary"


def test_missing_docker_is_an_error_in_required_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDOPS_TEST_REQUIRED_SERVICES", "1")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(pytest.fail.Exception, match="required dependency: Docker"):
        configuration(tmp_path)


def test_missing_compose_plugin_is_an_error_in_required_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDOPS_TEST_REQUIRED_SERVICES", "1")
    monkeypatch.setattr(shutil, "which", lambda _: "/synthetic/docker")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1))
    with pytest.raises(pytest.fail.Exception, match="required dependency: Docker Compose plugin"):
        configuration(tmp_path)
