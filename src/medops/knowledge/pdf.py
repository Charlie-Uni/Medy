"""Locked raw PDF text extraction, shared by production ingestion and probe tooling.

Never normalizes page text. extraction-v1 constants and warning behavior are preserved.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import logging
from io import BytesIO
from typing import Literal

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from medops.core.canonical import canonical_json

EXTRACTOR = "pypdf"
EXTRACTOR_VERSION = importlib.metadata.version("pypdf")
# The only parameter that changes pypdf's text output for our use; frozen as extraction-v1.
EXTRACTION_MODE: Literal["plain"] = "plain"
PARAMS: dict[str, str] = {"extraction_mode": EXTRACTION_MODE}
PARAMS_HASH = hashlib.sha256(canonical_json(PARAMS).encode("utf-8")).hexdigest()
RECORD_NAME = "extraction.json"


MAX_WARNING_MESSAGES = 100


class _WarningCounter(logging.Handler):
    """Counts pypdf warnings without silencing them: they signal skipped font parsing and mandate a quality
    review. The first MAX_WARNING_MESSAGES message texts are kept so the review can see what was skipped."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1
        if len(self.messages) < MAX_WARNING_MESSAGES:
            self.messages.append(record.getMessage()[:300])


def extraction_record() -> dict[str, object]:
    return {
        "extractor": EXTRACTOR,
        "extractor_version": EXTRACTOR_VERSION,
        "params": dict(PARAMS),
        "params_hash": PARAMS_HASH,
    }


def extract_pages(pdf_bytes: bytes) -> tuple[list[str], int]:
    """Raw text per physical page (1-based order) and the number of pypdf warnings emitted while extracting."""
    texts, messages = extract_pages_detailed(pdf_bytes)
    return texts, len(messages)


def extract_pages_detailed(pdf_bytes: bytes) -> tuple[list[str], list[str]]:
    """Raw text per physical page and the pypdf warning messages emitted while extracting (one entry per
    warning, texts capped at MAX_WARNING_MESSAGES). Warnings stay on the pypdf logger (visible to the
    caller); they are only recorded here. Unreadable files raise ValueError."""
    counter = _WarningCounter()
    logger = logging.getLogger("pypdf")
    logger.addHandler(counter)
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise ValueError("encrypted PDF is not accepted as a probe source")
        texts = [page.extract_text(extraction_mode=EXTRACTION_MODE) or "" for page in reader.pages]
    except PyPdfError as exc:
        raise ValueError(f"unreadable PDF: {exc}") from exc
    finally:
        logger.removeHandler(counter)
    if counter.count > len(counter.messages):
        counter.messages.append(f"... {counter.count - len(counter.messages)} more warnings not recorded")
    return texts, counter.messages
