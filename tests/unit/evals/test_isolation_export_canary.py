import json
import subprocess
import sys

import pytest

from medops.evals.isolation import __main__ as cli
from medops.evals.isolation.canary import export_self_check
from medops.evals.isolation.contracts import IsolationError


def test_export_canary_uses_real_transport_and_preserves_unknown_qualification():
    result = export_self_check()
    assert result["format"] == "eval-export-canary-v1"
    assert result["checks"] == {
        "whole_paired_batch": True,
        "body_free_export": True,
        "partial_batch_denied": True,
        "rare_metric_both_arms_suppressed": True,
        "changed_rows_existing_grant_denied": True,
        "developer_grant_denied": True,
    }
    assert result["model_calls"] == 0 and result["qualification"] == "unknown"
    assert result["deployment_isolation_verified"] is result["independent_human_review_verified"] is False


@pytest.mark.parametrize(
    "flags,code",
    [
        ([], 2),
        (["--self-check", "--export-self-check"], 2),
        (["--input", "sealed.json"], 2),
        (["--export-self-check"], 0),
    ],
)
def test_cli_exposes_only_disposable_synthetic_checks(flags, code):
    result = subprocess.run(
        [sys.executable, "-m", "medops.evals.isolation", *flags], capture_output=True, text=True, check=False
    )
    assert result.returncode == code
    if code == 0:
        payload = json.loads(result.stdout)
        assert payload["format"] == "eval-export-canary-v1" and all(payload["checks"].values())
        assert "SYNTHETIC" not in result.stdout and not result.stderr
    else:
        assert not result.stdout


def test_export_cli_failure_reports_only_fixed_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["isolation", "--export-self-check"])

    def fail():
        raise IsolationError("batch_incomplete")

    monkeypatch.setattr(cli, "export_self_check", fail)
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out) == {"error": "batch_incomplete"}
