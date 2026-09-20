"""ADR-0009 §1-2 DOCX extraction: top-level sections at headings, heading paths, tables, tracked changes
read as accept-all, style-name headings, outline levels, the no-headings warning and refusals."""

from __future__ import annotations

import pytest

from medops.ingestion import docx
from tests.unit.ingestion.docx_factory import W_NS, make_docx, paragraph, table


def test_sections_follow_top_level_headings_and_keep_nested_paths():
    body = (
        paragraph("Preamble text before any heading.")
        + paragraph("1 Indications", heading=1)
        + paragraph("Adults with hypertension.")
        + paragraph("1.1 Special populations", heading=2)
        + paragraph("Elderly: start low.")
        + paragraph("2 Dosage", heading=1)
        + table([["Population", "Dose"], ["Adults", "500 mg"]])
        + paragraph("Do not exceed 3 g/day.", inserted=" (revised)", deleted=" OLD TEXT")
    )
    sections, warnings = docx.extract_sections(make_docx(body))
    assert warnings == []
    assert [s.ordinal for s in sections] == [1, 2, 3]
    assert sections[0].heading_path == () and sections[0].text == "Preamble text before any heading."
    assert sections[1].heading_path == ("1 Indications",) and sections[1].label == "1 Indications"
    assert "1.1 Special populations" in sections[1].text and "Elderly: start low." in sections[1].text
    assert sections[2].heading_path == ("2 Dosage",)
    assert "Population | Dose" in sections[2].text and "Adults | 500 mg" in sections[2].text
    assert "Do not exceed 3 g/day. (revised)" in sections[2].text and "OLD TEXT" not in sections[2].text


def test_headings_by_style_name_or_outline_level_and_chinese_style_names():
    styles = (
        f'<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{W_NS}">'
        '<w:style w:type="paragraph" w:styleId="Ttulo1"><w:name w:val="heading 1"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="X2"><w:name w:val="標題 2"/></w:style>'
        "</w:styles>"
    )
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Ttulo1"/></w:pPr><w:r><w:t>Alpha</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>a-text</w:t></w:r></w:p>"
        '<w:p><w:pPr><w:pStyle w:val="X2"/></w:pPr><w:r><w:t>Alpha sub</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:r><w:t>Beta</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>b-text</w:t></w:r></w:p>"
    )
    sections, warnings = docx.extract_sections(make_docx(body, styles_xml=styles))
    assert warnings == [] and [s.heading_path for s in sections] == [("Alpha",), ("Beta",)]


def test_no_headings_gives_one_section_and_a_warning():
    sections, warnings = docx.extract_sections(make_docx(paragraph("Just text.") + paragraph("More text.")))
    assert warnings == [docx.NO_HEADINGS]
    assert len(sections) == 1 and sections[0].heading_path == () and sections[0].text == "Just text.\nMore text."


def test_unreadable_or_empty_documents_are_refused():
    with pytest.raises(ValueError, match="no text"):
        docx.extract_sections(make_docx(paragraph("   ")))
    with pytest.raises(ValueError, match="unreadable"):
        docx.extract_sections(b"PK\x03\x04nope")
    assert docx.PARAMS_HASH and docx.PARSER_VERSION == "docx-ooxml-v1"
