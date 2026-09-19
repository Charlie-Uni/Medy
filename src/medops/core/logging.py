"""Structured JSON logging with bounded redaction (baseline M0-05, INV-OBS-02/03).

One JSON object per line: ts, level, logger, event, trace_id, optional fields and exception.
Before serialization every value passes through `redact()`, which
- masks sensitive keys and secret-looking substrings,
- accepts only JSON-native types; bytes and unknown objects become safe placeholders (never `str()`),
- is bounded: depth, container size and string length are capped and cycles are cut.
If formatting still fails, a minimal safe record is emitted instead of the raw payload.

`configure_logging()` is for application entry points only (it replaces the root handlers).
Identity fields must already be surrogate ids; the redactor is a backstop, not a substitute, and
logs should not receive full queries or evidence text by default.

    logger.info("ask.received", extra={"fields": {"dept": "MA", "k": 20}})
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import islice
from typing import Final, TextIO

from medops.core.tracing import current_trace_id

REDACTED: Final = "[REDACTED]"
MAX_DEPTH: Final = 8
MAX_ITEMS: Final = 200
MAX_STRING: Final = 2000
MAX_STRING_PROCESS: Final = 20_000  # longer strings are not scanned at all; they become a placeholder
SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "client_secret",
        "private_key",
    }
)
_SENSITIVE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"sk-[A-Za-z0-9]{8,}"),  # no word boundaries: over-redacting glued text is the safe direction
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),  # JWT
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)
_NOISY_LOGGERS: Final = ("uvicorn.access", "httpx", "httpcore")


def _redact_str(value: str) -> str:
    """Redact first, truncate second, so a secret crossing the cut never survives as a fragment."""
    if len(value) > MAX_STRING_PROCESS:
        return f"<string len={len(value)} omitted>"
    for pattern in _SENSITIVE_PATTERNS:
        value = pattern.sub(REDACTED, value)
    if len(value) > MAX_STRING:
        value = value[:MAX_STRING] + f"<truncated {len(value) - MAX_STRING} chars>"
    return value


def _key(k: object) -> str:
    if isinstance(k, str):
        return _redact_str(k)
    if isinstance(k, (bool, int, float)):
        return str(k)
    return f"<key:{type(k).__name__}>"


def redact(value: object, *, _depth: int = 0, _seen: frozenset[int] = frozenset()) -> object:
    """Return a JSON-native, redacted, bounded copy of `value`."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<bytes len={len(value)}>"
    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        if id(value) in _seen:
            return "<cycle>"
        if _depth >= MAX_DEPTH:
            return "<max-depth>"
        seen = _seen | {id(value)}
        if isinstance(value, Mapping):
            out: dict[str, object] = {}
            # Read at most MAX_ITEMS + 1 entries; never materialize or stringify the rest.
            for i, (k, v) in enumerate(islice(value.items(), MAX_ITEMS + 1)):
                if i == MAX_ITEMS:
                    out["<truncated>"] = "more keys omitted"
                    break
                key = _key(k)
                out[key] = REDACTED if key.lower() in SENSITIVE_KEYS else redact(v, _depth=_depth + 1, _seen=seen)
            return out
        result: list[object] = []
        for i, v in enumerate(islice(value, MAX_ITEMS + 1)):
            if i == MAX_ITEMS:
                result.append("<truncated: more items omitted>")
                break
            result.append(redact(v, _depth=_depth + 1, _seen=seen))
        return result
    return f"<{type(value).__name__}>"


def _placeholder(obj: object) -> str:
    """Safety net for json.dumps: never stringify unknown objects."""
    return f"<{type(obj).__name__}>"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": current_trace_id(),
        }
        try:
            payload = dict(base)
            payload["event"] = redact(record.getMessage())
            fields = getattr(record, "fields", None)
            if isinstance(fields, Mapping):
                payload["fields"] = redact(fields)
            if record.exc_info:
                payload["exception"] = redact(self.formatException(record.exc_info))
            return json.dumps(payload, ensure_ascii=False, default=_placeholder)
        except (RecursionError, TypeError, ValueError) as exc:
            safe = dict(base)
            safe["event"] = "<log-format-error>"
            safe["error"] = type(exc).__name__
            return json.dumps(safe, ensure_ascii=False, default=_placeholder)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Install the JSON formatter on the root logger. Application entry points only: it replaces
    existing root handlers, so tests must save and restore root logger state around it."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
