"""The local ARCH-12 diagnostic cannot silently pick a developer DB or print secrets."""

import json
import sys

import pytest
from tests.diagnostics import request_transactions as probe


@pytest.mark.parametrize(
    "args", [["--concurrency", "1"], ["--rounds", "0"], ["--wait-ms", "nan"], ["--wait-ms", "1001"]]
)
def test_invalid_workload_is_rejected_before_connecting(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["probe", *args])
    monkeypatch.setattr(probe, "run", lambda **_: pytest.fail("must not connect"))
    with pytest.raises(SystemExit) as exc:
        probe.main()
    assert exc.value.code == 2


def test_missing_explicit_url_has_no_environment_file_fallback(monkeypatch, capsys):
    monkeypatch.delenv("MEDOPS_TEST_ADMIN_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["probe"])
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "error_type": "ValueError"}


def test_failure_reports_only_type_and_no_dsn_or_exception_text(monkeypatch, capsys):
    def fail(**_):
        raise RuntimeError("postgresql://SENSITIVE_SENTINEL@host/db")

    monkeypatch.setattr(probe, "run", fail)
    monkeypatch.setattr(sys, "argv", ["probe"])
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "failed", "error_type": "RuntimeError"}
    assert "SENSITIVE_SENTINEL" not in captured.out + captured.err
