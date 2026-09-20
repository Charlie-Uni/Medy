"""ADR-0009 §3 structural malicious-content gate: PDF actions/scripts/embedded files (raw and hex-escaped
names, parsed object graph), DOCX macros/OLE/external relationships/field codes, ZIP-bomb limits, and the
signature sniffer that never trusts a file name."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from medops.ingestion import filecheck
from tests.integration.pdf_factory import make_pdf
from tests.unit.ingestion.docx_factory import field, make_docx, paragraph

CLEAN_PDF = make_pdf(["Adults: 500 mg orally twice daily."])
CLEAN_DOCX = make_docx(paragraph("Dosage", heading=1) + paragraph("500 mg twice daily."))


def test_sniff_uses_signatures_not_names():
    assert filecheck.sniff(CLEAN_PDF) == "pdf" and filecheck.sniff(CLEAN_DOCX) == "docx"
    assert filecheck.sniff(b"plain text") is None and filecheck.sniff(b"PK\x03\x04garbage") is None
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "not a docx")
    assert filecheck.sniff(buf.getvalue()) is None
    with pytest.raises(ValueError):
        filecheck.scan("odt", b"")


def test_clean_files_pass():
    assert filecheck.scan("pdf", CLEAN_PDF).clean and filecheck.scan("docx", CLEAN_DOCX).clean


def _pdf_with_catalog(extra: bytes) -> bytes:
    return CLEAN_PDF.replace(b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Catalog /Pages 2 0 R " + extra + b" >>")


@pytest.mark.parametrize(
    ("extra", "rule"),
    [
        (b"/OpenAction << /S /JavaScript /JS (app.alert(1)) >>", "pdf.open_action"),
        (b"/OpenAction << /S /JavaScript /JS (app.alert(1)) >>", "pdf.javascript"),
        (b"/AA << /O 4 0 R >>", "pdf.additional_actions"),
        (b"/Names << /EmbeddedFiles << /Names [] >> >>", "pdf.embedded_file"),
        (b"/AcroForm << /XFA 4 0 R >>", "pdf.xfa"),
        (b"/OpenAction << /S /Launch /F (cmd.exe) >>", "pdf.launch"),
        (b"/J#61vaScript 4 0 R", "pdf.javascript"),  # hex-escaped name
        (b"/OpenAction << /S /SubmitForm >>", "pdf.form_submit"),
    ],
)
def test_pdf_active_content_is_found_in_raw_bytes_and_object_graph(extra, rule):
    findings = filecheck.scan("pdf", _pdf_with_catalog(extra))
    assert rule in findings.rules


def test_pdf_lookalike_names_and_uri_links_are_allowed():
    ok = _pdf_with_catalog(b"/AAPL:Keywords [] /URI (https://example.invalid) /Lang (en)")
    assert filecheck.scan("pdf", ok).clean


def test_encrypted_or_unparseable_pdf_is_refused():
    enc = CLEAN_PDF.replace(b"/Root 1 0 R", b"/Root 1 0 R /Encrypt 9 0 R")
    assert "pdf.encrypted" in filecheck.scan("pdf", enc).rules
    assert "pdf.unparseable" in filecheck.scan("pdf", b"%PDF-1.4\ngarbage").rules


@pytest.mark.parametrize(
    ("kwargs", "rule"),
    [
        ({"macro": True}, "docx.macro"),
        ({"ole": True}, "docx.ole_object"),
        ({"external_rel": "attachedTemplate"}, "docx.external_relationship"),
        ({"external_rel": "oleObject"}, "docx.external_relationship"),
        ({"extra_files": {"word/activeX/activeX1.xml": b"<x/>"}}, "docx.activex"),
    ],
)
def test_docx_macros_ole_activex_and_external_parts_are_refused(kwargs, rule):
    data = make_docx(paragraph("Title", heading=1) + paragraph("body"), **kwargs)
    assert rule in filecheck.scan("docx", data).rules


def test_docx_external_hyperlinks_are_allowed_but_field_codes_are_not():
    assert filecheck.scan("docx", make_docx(paragraph("t", heading=1) + paragraph("b"), external_rel="hyperlink")).clean
    for instr in ("DDEAUTO c:\\\\cmd.exe", "INCLUDETEXT https://example.invalid/x", 'LINK Excel.Sheet.8 "x"'):
        data = make_docx(paragraph("t", heading=1) + field(instr))
        assert "docx.field_code" in filecheck.scan("docx", data).rules, instr
    assert filecheck.scan("docx", make_docx(paragraph("t", heading=1) + field("PAGE"))).clean


def test_zip_bomb_limits_and_path_traversal():
    bomb = make_docx(
        paragraph("t", heading=1) + paragraph("b"), extra_files={"word/media/big.bin": b"\0" * (5 * 1024 * 1024)}
    )
    assert "zip.compression_ratio" in filecheck.scan("docx", bomb).rules
    traversal = make_docx(paragraph("t", heading=1) + paragraph("b"), extra_files={"../evil.txt": b"x"})
    assert "zip.path_traversal" in filecheck.scan("docx", traversal).rules
    many = make_docx(
        paragraph("t", heading=1) + paragraph("b"),
        extra_files={f"word/media/{i}.txt": b"x" for i in range(filecheck.ZIP_MAX_ENTRIES + 1)},
    )
    assert "zip.too_many_entries" in filecheck.scan("docx", many).rules
    assert filecheck.scan("docx", b"PK\x03\x04broken").rules == ("zip.unreadable",)


def test_xml_entity_attacks_are_reported_not_expanded():
    evil = make_docx(paragraph("t", heading=1) + paragraph("b"))
    xxe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">&e;</Types>'
    buf = BytesIO()
    with zipfile.ZipFile(BytesIO(evil)) as src, zipfile.ZipFile(buf, "w") as dst:
        for item in src.infolist():
            dst.writestr(item.filename, xxe if item.filename == "[Content_Types].xml" else src.read(item.filename))
    rules = filecheck.scan("docx", buf.getvalue()).rules
    assert any(r.startswith("docx.unparseable") for r in rules)
