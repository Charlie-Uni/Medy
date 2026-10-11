"""Page-text extraction for probe-set sources (SPEC §4).

Writes the raw text of every physical page to ``<pages_dir>/<source_hash>/<page>.txt`` exactly as
``PageTextProvider`` reads it, plus ``extraction.json`` recording the frozen extraction parameters.
Page text is never normalized here: the validator applies norm-v1 itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from medops.knowledge import pdf


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
    texts, warnings = pdf.extract_pages(data)
    record = {
        **pdf.extraction_record(),
        "source_hash": source_hash,
        "byte_size": len(data),
        "pages": len(texts),
        "chars_per_page": [len(t) for t in texts],
    }
    files = {f"{i}.txt": text.encode("utf-8") for i, text in enumerate(texts, 1)}
    files[pdf.RECORD_NAME] = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
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
    for pdf_path in args.pdf:
        try:
            result = write_pages(pdf_path, args.pages)
        except (OSError, ValueError) as exc:
            failed += 1
            print(json.dumps({"file": str(pdf_path), "error": str(exc)}, ensure_ascii=False))
            continue
        # extractor_warnings > 0 means pypdf skipped part of the font parsing (its warnings are printed above):
        # the page text must pass a quality review before any page is used as a gold source (SPEC §4).
        print(
            json.dumps(
                {
                    "file": str(pdf_path),
                    "source_hash": result.source_hash,
                    "byte_size": result.byte_size,
                    "pages": result.pages,
                    "empty_pages": list(result.empty_pages),
                    "extractor_warnings": result.extractor_warnings,
                    "extractor_version": pdf.EXTRACTOR_VERSION,
                    "params_hash": pdf.PARAMS_HASH,
                },
                ensure_ascii=False,
            )
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
