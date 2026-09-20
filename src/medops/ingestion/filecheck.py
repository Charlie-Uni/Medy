"""Structural malicious-content gate for ingested files (ADR-0009 §3; baseline 5.1 "恶意文件").

The gate is deterministic and in-process: it looks for the document features that carry active content or
pull in external resources, and refuses the file before anything is parsed for text. It is not an antivirus
(that is the optional clamd hook in `medops.ingestion.av`); the two are complementary.

PDF: names are read both from the raw bytes (with `#xx` escapes decoded, so `/J#61vaScript` is still
`/JavaScript`) and from the parsed object graph (catalog, names tree, pages, annotations, AcroForm), so a
name hidden in an object stream is still found by the walk. DOCX: ZIP-bomb limits, then the OOXML package
(content types, parts, relationships, field codes).
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from defusedxml import ElementTree as SafeET
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
DOCX_MAIN_PART = "word/document.xml"

PDF_FORBIDDEN_NAMES: dict[str, str] = {
    "/JavaScript": "pdf.javascript",
    "/JS": "pdf.javascript",
    "/AA": "pdf.additional_actions",
    "/Launch": "pdf.launch",
    "/EmbeddedFile": "pdf.embedded_file",
    "/EmbeddedFiles": "pdf.embedded_file",
    "/RichMedia": "pdf.rich_media",
    "/XFA": "pdf.xfa",
    "/SubmitForm": "pdf.form_submit",
    "/ImportData": "pdf.form_import",
    "/Encrypt": "pdf.encrypted",
}
PDF_MAX_OBJECTS_WALKED = (
    500_000  # a 300-page guideline has ~10^4–10^5 objects; the budget only stops pathological graphs
)

ZIP_MAX_ENTRIES = 2_000
ZIP_MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024
ZIP_MAX_RATIO = 100

_PDF_NAME = re.compile(rb"/([^\s/<>\[\]()%]+)")
_HEX_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
_DOCX_FIELD = re.compile(r"\b(DDEAUTO|DDE|INCLUDETEXT|INCLUDEPICTURE|IMPORT|LINK)\b", re.IGNORECASE)
_OLE_PART = re.compile(r"^word/embeddings/(oleObject\d*|.*\.bin)$", re.IGNORECASE)
_ACTIVEX_PART = re.compile(r"^word/activeX/", re.IGNORECASE)
_ALLOWED_EXTERNAL_REL = ("/hyperlink",)
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"


@dataclass(frozen=True)
class Findings:
    kind: str  # "pdf" | "docx"
    rules: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not self.rules


def sniff(data: bytes) -> str | None:
    """`pdf`, `docx` or None; DOCX means a ZIP whose package declares the WordprocessingML main part."""
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if data.startswith(ZIP_MAGIC):
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names and DOCX_MAIN_PART in names:
            return "docx"
    return None


def scan(kind: str, data: bytes) -> Findings:
    if kind == "pdf":
        return Findings("pdf", tuple(sorted(scan_pdf(data))))
    if kind == "docx":
        return Findings("docx", tuple(sorted(scan_docx(data))))
    raise ValueError(f"unsupported file kind {kind!r}")


# ------------------------------------------------------------------------------------ PDF


def _decode_name(raw: bytes) -> str:
    return "/" + _HEX_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), raw).decode("latin-1")


def _pdf_raw_names(data: bytes) -> set[str]:
    hits = set()
    for m in _PDF_NAME.finditer(data):
        name = _decode_name(m.group(1))
        rule = PDF_FORBIDDEN_NAMES.get(name)
        if rule:
            hits.add(rule)
    return hits


BENIGN_OPEN_ACTION_TYPES = {
    "/GoTo"
}  # open the document at a destination; anything else (JavaScript, Launch, URI, GoToR, SubmitForm…) is refused


def _benign_open_action(value: Any) -> bool:
    """ADR-0009 §3 refinement (record 49): `/OpenAction` is common in ordinary PDFs as a plain destination
    (`[page /Fit]`) or a `/GoTo` action; only action types other than GoTo are active content."""
    try:
        if isinstance(value, IndirectObject):
            value = value.get_object()
        if isinstance(value, ArrayObject):
            return True
        if isinstance(value, DictionaryObject):
            return (
                str(value.get("/S", "")) in BENIGN_OPEN_ACTION_TYPES
                and "/JS" not in value
                and "/JavaScript" not in value
            )
    except PyPdfError:
        return False
    return False


def _walk(obj: Any, seen: set[int], hits: set[str], budget: list[int]) -> None:
    if budget[0] <= 0:
        return
    if isinstance(obj, IndirectObject):
        key = (obj.idnum, obj.generation)
        if key in seen:
            return
        seen.add(key)  # type: ignore[arg-type]
        try:
            obj = obj.get_object()
        except PyPdfError:
            return
    budget[0] -= 1
    if isinstance(obj, DictionaryObject):
        for k, v in obj.items():
            if str(k) == "/OpenAction":
                if not _benign_open_action(v):
                    hits.add("pdf.open_action")
            rule = PDF_FORBIDDEN_NAMES.get(str(k))
            if rule:
                hits.add(rule)
            if isinstance(v, NameObject):
                rule = PDF_FORBIDDEN_NAMES.get(str(v))
                if rule and str(k) in ("/S", "/Type", "/Subtype", "/FT"):
                    hits.add(rule)
            _walk(v, seen, hits, budget)
    elif isinstance(obj, ArrayObject):
        for item in obj:
            _walk(item, seen, hits, budget)


def scan_pdf(data: bytes) -> set[str]:
    hits = _pdf_raw_names(data)
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            hits.add("pdf.encrypted")
        seen: set[int] = set()
        budget = [PDF_MAX_OBJECTS_WALKED]
        _walk(reader.trailer, seen, hits, budget)
        if budget[0] <= 0:
            hits.add("pdf.object_graph_too_large")
    except (PyPdfError, ValueError, RecursionError, KeyError, TypeError, AttributeError, IndexError):
        hits.add("pdf.unparseable")  # a file the parser cannot read is not ingested (fail closed)
    return hits


# ------------------------------------------------------------------------------------ DOCX


def zip_limits(zf: zipfile.ZipFile) -> set[str]:
    hits = set()
    infos = zf.infolist()
    if len(infos) > ZIP_MAX_ENTRIES:
        hits.add("zip.too_many_entries")
    total = 0
    for info in infos:
        total += info.file_size
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/") or re.match(r"^[A-Za-z]:", name):
            hits.add("zip.path_traversal")
        if info.flag_bits & 0x1:
            hits.add("zip.encrypted_entry")
        if info.compress_size > 0 and info.file_size / info.compress_size > ZIP_MAX_RATIO:
            hits.add("zip.compression_ratio")
        if info.compress_size == 0 and info.file_size > 0:
            hits.add("zip.compression_ratio")
    if total > ZIP_MAX_TOTAL_UNCOMPRESSED:
        hits.add("zip.total_size")
    return hits


def _xml(zf: zipfile.ZipFile, name: str) -> Any:
    return SafeET.fromstring(zf.read(name))


def scan_docx(data: bytes) -> set[str]:
    hits: set[str] = set()
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        return {"zip.unreadable"}
    with zf:
        hits |= zip_limits(zf)
        if hits & {
            "zip.too_many_entries",
            "zip.total_size",
            "zip.compression_ratio",
            "zip.path_traversal",
            "zip.encrypted_entry",
        }:
            return hits  # do not read the parts of a suspicious archive
        names = zf.namelist()
        for name in names:
            low = name.lower()
            if low == "word/vbaproject.bin" or low.endswith("vbaproject.bin") or low.endswith("vbadata.xml"):
                hits.add("docx.macro")
            if _OLE_PART.match(name):
                hits.add("docx.ole_object")
            if _ACTIVEX_PART.match(name):
                hits.add("docx.activex")
        try:
            types = _xml(zf, "[Content_Types].xml")
            for el in types.iter():
                ct = (el.get("ContentType") or "").lower()
                if "macroenabled" in ct or "vbaproject" in ct:
                    hits.add("docx.macro")
                if "oleobject" in ct:
                    hits.add("docx.ole_object")
            for name in names:
                if name.endswith(".rels"):
                    for rel in _xml(zf, name).iter(f"{_REL_NS}Relationship"):
                        if (rel.get("TargetMode") or "").lower() == "external":
                            rtype = rel.get("Type") or ""
                            if not rtype.endswith(_ALLOWED_EXTERNAL_REL):
                                hits.add("docx.external_relationship")
                        rtype = rel.get("Type") or ""
                        if rtype.endswith("/attachedTemplate") or rtype.endswith("/aFChunk"):
                            hits.add(
                                "docx.external_relationship"
                                if rtype.endswith("/attachedTemplate")
                                else "docx.alt_chunk"
                            )
            if DOCX_MAIN_PART in names:
                doc = _xml(zf, DOCX_MAIN_PART)
                for instr in doc.iter(f"{_W}instrText"):
                    if instr.text and _DOCX_FIELD.search(instr.text):
                        hits.add("docx.field_code")
                for fld in doc.iter(f"{_W}fldSimple"):
                    if _DOCX_FIELD.search(fld.get(f"{_W}instr") or ""):
                        hits.add("docx.field_code")
                for _ in doc.iter(f"{_W}altChunk"):
                    hits.add("docx.alt_chunk")
                    break
                for _ in doc.iter(f"{_W}object"):
                    hits.add("docx.ole_object")
                    break
        except (SafeET.ParseError, KeyError, ValueError) as exc:  # defusedxml raises on entity attacks too
            hits.add(f"docx.unparseable:{type(exc).__name__}")
    return hits


def describe(rules: Iterable[str]) -> str:
    return ", ".join(sorted(rules))
