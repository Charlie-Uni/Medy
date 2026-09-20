"""DOCX (OOXML WordprocessingML) text extraction into heading-anchored sections (ADR-0009 §1-2).

Standard-library `zipfile` plus `defusedxml`; no python-docx. Text units are paragraphs (`w:p`, including
those inside table cells, joined row-wise with " | "); tracked changes are read as "accept all" (`w:ins`
kept, `w:del` dropped); comments, headers/footers and footnotes are ignored. A heading is a paragraph whose
style id or name is `Heading N` / `heading N` / `標題 N` / `标题 N`, or that carries an outline level. The
document is cut into top-level sections at headings of the smallest level present; text before the first
heading is section 1 with an empty heading path. A document without any heading has no reliable sections
and is reported so the pipeline marks it `low_trust` (INV-DATA-05).
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from defusedxml import ElementTree as SafeET

from medops.core.canonical import canonical_json

PARSER = "docx-ooxml"
PARSER_VERSION = "docx-ooxml-v1"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PARAMS: dict[str, str] = {
    "parser": PARSER_VERSION,
    "tracked_changes": "accept_all",
    "tables": "cells_joined_with_pipe_per_row",
    "sections": "top_level_heading",
}
PARAMS_HASH = hashlib.sha256(canonical_json(PARAMS).encode("utf-8")).hexdigest()
MAX_HEADING_DEPTH = 3
NO_HEADINGS = "no_headings"

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_STYLE = re.compile(r"^(?:heading|標題|标题)\s*(\d)$", re.IGNORECASE)


@dataclass(frozen=True)
class Section:
    ordinal: int  # 1-based; stored as `page` for DOCX documents
    heading_path: tuple[str, ...]
    text: str  # raw paragraphs joined by newlines; norm-v1 is applied by the chunker

    @property
    def label(self) -> str | None:
        return " > ".join(self.heading_path) if self.heading_path else None


@dataclass(frozen=True)
class _Paragraph:
    text: str
    level: int | None  # heading level or None


def _style_names(zf: zipfile.ZipFile) -> dict[str, str]:
    """styleId -> style name (lower-cased) from word/styles.xml, when present."""
    if "word/styles.xml" not in zf.namelist():
        return {}
    root = SafeET.fromstring(zf.read("word/styles.xml"))
    names: dict[str, str] = {}
    for style in root.iter(f"{_W}style"):
        sid = style.get(f"{_W}styleId")
        name_el = style.find(f"{_W}name")
        if sid and name_el is not None and name_el.get(f"{_W}val"):
            names[sid] = str(name_el.get(f"{_W}val")).lower()
    return names


def _runs_text(p: Any) -> str:
    parts: list[str] = []

    def visit(node: Any) -> None:
        tag = node.tag
        if tag == f"{_W}del":  # rejected in "accept all": deleted text disappears
            return
        if tag == f"{_W}t":
            parts.append(node.text or "")
        elif tag == f"{_W}tab":
            parts.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
        for child in node:
            visit(child)

    visit(p)
    return "".join(parts)


def _heading_level(p: Any, style_names: dict[str, str]) -> int | None:
    ppr = p.find(f"{_W}pPr")
    if ppr is None:
        return None
    style = ppr.find(f"{_W}pStyle")
    if style is not None:
        sid = str(style.get(f"{_W}val") or "")
        for candidate in (sid, style_names.get(sid, "")):
            m = _HEADING_STYLE.match(candidate.replace("_", " ").strip()) or re.match(
                r"^(?:heading|標題|标题)(\d)$", candidate, re.IGNORECASE
            )
            if m:
                return int(m.group(1))
    outline = ppr.find(f"{_W}outlineLvl")
    if outline is not None and (outline.get(f"{_W}val") or "").isdigit():
        return int(str(outline.get(f"{_W}val"))) + 1
    return None


def _paragraphs(body: Any, style_names: dict[str, str]) -> list[_Paragraph]:
    out: list[_Paragraph] = []
    for child in body:
        if child.tag == f"{_W}p":
            out.append(_Paragraph(_runs_text(child), _heading_level(child, style_names)))
        elif child.tag == f"{_W}tbl":
            for row in child.iter(f"{_W}tr"):
                cells = []
                for cell in row.findall(f"{_W}tc"):
                    cells.append(" ".join(_runs_text(p) for p in cell.iter(f"{_W}p")).strip())
                out.append(_Paragraph(" | ".join(cells), None))
        elif child.tag == f"{_W}sdt":  # content controls wrap ordinary paragraphs
            content = child.find(f"{_W}sdtContent")
            if content is not None:
                out.extend(_paragraphs(content, style_names))
    return out


def extract_sections(data: bytes) -> tuple[list[Section], list[str]]:
    """Sections in document order plus warnings (`no_headings`). Raises ValueError for an unreadable package
    or a document without any text."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            style_names = _style_names(zf)
            root = SafeET.fromstring(zf.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, SafeET.ParseError) as exc:
        raise ValueError(f"unreadable DOCX package: {type(exc).__name__}") from None
    body = root.find(f"{_W}body")
    if body is None:
        raise ValueError("DOCX has no body")
    paragraphs = _paragraphs(body, style_names)
    if not any(p.text.strip() for p in paragraphs):
        raise ValueError("DOCX contains no text")
    levels = [p.level for p in paragraphs if p.level is not None and p.text.strip()]
    warnings: list[str] = []
    if not levels:
        warnings.append(NO_HEADINGS)
        text = "\n".join(p.text for p in paragraphs).strip()
        return [Section(1, (), text)], warnings
    top = min(levels)
    sections: list[Section] = []
    path: list[str] = []
    buffer: list[str] = []
    current_path: tuple[str, ...] = ()

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append(Section(len(sections) + 1, current_path, text))
        buffer.clear()

    for p in paragraphs:
        if p.level is not None and p.text.strip():
            depth = p.level - top  # 0 = top level
            if depth == 0:
                flush()
                path = [p.text.strip()]
                current_path = tuple(path)
            elif depth < MAX_HEADING_DEPTH:
                path = path[:depth] + [p.text.strip()]
                if not sections and not buffer:
                    current_path = tuple(path)
            buffer.append(p.text)
        else:
            buffer.append(p.text)
    flush()
    return sections, warnings
