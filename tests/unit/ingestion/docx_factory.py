"""Minimal OOXML (DOCX) package builder for tests: paragraphs with optional heading styles, tables, tracked
changes, plus knobs that inject the features the malicious-content gate must catch. No third-party document."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def paragraph(text: str, *, heading: int | None = None, inserted: str = "", deleted: str = "") -> str:
    ppr = f'<w:pPr><w:pStyle w:val="Heading{heading}"/></w:pPr>' if heading else ""
    body = f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    if inserted:
        body += f'<w:ins w:id="1" w:author="a" w:date="2026-01-01T00:00:00Z"><w:r><w:t xml:space="preserve">{escape(inserted)}</w:t></w:r></w:ins>'
    if deleted:
        body += f'<w:del w:id="2" w:author="a" w:date="2026-01-01T00:00:00Z"><w:r><w:delText xml:space="preserve">{escape(deleted)}</w:delText></w:r></w:del>'
    return f"<w:p>{ppr}{body}</w:p>"


def table(rows: list[list[str]]) -> str:
    cells = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(c)}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{cells}</w:tbl>"


def field(instr: str) -> str:
    return f'<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> {escape(instr)} </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'


def make_docx(
    body_xml: str,
    *,
    macro: bool = False,
    ole: bool = False,
    external_rel: str | None = None,  # relationship type suffix, e.g. "attachedTemplate" or "hyperlink"
    extra_files: dict[str, bytes] | None = None,
    styles_xml: str | None = None,
) -> bytes:
    content_types = [
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
    ]
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    files: dict[str, bytes] = {}
    if macro:
        content_types.append('<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>')
        rels.append(
            '<Relationship Id="rId9" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>'
        )
        files["word/vbaProject.bin"] = b"\xd0\xcf\x11\xe0 fake vba"
    if ole:
        content_types.append(
            '<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>'
        )
        rels.append(
            '<Relationship Id="rId8" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/oleObject1.bin"/>'
        )
        files["word/embeddings/oleObject1.bin"] = b"\xd0\xcf\x11\xe0 fake ole"
    if external_rel:
        rels.append(
            f'<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{external_rel}" '
            f'Target="https://example.invalid/x" TargetMode="External"/>'
        )
    files["[Content_Types].xml"] = (
        f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="{CT_NS}">' + "".join(content_types) + "</Types>"
    ).encode()
    files["_rels/.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    ).encode()
    files["word/_rels/document.xml.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{REL_NS}">' + "".join(rels) + "</Relationships>"
    ).encode()
    files["word/document.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W_NS}"><w:body>{body_xml}<w:sectPr/></w:body></w:document>'
    ).encode()
    files["word/styles.xml"] = (
        styles_xml or f'<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{W_NS}"></w:styles>'
    ).encode()
    files.update(extra_files or {})
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
