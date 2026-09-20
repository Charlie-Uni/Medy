"""Page-text extraction for probe-set sources (SPEC §4).

Writes the raw text of every physical page to ``<pages_dir>/<source_hash>/<page>.txt`` exactly as
``PageTextProvider`` reads it, plus ``extraction.json`` recording the frozen extraction parameters.
Page text is never normalized here: the validator applies norm-v1 itself.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
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


@dataclass(frozen=True)
class ExtractionResult:
    source_hash: str
    byte_size: int
    pages: int
    chars_per_page: tuple[int, ...]
    output_dir: Path
    extractor_warnings: int  # pypdf log records at WARNING or above (e.g. skipped font encoding parsing)

    @property
    def empty_pages(self) -> tuple[int, ...]:
        return tuple(i for i, n in enumerate(self.chars_per_page, 1) if n == 0)


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


def _write_file(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def write_pages(pdf_path: Path, pages_dir: Path) -> ExtractionResult:
    """Extract ``pdf_path`` into ``pages_dir/<sha256>/``.

    The directory is content-addressed and immutable: an existing directory must match byte for byte (no newline
    or encoding normalization), and a new one is written completely in a temporary directory and then published by
    a single rename, so a failed run leaves nothing behind.
    """
    data = Path(pdf_path).read_bytes()
    source_hash = hashlib.sha256(data).hexdigest()
    texts, warnings = extract_pages(data)
    record = {
        **extraction_record(),
        "source_hash": source_hash,
        "byte_size": len(data),
        "pages": len(texts),
        "chars_per_page": [len(t) for t in texts],
    }
    files = {f"{i}.txt": text.encode("utf-8") for i, text in enumerate(texts, 1)}
    files[RECORD_NAME] = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pages_dir = Path(pages_dir)
    out = pages_dir / source_hash
    if out.exists():
        for name, content in files.items():
            existing = out / name
            if not existing.is_file() or existing.read_bytes() != content:
                raise ValueError(f"{out} already exists with different content ({name}); sources are immutable")
        extra = {p.name for p in out.iterdir()} - set(files)
        if extra:
            raise ValueError(f"{out} contains unexpected files: {sorted(extra)}")
    else:
        pages_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{source_hash}.", dir=pages_dir))
        try:
            for name, content in files.items():
                _write_file(staging / name, content)
            staging.rename(out)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return ExtractionResult(source_hash, len(data), len(texts), tuple(len(t) for t in texts), out, warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m medops.evals.probe.extract", description="Extract page text for probe sources (SPEC §4)."
    )
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--pages", required=True, type=Path, help="pages_dir passed to the validator's --pages")
    args = parser.parse_args(argv)
    failed = 0
    for pdf in args.pdf:
        try:
            result = write_pages(pdf, args.pages)
        except (OSError, ValueError) as exc:
            failed += 1
            print(json.dumps({"file": str(pdf), "error": str(exc)}, ensure_ascii=False))
            continue
        # extractor_warnings > 0 means pypdf skipped part of the font parsing (its warnings are printed above):
        # the page text must pass a quality review before any page is used as a gold source (SPEC §4).
        print(
            json.dumps(
                {
                    "file": str(pdf),
                    "source_hash": result.source_hash,
                    "byte_size": result.byte_size,
                    "pages": result.pages,
                    "empty_pages": list(result.empty_pages),
                    "extractor_warnings": result.extractor_warnings,
                    "extractor_version": EXTRACTOR_VERSION,
                    "params_hash": PARAMS_HASH,
                },
                ensure_ascii=False,
            )
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
