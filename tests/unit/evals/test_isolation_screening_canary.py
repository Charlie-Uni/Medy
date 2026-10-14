import json
import subprocess
import sys

import pytest

from medops.evals.isolation.screening_canary import screening_self_check


def test_screening_canary_returns_six_actual_checks_and_no_body():
    result = screening_self_check()
    assert (
        result["format"] == "eval-screening-canary-v1" and len(result["checks"]) == 6 and all(result["checks"].values())
    )
    assert result["model_calls"] == 0 and result["qualification"] == "unknown"
    assert "SYNTHETIC" not in json.dumps(result)


@pytest.mark.parametrize(
    "flags,code",
    [
        (["--screening-self-check"], 0),
        (["--screening-self-check", "--self-check"], 2),
        (["--screening-self-check", "--export-self-check"], 2),
        (["--screening-self-check", "--input", "history.json"], 2),
    ],
)
def test_screening_cli_accepts_only_disposable_public_check(flags, code):
    result = subprocess.run(
        [sys.executable, "-m", "medops.evals.isolation", *flags], capture_output=True, text=True, check=False
    )
    assert result.returncode == code
    if code == 0:
        assert json.loads(result.stdout)["format"] == "eval-screening-canary-v1" and not result.stderr
    else:
        assert not result.stdout
