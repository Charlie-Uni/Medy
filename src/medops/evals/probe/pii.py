"""PII rule set `pii-rules-v1` used by probe validator rule PR-07 (SPEC section 10).

The probe set may only contain public documents; these patterns catch the obvious
personal-data shapes that would indicate a non-public source slipped in.
"""

from __future__ import annotations

import re

PII_RULESET_VERSION = "pii-rules-v1"

_PATTERNS: dict[str, re.Pattern[str]] = {
    "cn_id_card": re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"),
    "cn_mobile": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "patient_identifier": re.compile(r"(患者姓名|病历号|住院号|身份证号|medical record number)\s*[:：]?\s*\S+"),
}


def find_pii(text: str) -> list[str]:
    """Return the names of PII patterns that match `text` (empty list when clean)."""
    return [name for name, pattern in _PATTERNS.items() if pattern.search(text)]


def find_pii_matches(text: str) -> list[tuple[str, str]]:
    """Every (rule name, matched text) pair in `text`, in document order per rule; for review and audit."""
    return [(name, match.group(0)) for name, pattern in _PATTERNS.items() for match in pattern.finditer(text)]


def find_pii_spans(text: str) -> list[tuple[str, str, int, int]]:
    """Exact per-hit positions in the scanned field; offsets distinguish repeated matches."""
    return [
        (name, match.group(0), match.start(), match.end())
        for name, pattern in _PATTERNS.items()
        for match in pattern.finditer(text)
    ]
