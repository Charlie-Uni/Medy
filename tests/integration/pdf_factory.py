"""Tiny synthetic PDF builder for ingestion tests: one Helvetica text line per page, ASCII only.

pypdf reads the text back verbatim, which is all the ingestion pipeline needs. No third-party document
is used in tests (INV-DATA-01).
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    next_id = 4
    kids: list[int] = []
    for text in pages:
        text.encode("ascii")  # the factory is ASCII-only by design
        content = f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET".encode("ascii")
        stream = b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
        content_id, page_id = next_id, next_id + 1
        next_id += 2
        objects[content_id] = stream
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")
        kids.append(page_id)
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(pages)} >>".encode("ascii")

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for oid in sorted(objects):
        offsets[oid] = len(out)
        out += f"{oid} 0 obj\n".encode("ascii") + objects[oid] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode("ascii") + b"0000000000 65535 f \n"
    for oid in range(1, size):
        out += f"{offsets[oid]:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)
