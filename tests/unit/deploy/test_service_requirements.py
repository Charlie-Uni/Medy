"""Exercise actual pytest exit codes, not just the skip/fail helper's branches."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.service_requirements import required_services

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("ci", ["CI", "GITHUB_ACTIONS"])
def test_ci_cannot_opt_out(monkeypatch, ci):
    monkeypatch.setenv(ci, "true")
    monkeypatch.setenv("MEDOPS_TEST_REQUIRED_SERVICES", "0")
    assert required_services()


def test_invalid_mode_is_configuration_error(monkeypatch):
    monkeypatch.setenv("MEDOPS_TEST_REQUIRED_SERVICES", "typo")
    with pytest.raises(pytest.UsageError, match="must be"):
        required_services()


def test_explicit_urls_do_not_bypass_mode_validation(monkeypatch):
    from tests.integration.conftest import _admin_dsn, _redis_url

    monkeypatch.setenv("MEDOPS_TEST_REQUIRED_SERVICES", "typo")
    monkeypatch.setenv("MEDOPS_TEST_ADMIN_URL", "synthetic")
    monkeypatch.setenv("MEDOPS_TEST_REDIS_URL", "synthetic")
    for resolve in (_admin_dsn, _redis_url):
        with pytest.raises(pytest.UsageError, match="must be"):
            resolve()


@pytest.mark.parametrize("service", ["PostgreSQL", "Redis"])
@pytest.mark.parametrize("fault", ["missing", "unreachable", "malformed"])
def test_required_fixture_has_nonzero_exit_without_secret(tmp_path, service, fault):
    result = _run_fixture(tmp_path, service, fault, required=True)
    assert result.returncode == 1, result.stdout
    assert "required dependency:" in result.stdout and "1 error" in result.stdout
    assert "SENSITIVE_SENTINEL" not in result.stdout and "1 skipped" not in result.stdout


@pytest.mark.parametrize("service", ["PostgreSQL", "Redis", "experiment"])
def test_optional_absence_remains_a_skip(tmp_path, service):
    # CI still permits missing optional DEC-001 experiment servers.
    result = _run_fixture(tmp_path, service, "missing", required=service == "experiment")
    assert result.returncode == 0, result.stdout
    assert "1 skipped" in result.stdout


def _run_fixture(tmp_path, service, fault, *, required):
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts=--tb=short\n")
    (tmp_path / "conftest.py").write_text(
        'pytest_plugins = ["tests.integration.conftest"]\n'
        "def pytest_configure():\n"
        "    from pathlib import Path\n"
        "    import tests.integration.conftest as fixtures\n"
        "    import tests.integration.lexical_adapter_suite as experiments\n"
        "    fixtures.REPO = experiments.REPO = Path(__file__).parent\n"
    )
    fixture = "admin_dsn" if service == "PostgreSQL" else "redis_url"
    body = f"def test_dependency({fixture}):\n    assert {fixture}\n"
    if service == "experiment":
        body = 'def test_dependency():\n    from tests.integration.lexical_adapter_suite import require_server\n    require_server("B")\n'
    (tmp_path / "test_dependency.py").write_text(body)
    env = dict(os.environ)
    for name in (
        "CI",
        "GITHUB_ACTIONS",
        "DEBUG",
        "MEDOPS_TEST_ADMIN_URL",
        "MEDOPS_TEST_REDIS_URL",
        "MEDOPS_TEST_B_ADMIN_URL",
        "DEC001_B_ADMIN_URL",
    ):
        env.pop(name, None)
    env["MEDOPS_TEST_REQUIRED_SERVICES"] = "1" if required else "0"
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    name = "MEDOPS_TEST_ADMIN_URL" if service == "PostgreSQL" else "MEDOPS_TEST_REDIS_URL"
    scheme = "postgresql" if service == "PostgreSQL" else "redis"
    if fault == "unreachable":
        env[name] = f"{scheme}://ci:SENSITIVE_SENTINEL@127.0.0.1:1/0"
    elif fault == "malformed":
        env[name] = "SENSITIVE_SENTINEL"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30
    )
