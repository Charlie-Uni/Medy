"""Explicit CI gate: real image + BGE models + published policy + ready/not-ready.

Run separately with `-p tests.integration.conftest`. It is outside default discovery so a missing
image is an error when invoked, never a routine skip. All writes target the fixtures' throwaway DB.
"""

import json
import os
import subprocess
import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
import pytest
from tests.support.database import container_dsn
from tests.support.documents import document, job, source_object
from tests.support.identity import TestIssuer

from medops.application.policy_loader import load_released
from medops.infrastructure.db.policies import PgPolicyStore
from medops.retrieval.production import build_production_lexical_index

ROOT = Path(__file__).resolve().parents[2]


def private_diagnostic(stdout, stderr):
    """Optional private debugging files; never upload or print raw Docker / application output."""
    directory = os.environ.get("MEDOPS_TEST_CONTAINER_DIAGNOSTICS")
    if directory:
        path = Path(directory)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path / (uuid.uuid4().hex + ".log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write((stdout + "\n" + stderr)[-65536:])


def run(*args, timeout=30):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        private_diagnostic(result.stdout, result.stderr)
        pytest.fail(
            f"container gate command failed: {args[0]} (exit {result.returncode}; raw output withheld)", pytrace=False
        )
    return result.stdout


def container_status(name, path):
    value = run("exec", name, "python", "/app/ci_http_probe.py", "http://127.0.0.1:8000" + path).strip()
    return None if value == "None" else int(value)


def wait_status(name, path, expected, *, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if run("inspect", "--format", "{{.State.Running}}", name).strip() != "true":
            pytest.fail("runtime container exited before readiness (raw logs withheld)", pytrace=False)
        if container_status(name, path) == expected:
            return
        time.sleep(1)
    pytest.fail(f"container endpoint did not reach HTTP {expected} within {timeout}s", pytrace=False)


def test_published_configuration_boots_and_lost_index_fails_readiness(migrated, login_users, tmp_path):
    image = os.environ.get("MEDOPS_TEST_RUNTIME_IMAGE")
    assert image, "explicit MEDOPS_TEST_RUNTIME_IMAGE is required; no old default image fallback"
    models = Path(os.environ["MEDOPS_TEST_MODEL_CACHE"]).resolve()
    assert models.is_dir(), "pinned public model cache is required"
    host = os.environ["MEDOPS_TEST_CONTAINER_DB_HOST"]
    network = os.environ["MEDOPS_TEST_CONTAINER_NETWORK"]
    policies = json.loads((ROOT / "deploy/ci/released-policies.json").read_text())["policies"]
    with psycopg.connect(migrated) as c:
        src = source_object(c, 187001)
        doc = document(c, src, job(c, src), status="active", effective_from=date(2026, 1, 1))
        c.execute("insert into document_acl values (%s, 'MA', 'read', 'ci', now())", (doc,))
        c.execute(
            "insert into chunks (doc_id,seq,page,content) values (%s,0,1,'Synthetic container readiness document.')",
            (doc,),
        )
        build_production_lexical_index(c, built_by="ci-container-only")
    with psycopg.connect(login_users["admin"]["dsn"]) as c:
        store = PgPolicyStore(c)
        for p in policies:
            pid = store.insert_candidate(**p, evidence={"ci_fixture": True}, created_by="ci:fixture")
            assert store.decide(
                pid, status="approved", decided_by="ci:fixture", reason="isolated fixture", at=datetime.now(UTC)
            )
            store.release(
                pid, kind=p["kind"], name=p["name"], actor="ci:fixture", reason="isolated fixture", canary_percent=100
            )
    with psycopg.connect(login_users["app"]["dsn"]) as c:
        loaded = load_released(c)
        assert [
            {"kind": p.kind, "name": p.name, "version": p.version, "diff": dict(p.diff)} for p in loaded.policies
        ] == policies
    name = "medy-ci-runtime-" + uuid.uuid4().hex[:10]
    env_file = tmp_path / "runtime.env"
    env_file.write_text(
        "\n".join(
            f"{k}={v}"
            for k, v in {
                "APP_ENV": "test",
                "DEBUG": "false",
                "DOCS_ENABLED": "false",
                "DATABASE_URL": container_dsn(login_users["app"]["dsn"], host),
                "DATABASE_ADMIN_URL": container_dsn(login_users["admin"]["dsn"], host),
                "REDIS_URL": "redis://127.0.0.1:1/0",
                "RETRIEVAL_CACHE": "off",
                "OPENAI_API_KEY": "synthetic-ci-no-provider-key",
                "OPENAI_BASE_URL": "http://127.0.0.1:1",
                "LLM_MONTHLY_BUDGET_USD": "0",
                "OIDC_ISSUER": "https://ci.invalid",
                "OIDC_AUDIENCE": "ci",
                "OIDC_JWKS_JSON": json.dumps(TestIssuer().jwks, separators=(",", ":")),
                "IDENTITY_PSEUDONYM_KEY": "ci-only-synthetic-identity-key",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "OMP_NUM_THREADS": "2",
            }.items()
        )
        + "\n"
    )
    env_file.chmod(0o600)
    common = [
        "--network",
        network,
        "--add-host",
        "host.docker.internal:host-gateway",
        "--env-file",
        str(env_file),
        "--mount",
        f"type=bind,source={models},target=/models,readonly",
        "--mount",
        f"type=bind,source={ROOT / 'deploy/ci/http_probe.py'},target=/app/ci_http_probe.py,readonly",
        "--memory",
        os.environ.get("MEDOPS_TEST_CONTAINER_MEMORY", "6g"),
        "--cpus",
        "2",
        "--pids-limit",
        "128",
        "--label",
        "medy.ci-runtime=1",
    ]
    try:
        # Build real BGE embeddings inside the exact image first; never label hashing vectors as production.
        run(
            "run",
            "--rm",
            "--name",
            name + "-index",
            *common,
            image,
            "python",
            "-m",
            "medops.retrieval.production",
            "build-embeddings",
            "--device",
            "cpu",
            "--built-by",
            "ci-container-only",
            timeout=300,
        )
        run("run", "-d", "--name", name, "--init", *common, image)
        wait_status(name, "/healthz", 200, timeout=180)
        wait_status(name, "/readyz", 200, timeout=30)
        assert run("exec", name, "id", "-u").strip() == "10001"
        with psycopg.connect(migrated) as c:
            assert c.execute("select count(*) from llm_spend_reservations").fetchone()[0] == 0
            c.execute("delete from chunk_embeddings")
        wait_status(name, "/readyz", 503, timeout=15)
        assert container_status(name, "/healthz") == 200
        print(
            json.dumps(
                {
                    "published_versions": [p["version"] for p in policies],
                    "ready": 200,
                    "missing_index": 503,
                    "uid": 10001,
                    "hosted_calls": 0,
                }
            )
        )
    except BaseException:
        logs = subprocess.run(["docker", "logs", "--tail", "100", name], capture_output=True, text=True, timeout=10)
        private_diagnostic(logs.stdout, logs.stderr)
        raise
    finally:
        # No global prune or shared service shutdown. Bound model mount prevents anonymous-volume leakage.
        try:
            subprocess.run(["docker", "rm", "-f", name, name + "-index"], capture_output=True, timeout=30)
            assert not run("ps", "-aq", "--filter", f"name=^/{name}(-index)?$").strip(), "CI containers not removed"
        finally:
            env_file.unlink(missing_ok=True)
