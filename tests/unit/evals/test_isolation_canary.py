import json

from medops.evals.isolation.__main__ import main
from medops.evals.isolation.canary import self_check


def test_synthetic_canary_runs_real_boundaries_and_never_qualifies_unseen():
    result = self_check()
    assert len(result["checks"]) == 9 and all(result["checks"].values())
    assert result["model_calls"] == 0 and result["qualification"] == "unknown"
    assert result["deployment_isolation_verified"] is False


def test_cli_outputs_only_public_summary(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["isolation", "--self-check"])
    assert main() == 0
    output = capsys.readouterr().out
    assert json.loads(output)["model_calls"] == 0
    assert "SYNTHETIC GOLD CANARY" not in output and "PUBLIC SYNTHETIC QUERY" not in output
