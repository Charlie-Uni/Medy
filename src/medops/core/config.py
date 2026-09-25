"""Runtime configuration from environment variables (baseline 4.3, 5.12; M0-02).

Values come from the process environment or a local `.env` file that is never committed;
`.env.example` documents every key. Unknown keys in the `.env` file or explicit constructor
input are rejected (`extra="forbid"`); unknown *process* environment variables are ignored,
as pydantic-settings only reads declared names from the environment.

Connection strings carry passwords, so they are stored as `SecretStr` like every other secret:
masked in `repr()`, `model_dump()`, JSON and logs. Consumers call `.get_secret_value()` at the
point of connecting. DSN format is still validated, and `str(ValidationError)` never echoes the
value. That protection does NOT extend to `ValidationError.errors()` / `.json()`: pydantic keeps the
raw `input` there. Entry points must therefore report configuration failures only through
`safe_config_errors()` and must never log or return the raw structured form.
Production forbids debug and interactive API docs (baseline 5.12).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

_POSTGRES = TypeAdapter(PostgresDsn)
_REDIS = TypeAdapter(RedisDsn)


def safe_config_errors(exc: ValidationError) -> list[dict[str, object]]:
    """The only allowed structured form of a configuration error: location, type and message,
    without `input`, `ctx` or documentation URLs, so secrets in DSNs never reach logs or responses."""
    return [
        {"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]}
        for e in exc.errors(include_input=False, include_context=False, include_url=False)
    ]


def _check_dsn(adapter: TypeAdapter, value: SecretStr, label: str) -> SecretStr:
    try:
        adapter.validate_python(value.get_secret_value())
    except ValidationError as exc:  # never include the input in the raised message
        raise ValueError(
            f"{label} is not a valid DSN ({exc.error_count()} validation error(s); value withheld)"
        ) from None
    return value


class AppEnv(StrEnum):
    dev = "dev"
    test = "test"
    prod = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="forbid", frozen=True, hide_input_in_errors=True
    )

    app_env: AppEnv = AppEnv.dev
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")
    debug: bool = False
    docs_enabled: bool = True  # interactive API docs; must be off in prod

    # Idempotency-Key retention (baseline 3.2): at least 24 h and not shorter than the task lifetime;
    # the value is published in the OpenAPI document (M0-08).
    idempotency_key_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=24 * 3600)

    # Fact plane and cache. The application role must be NOSUPERUSER NOBYPASSRLS (baseline 3.7);
    # migrations use a separate admin DSN that never reaches request handlers.
    database_url: SecretStr
    database_admin_url: SecretStr | None = None
    # Read-only LOGIN user for the MCP server (INV-AUTH-04): the database proves the tools cannot write.
    database_readonly_url: SecretStr | None = None
    database_restricted_url: SecretStr | None = None  # restricted payload reader / retention (DEC-013)
    # every runtime connection fails fast instead of hanging when PostgreSQL is unreachable or stalled (record 78)
    db_connect_timeout_s: int = Field(default=5, ge=1, le=60)
    db_statement_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    redis_url: SecretStr
    # Retrieval candidate cache TTL (M1-19). Entries also die with the department epoch on publish events.
    retrieval_cache_ttl_seconds: int = Field(default=300, ge=1, le=86400)
    # Antivirus hook for ingestion (ADR-0009 §4): clamd INSTREAM at tcp://host:port or unix:///path.
    # Optional in dev/test (the ingest audit records `av_scan: skipped`); required in prod.
    clamd_address: str | None = Field(default=None, pattern=r"^(tcp://[^/\s]+:\d{1,5}|unix:///\S+)$")
    # Local model cache for the optional embedding/reranker stack (ADR-0007); default ~/.cache/medops-models.
    model_cache_dir: str | None = None

    # Compose bootstrap values (docker-compose.yml reads the same .env); optional for the app itself.
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None

    # Login users for the group roles of migration 0002 (python -m medops.infrastructure.db.login_users); masked.
    db_app_password: SecretStr | None = None
    db_readonly_password: SecretStr | None = None
    db_admin_password: SecretStr | None = None
    db_restricted_password: SecretStr | None = None  # optional LOGIN user for medops_restricted_role

    # Secrets that later milestones consume; masked everywhere.
    redis_password: SecretStr | None = None
    identity_pseudonym_key: SecretStr | None = None  # HMAC key for surrogate ids (INV-OBS-02)
    payload_key_file: str | None = None  # JSON KEK file for restricted payloads (DEC-013); unset = payloads not written
    payload_retention_days: int = Field(default=90, ge=1)
    escalation_payload_grace_days: int = Field(default=30, ge=0)
    # Runtime LLM provider (ADR-0010 / DEC-009): OpenAI API key and the monthly spend cap enforced by the
    # Model Gateway ledger (M2-06). Offline drafting/review keep using subscription CLIs and never read this key.
    openai_api_key: SecretStr | None = None
    llm_monthly_budget_usd: float = Field(default=30.0, ge=0)
    # Identity boundary (ADR-0001, M3-05): OIDC issuer/audience the API accepts and the JWK set it trusts (a JSON
    # document; dev/test use the local synthetic issuer). Group claims map to scopes only via the allowlist JSON.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_json: str | None = None
    oidc_jwks_url: str | None = None  # explicit JWKS URL; unset -> OIDC discovery from the issuer
    oidc_group_scopes_json: str | None = None
    # Telemetry (M3-09): OTLP/HTTP collector endpoint (e.g. http://otel-collector:4318); unset -> spans are not recorded.
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "medops-copilot"

    @field_validator(
        "postgres_password",
        "redis_password",
        "identity_pseudonym_key",
        "database_admin_url",
        "database_readonly_url",
        "db_app_password",
        "db_readonly_password",
        "db_admin_password",
        "clamd_address",
        "model_cache_dir",
        "oidc_issuer",
        "oidc_audience",
        "oidc_jwks_json",
        "oidc_jwks_url",
        "oidc_group_scopes_json",
        "otel_exporter_otlp_endpoint",
        mode="before",
    )
    @classmethod
    def _empty_secret_is_unset(cls, value: object) -> object:
        """`KEY=` in an env file must mean unset, never an empty secret that passes presence checks."""
        if isinstance(value, str) and value.strip() == "":
            return None
        if isinstance(value, SecretStr) and value.get_secret_value().strip() == "":
            return None
        return value

    @field_validator("database_url", "database_admin_url", "database_readonly_url")
    @classmethod
    def _postgres_dsn(cls, value: SecretStr | None) -> SecretStr | None:
        return None if value is None else _check_dsn(_POSTGRES, value, "database DSN")

    @field_validator("redis_url")
    @classmethod
    def _redis_dsn(cls, value: SecretStr) -> SecretStr:
        return _check_dsn(_REDIS, value, "redis DSN")

    @model_validator(mode="after")
    def _prod_hardening(self) -> Settings:
        if self.app_env is AppEnv.prod:
            if self.debug or self.docs_enabled:
                raise ValueError("prod forbids debug=true and docs_enabled=true (baseline 5.12)")
            if self.log_level == "DEBUG":
                raise ValueError("prod forbids DEBUG log level")
            if self.identity_pseudonym_key is None:
                raise ValueError("prod requires identity_pseudonym_key (INV-OBS-02)")
            if self.clamd_address is None:
                raise ValueError("prod requires clamd_address: ingested files must be virus-scanned (ADR-0009)")
        return self
