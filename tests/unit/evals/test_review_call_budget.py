"""The model review call must pass its explicit cost limit to the CLI."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
HELPERS = runpy.run_path(str(REPO / "evals/main_set/tools/draft_common.py"))
RUNNER = runpy.run_path(str(REPO / "evals/main_set/tools/run_review.py"))


def test_new_review_honors_targeted_selection_before_call():
    assert RUNNER["selected_ids"](["ms-0002"], ["ms-0001", "ms-0002"]) == {"ms-0002"}
    assert RUNNER["selected_ids"](None, ["ms-0001", "ms-0002"]) == {"ms-0001", "ms-0002"}
    with pytest.raises(ValueError, match="--only"):
        RUNNER["selected_ids"](["ms-9999"], ["ms-0001", "ms-0002"])


def test_review_budget_reaches_cli_and_preserves_tools_off(monkeypatch, tmp_path):
    observed = []

    def run(cmd, **kwargs):
        observed.append(cmd)
        structured = {"verdict": "supported"}
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "subtype": "success",
                    "result": "human-readable summary",
                    "structured_output": structured,
                    "total_cost_usd": 0.03,
                    "modelUsage": {
                        "review-model": {
                            "inputTokens": 20,
                            "cacheReadInputTokens": 100,
                            "cacheCreationInputTokens": 80,
                            "outputTokens": 5,
                        }
                    },
                }
            ),
        )

    monkeypatch.setattr(HELPERS["subprocess"], "run", run)
    schema = {"type": "object", "properties": {"verdict": {"type": "string"}}, "required": ["verdict"]}
    reply, meta = HELPERS["run_claude"](
        "claude",
        "review-model",
        "high",
        "neutral",
        "input",
        tmp_path,
        max_cost_usd=0.25,
        json_schema=schema,
    )
    assert json.loads(reply) == {"verdict": "supported"} and meta["requested_max_cost_usd"] == 0.25
    assert meta["input_tokens"] == 20
    assert meta["cache_read_input_tokens"] == 100
    assert meta["cache_creation_input_tokens"] == 80
    assert meta["total_input_tokens"] == 200
    assert meta["output_tokens"] == 5 and meta["cost_usd"] == 0.03
    cmd = observed[0]
    assert cmd[cmd.index("--max-budget-usd") + 1] == "0.25"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == schema
    assert meta["json_schema_sha256"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cmd


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_budget_fails_before_any_model_call(monkeypatch, tmp_path, value):
    def run(*args, **kwargs):
        pytest.fail("invalid budget reached the model CLI")

    monkeypatch.setattr(HELPERS["subprocess"], "run", run)
    with pytest.raises(ValueError, match="finite and positive"):
        HELPERS["run_claude"]("claude", "review-model", "high", "neutral", "input", tmp_path, max_cost_usd=value)


@pytest.mark.parametrize("failure", ["failed", "model_mismatch", "non_json", "timeout", "not_started"])
def test_failed_call_preserves_actual_cost_and_private_cli_artifact(monkeypatch, tmp_path, failure):
    import subprocess

    def run(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("claude", 1, output=b"partial PRIVATE", stderr=b"private stderr")
        if failure == "not_started":
            raise FileNotFoundError("no binary")
        if failure == "non_json":
            return SimpleNamespace(returncode=1, stdout="PRIVATE non-json", stderr="detail")
        return SimpleNamespace(
            returncode=1 if failure == "failed" else 0,
            stderr="",
            stdout=json.dumps(
                {
                    "subtype": "error_during_execution" if failure == "failed" else "success",
                    "is_error": failure == "failed",
                    "total_cost_usd": 0.02,
                    "modelUsage": {"wrong" if failure == "model_mismatch" else "review-model": {"inputTokens": 10}},
                    "result": "PRIVATE payload",
                }
            ),
        )

    monkeypatch.setattr(HELPERS["subprocess"], "run", run)
    target = tmp_path / "call.json"
    with pytest.raises(HELPERS["ClaudeCallError"]) as caught:
        HELPERS["run_claude"](
            "claude", "review-model", "high", "neutral", "input", tmp_path, max_cost_usd=0.25, capture_path=target
        )
    meta = caught.value.metadata
    expected = 0 if failure == "not_started" else (None if failure in {"timeout", "non_json"} else 0.02)
    assert meta["cost_usd"] == expected and meta["cli_capture_sha256"]
    assert "PRIVATE" not in str(caught.value)
    assert target.stat().st_mode & 0o777 == 0o600
    assert json.loads(target.read_text())["stdout"] is not None
