import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from medops.core.config import AppEnv, Settings

REPO = Path(__file__).resolve().parents[3]
BASE = {"DATABASE_URL": "postgresql://u:p@localhost:5432/db", "REDIS_URL": "redis://:pw@localhost:6379/0"}


def _settings(monkeypatch, **env):
    for k in list(os.environ):
        if k.startswith(("APP_", "DATABASE_", "REDIS_", "IDENTITY_", "LOG_", "DEBUG", "DOCS_")):
            monkeypatch.delenv(k, raising=False)
    for k, v in {**BASE, **env}.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


def test_defaults_are_dev_safe(monkeypatch):
    s = _settings(monkeypatch)
    assert s.app_env is AppEnv.dev and s.debug is False and s.docs_enabled is True and s.log_level == "INFO"


def test_unknown_keys_and_bad_dsn_are_rejected(monkeypatch):
    with pytest.raises(ValidationError):
        _settings(monkeypatch, DATABASE_URL="mysql://x")
    monkeypatch.setenv("DATABASE_URL", BASE["DATABASE_URL"])
    with pytest.raises(ValidationError):
        Settings(_env_file=None, unknown_key="x", **{k.lower(): v for k, v in BASE.items()})


def test_prod_hardening(monkeypatch):
    with pytest.raises(ValidationError, match="prod forbids"):
        _settings(monkeypatch, APP_ENV="prod", DOCS_ENABLED="true", DEBUG="false", IDENTITY_PSEUDONYM_KEY="k" * 64)
    with pytest.raises(ValidationError, match="identity_pseudonym_key"):
        _settings(monkeypatch, APP_ENV="prod", DOCS_ENABLED="false", DEBUG="false")
    with pytest.raises(ValidationError, match="identity_pseudonym_key"):  # empty value is unset, not a key
        _settings(monkeypatch, APP_ENV="prod", DOCS_ENABLED="false", DEBUG="false", IDENTITY_PSEUDONYM_KEY="   ")
    ok = _settings(monkeypatch, APP_ENV="prod", DOCS_ENABLED="false", DEBUG="false", IDENTITY_PSEUDONYM_KEY="k" * 64)
    assert ok.app_env is AppEnv.prod


def test_secrets_are_masked_in_repr_and_dump(monkeypatch):
    s = _settings(monkeypatch, IDENTITY_PSEUDONYM_KEY="SYNTHETIC-SECRET-VALUE", REDIS_PASSWORD="SYNTHETIC-REDIS-PW")
    assert "SYNTHETIC" not in repr(s) and "SYNTHETIC" not in str(s.model_dump())
    assert (
        s.identity_pseudonym_key is not None and s.identity_pseudonym_key.get_secret_value() == "SYNTHETIC-SECRET-VALUE"
    )


def test_env_example_parses_and_contains_no_real_looking_secret(monkeypatch):
    for k in list(os.environ):
        if k.startswith(("APP_", "DATABASE_", "REDIS_", "IDENTITY_", "LOG_", "DEBUG", "DOCS_", "POSTGRES_")):
            monkeypatch.delenv(k, raising=False)
    example = REPO / ".env.example"
    s = Settings(_env_file=example)
    assert s.app_env is AppEnv.dev and s.identity_pseudonym_key is None
    text = example.read_text(encoding="utf-8")
    assert "change-me" in text and "sk-" not in text and "BEGIN PRIVATE KEY" not in text


def test_dsn_passwords_are_masked_everywhere_and_available_on_request(monkeypatch):
    import json

    from medops.core.logging import redact

    pw = "SYNTHETIC-DSN-PASSWORD-9f8e7d"
    s = _settings(
        monkeypatch,
        DATABASE_URL=f"postgresql://app:{pw}@db:5432/medops",
        DATABASE_ADMIN_URL=f"postgresql://admin:{pw}@db:5432/medops",
        REDIS_URL=f"redis://:{pw}@cache:6379/0",
    )
    surfaces = [
        repr(s),
        str(s),
        str(s.model_dump()),
        s.model_dump_json(),
        json.dumps(redact(s.model_dump()), ensure_ascii=False, default=str),
    ]
    assert all(pw not in surface for surface in surfaces)
    assert s.database_url.get_secret_value().endswith("@db:5432/medops") and pw in s.redis_url.get_secret_value()


def test_invalid_dsn_error_does_not_echo_the_value(monkeypatch):
    pw = "SYNTHETIC-LEAK-CHECK-1234"
    with pytest.raises(ValidationError) as exc:
        _settings(monkeypatch, DATABASE_URL=f"mysql://app:{pw}@db/medops")
    assert pw not in str(exc.value) and "value withheld" in str(exc.value)
    with pytest.raises(ValidationError) as exc2:
        _settings(monkeypatch, REDIS_URL=f"postgresql://x:{pw}@h/db")
    assert pw not in str(exc2.value)


def test_unknown_process_env_is_ignored_but_unknown_dotenv_key_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("TOTALLY_UNRELATED_VAR", "x")
    assert _settings(monkeypatch).app_env is AppEnv.dev
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://u:p@h:5432/d\nREDIS_URL=redis://:p@h:6379/0\nMISTYPED_KEY=1\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_structured_error_output_contract(monkeypatch):
    """Raw errors()/json() keep pydantic's `input` (documented, not safe); safe_config_errors is the only allowed form."""
    import json

    from medops.core.config import safe_config_errors
    from medops.core.logging import redact

    pw = "SYNTHETIC-STRUCTURED-LEAK-42"
    with pytest.raises(ValidationError) as exc:
        _settings(monkeypatch, DATABASE_URL=f"mysql://app:{pw}@db/medops")
    err = exc.value
    assert pw in json.dumps(err.errors(), default=str) and pw in err.json()  # characterization: raw forms are unsafe
    safe = safe_config_errors(err)
    assert safe and all(set(e) == {"loc", "type", "msg"} for e in safe)
    assert pw not in json.dumps(safe, ensure_ascii=False) and pw not in json.dumps(redact(safe), ensure_ascii=False)
    assert safe[0]["loc"] == ["database_url"] and "value withheld" in safe[0]["msg"]
