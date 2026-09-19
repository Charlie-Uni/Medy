"""Page-text extraction: layout consumed by PageTextProvider, immutability, frozen parameters."""

import hashlib
import json

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe import extract
from medops.evals.probe.validator import PageTextProvider


def _pdf(*page_texts: str) -> bytes:
    """Minimal valid PDF with one Helvetica text line per page (no compression, ASCII only)."""
    objs: list[bytes] = []
    n_pages = len(page_texts)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    font_id = 3 + 2 * n_pages
    for i, text in enumerate(page_texts):
        content = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {4 + 2 * i} 0 R >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_extracts_physical_pages_in_order(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_pdf("first page", "second page"))
    result = extract.write_pages(pdf, tmp_path / "pages")
    assert result.source_hash == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert result.pages == 2 and result.byte_size == pdf.stat().st_size
    provider = PageTextProvider(tmp_path / "pages")
    assert provider.page_text(result.source_hash, 1) == "first page"
    assert provider.page_text(result.source_hash, 2) == "second page"
    assert provider.page_text(result.source_hash, 3) is None
    record = json.loads((result.output_dir / extract.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["extractor"] == "pypdf" and record["extractor_version"] == extract.EXTRACTOR_VERSION
    assert record["params"] == {"extraction_mode": "plain"}
    assert record["params_hash"] == hashlib.sha256(canonical_json(record["params"]).encode()).hexdigest()
    assert record["chars_per_page"] == [10, 11] and record["source_hash"] == result.source_hash


def test_rerun_is_idempotent_and_conflicts_are_refused(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_pdf("same"))
    first = extract.write_pages(pdf, tmp_path / "pages")
    assert extract.write_pages(pdf, tmp_path / "pages") == first
    (first.output_dir / "1.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="immutable"):
        extract.write_pages(pdf, tmp_path / "pages")
    (first.output_dir / "1.txt").write_text("same", encoding="utf-8")
    (first.output_dir / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected files"):
        extract.write_pages(pdf, tmp_path / "pages")


def test_immutability_compares_raw_bytes_not_normalized_text(tmp_path):
    """Changing only the line endings of a published page must be detected (read_text would hide it)."""
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_pdf("first page", "second page"))
    result = extract.write_pages(pdf, tmp_path / "pages")
    record = result.output_dir / extract.RECORD_NAME
    original = record.read_bytes()
    assert b"\r\n" not in original and b"\n" in original
    record.write_bytes(original.replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="immutable"):
        extract.write_pages(pdf, tmp_path / "pages")


def test_failed_write_leaves_no_partial_directory_and_retry_succeeds(tmp_path, monkeypatch):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_pdf("one", "two", "three"))
    real_write = extract._write_file

    def flaky(path, data):
        if path.name == "2.txt":
            raise OSError("disk full")
        real_write(path, data)

    monkeypatch.setattr(extract, "_write_file", flaky)
    with pytest.raises(OSError, match="disk full"):
        extract.write_pages(pdf, tmp_path / "pages")
    source_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert not (tmp_path / "pages" / source_hash).exists()
    assert [p.name for p in (tmp_path / "pages").iterdir()] == [], "no staging directory may be left behind"
    monkeypatch.setattr(extract, "_write_file", real_write)
    result = extract.write_pages(pdf, tmp_path / "pages")
    assert result.pages == 3 and sorted(p.name for p in result.output_dir.iterdir()) == [
        "1.txt",
        "2.txt",
        "3.txt",
        extract.RECORD_NAME,
    ]


def test_pypdf_warnings_are_counted_and_still_logged(tmp_path, caplog, monkeypatch):
    """A pypdf warning (e.g. skipped font parsing) is counted per extraction and stays visible to the caller."""
    import logging

    class FakePage:
        def extract_text(self, extraction_mode):
            logging.getLogger("pypdf").warning("synthetic font warning")
            return "ok"

    class FakeReader:
        def __init__(self, stream):
            self.is_encrypted = False
            self.pages = [FakePage(), FakePage()]

    monkeypatch.setattr(extract, "PdfReader", FakeReader)
    with caplog.at_level(logging.WARNING, logger="pypdf"):
        texts, count = extract.extract_pages(b"%PDF-irrelevant")
    assert texts == ["ok", "ok"] and count == 2
    assert sum("synthetic font warning" in r.message for r in caplog.records) == 2
    assert not logging.getLogger("pypdf").handlers, "the counting handler must be removed after extraction"


def test_empty_pages_are_reported_not_hidden(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_pdf("text", ""))
    result = extract.write_pages(pdf, tmp_path / "pages")
    assert result.chars_per_page == (4, 0) and result.empty_pages == (2,)


def test_cli_reports_per_file_and_fails_on_error(tmp_path, capsys):
    good = tmp_path / "good.pdf"
    good.write_bytes(_pdf("ok"))
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    code = extract.main([str(good), str(bad), "--pages", str(tmp_path / "pages")])
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 1
    assert lines[0]["pages"] == 1 and lines[0]["params_hash"] == extract.PARAMS_HASH
    assert lines[0]["extractor_warnings"] == 0
    assert "error" in lines[1]
