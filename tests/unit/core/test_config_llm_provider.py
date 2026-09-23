"""ADR-0010: the runtime LLM key is optional, secret and never echoed; the monthly cap cannot be negative."""

import pytest
from pydantic import ValidationError

from medops.core.config import Settings

BASE = {
    "DATABASE_URL": "postgresql://u:p@localhost:5432/medops",
    "REDIS_URL": "redis://:p@localhost:6379/0",
}


def _settings(monkeypatch, **extra):
    for k, v in {**BASE, **extra}.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_openai_key_is_optional_and_masked(monkeypatch):
    assert _settings(monkeypatch).openai_api_key is None
    s = _settings(monkeypatch, OPENAI_API_KEY="sk-test-not-a-real-key")
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == "sk-test-not-a-real-key"
    assert "sk-test" not in repr(s) and "sk-test" not in str(s.openai_api_key)


def test_monthly_budget_defaults_to_the_decided_cap_and_rejects_negative(monkeypatch):
    assert _settings(monkeypatch).llm_monthly_budget_usd == 30.0
    assert _settings(monkeypatch, LLM_MONTHLY_BUDGET_USD="0").llm_monthly_budget_usd == 0.0
    with pytest.raises(ValidationError):
        _settings(monkeypatch, LLM_MONTHLY_BUDGET_USD="-1")
