"""Credential handling for the operational pg_dump / pg_restore Docker clients."""

from __future__ import annotations

import os
from urllib.parse import quote, quote_plus, unquote, urlsplit


def pg_environment(password: str) -> dict[str, str]:
    """Docker's bare ``-e PGPASSWORD`` inherits this value, without putting it in argv."""
    env = dict(os.environ)
    env.pop("DATABASE_ADMIN_URL", None)
    env["PGPASSWORD"] = password
    return env


def safe_stderr(stderr: bytes, *, dsn: str, password: str, limit: int) -> str:
    """Remove known credentials before truncation; a cut through a secret must not expose a suffix."""
    text = stderr.decode("utf-8", errors="replace")
    secrets = {
        dsn,
        unquote(dsn),
        password,
        quote(password, safe=""),
        quote_plus(password),
        urlsplit(dsn).password or "",
    }
    for secret in sorted(secrets - {""}, key=len, reverse=True):
        text = text.replace(secret, "[redacted]")
    return text[-limit:]
