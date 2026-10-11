"""Required CI services fail closed; local optional services may be absent.

This governs PostgreSQL, Redis and Compose, not the separate DEC-001 experiment servers.
"""

import os
from typing import NoReturn

import pytest


def required_services() -> bool:
    value = os.environ.get("MEDOPS_TEST_REQUIRED_SERVICES", "").lower()
    if value not in {"", "0", "1", "false", "true"}:
        raise pytest.UsageError("MEDOPS_TEST_REQUIRED_SERVICES must be 0/1 or false/true")
    ci = any(os.environ.get(key, "").lower() in {"1", "true"} for key in ("CI", "GITHUB_ACTIONS"))
    return ci or value in {"1", "true"}


def unavailable(reason: str) -> NoReturn:
    """Reasons must be fixed text / exception types, never URLs or exception messages."""
    if required_services():
        pytest.fail(f"required dependency: {reason}", pytrace=False)
    pytest.skip(f"optional local dependency: {reason}")
