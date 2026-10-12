"""JSONL serialization and atomic text replacement for maintained evaluation tools.

Keep each caller's historical key ordering explicit: the wire bytes bind reviews
and frozen manifests. This is file atomicity, not a multi-file transaction.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def jsonl_text(rows: Iterable[dict[str, Any]], *, sort_keys: bool = False) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=sort_keys) + "\n" for row in rows)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """The safety tooling's original sorted, UTF-8 wire format."""
    path.write_text(jsonl_text(rows, sort_keys=True), encoding="utf-8")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
