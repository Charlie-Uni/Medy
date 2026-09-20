"""Deterministic, page-anchored chunking of extracted page texts (M1-10; baseline 5.1, SPEC section 6).

`chunker-v2` works on the norm-v1 normalised text of each page, which is the coordinate system the
probe validator and the hit rule use: every chunk is exactly `normalized_page[char_start:char_end]`,
so a gold `key_text` position found in the normalised page can be tested against chunk spans without
any re-normalisation. Chunks never cross pages (one span per chunk), boundaries fall on sentence ends,
a chunk closes once it reaches TARGET_CHARS and never exceeds MAX_CHARS except when an unbreakable run
has nothing to split at, and a short tail is merged into the previous chunk when that still fits. The
section label is a best-effort heading heuristic carried forward across pages; citations rely on
page and chunk_id, not on the label. Any change to these rules is a new CHUNKER_VERSION.

v2 changes (record 34, 2026-09-20), decided before the second DEC-001 run: a semicolon is a clause mark,
not a sentence end (v1 cut `...in the DSUR; however, it should not...` between the two halves of one
clause), and an over-long run is split at the last clause mark (`, ; : ， ； ： 、`) in the final
LONG_RUN_LOOKBACK characters of the window before falling back to whitespace and then to a hard cut.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

CHUNKER_VERSION = "chunker-v2"
TARGET_CHARS = 400
MAX_CHARS = 600
MIN_TAIL_CHARS = 120
LONG_RUN_LOOKBACK = 200

_SENTENCE_END = re.compile(r"(?<=[。！？])|(?<=[.!?])(?=\s)")
_CLAUSE_MARK = re.compile(r"[,;:，；：、]\s*")
_ZH_SECTIONS = (
    "適應症",
    "适应症",
    "用法用量",
    "用法及用量",
    "用法與用量",
    "用法与用量",
    "禁忌",
    "警語",
    "警语",
    "注意事項",
    "注意事项",
    "不良反應",
    "不良反应",
    "副作用",
    "藥物交互作用",
    "药物相互作用",
    "交互作用",
    "過量",
    "过量",
    "藥理作用",
    "药理作用",
    "藥物動力學",
    "药代动力学",
    "懷孕",
    "孕婦",
    "妊娠",
    "授乳",
    "哺乳",
    "儲存",
    "贮藏",
    "包裝",
    "包装",
    "性狀",
    "性状",
    "成分",
    "組成",
)
_ZH_NAMES = "|".join(map(re.escape, sorted(_ZH_SECTIONS, key=len, reverse=True)))
_LINE_HEADINGS = (
    re.compile(r"^【(?P<label>[^】]{1,40})】"),
    re.compile(r"^(?P<label>" + _ZH_NAMES + r")\s*(?:[:：]|$)"),
    re.compile(r"^(?P<label>\d{1,2}(?:\.\d{1,2}){0,3}\.?\s+\S.{1,80})$"),
    re.compile(r"^(?P<label>[IVX]{1,5}\.[A-Z]\.(?:\d{1,2}\.)*\s+\S.{1,80})$"),
)


@dataclass(frozen=True)
class Span:
    page: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class Chunk:
    seq: int
    page: int
    section: str | None
    content: str
    spans: tuple[Span, ...]
    content_hash: str


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _segments(text: str) -> list[tuple[int, int]]:
    """Sentence segments covering `text` completely; runs longer than MAX_CHARS are split by `_long_run_cut`."""
    cuts = [0, *[m.start() for m in _SENTENCE_END.finditer(text) if 0 < m.start() < len(text)], len(text)]
    raw = [(s, e) for s, e in zip(cuts, cuts[1:], strict=False) if e > s]
    out: list[tuple[int, int]] = []
    for s, e in raw:
        while s < e and text[s].isspace():
            s += 1
        if s >= e:
            continue
        while e - s > MAX_CHARS:
            cut = s + _long_run_cut(text[s : s + MAX_CHARS])
            out.append((s, cut))
            s = cut
        out.append((s, e))
    return out


def _long_run_cut(window: str) -> int:
    """Offset inside a MAX_CHARS window at which an over-long run is split: after the last clause mark
    in the final LONG_RUN_LOOKBACK characters, else at the last whitespace in the final 100, else MAX_CHARS."""
    marks = [m.end() for m in _CLAUSE_MARK.finditer(window) if m.start() >= MAX_CHARS - LONG_RUN_LOOKBACK]
    if marks:
        return marks[-1]
    cut = window.rfind(" ", MAX_CHARS - 100)
    return cut if cut > 0 else MAX_CHARS


def _pack(text: str) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    for s, e in _segments(text):
        if cur is None:
            cur = (s, e)
        elif e - cur[0] <= MAX_CHARS:
            cur = (cur[0], e)
        else:
            chunks.append(cur)
            cur = (s, e)
        if cur is not None and cur[1] - cur[0] >= TARGET_CHARS:
            chunks.append(cur)
            cur = None
    if cur is not None:
        chunks.append(cur)
    if (
        len(chunks) >= 2
        and chunks[-1][1] - chunks[-1][0] < MIN_TAIL_CHARS
        and chunks[-1][1] - chunks[-2][0] <= MAX_CHARS
    ):
        last = chunks.pop()
        chunks[-1] = (chunks[-1][0], last[1])
    trimmed: list[tuple[int, int]] = []
    for s, e in chunks:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            trimmed.append((s, e))
    return trimmed


def _headings(raw: str, text: str) -> list[tuple[int, str]]:
    """Headings are recognised on raw lines (a short line of its own, or a Chinese section name at line
    start) and located in the normalised page text by the whole line, so the recorded position is where
    the heading line begins. Labels and positions come back in page order."""
    found: list[tuple[int, str]] = []
    cursor = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 120:
            continue
        for pattern in _LINE_HEADINGS:
            m = pattern.match(stripped)
            if m:
                label = normalize_text(m.group("label"))
                line_norm = normalize_text(stripped)
                pos = text.find(line_norm, cursor)
                if pos < 0:
                    pos = text.find(label, cursor)
                if label and pos >= 0:
                    found.append((pos, label))
                    cursor = pos + len(label)
                break
    return found


def chunk_pages(raw_pages: Sequence[str]) -> list[Chunk]:
    """Chunk a document given its raw page texts in page order (page numbers are 1-based positions)."""
    chunks: list[Chunk] = []
    section: str | None = None
    for page_no, raw in enumerate(raw_pages, start=1):
        text = normalize_text(raw)
        if not text:
            continue
        headings = _headings(raw, text)
        for start, end in _pack(text):
            for pos, label in headings:
                if pos <= start:
                    section = label
                else:
                    break
            content = text[start:end]
            chunks.append(
                Chunk(
                    seq=len(chunks),
                    page=page_no,
                    section=section,
                    content=content,
                    spans=(Span(page_no, start, end),),
                    content_hash=content_hash(content),
                )
            )
        if headings:
            section = headings[-1][1]
    return chunks


def chunker_record() -> dict[str, str]:
    """Versions to store with a chunking run (index metadata, chunk_mapping files)."""
    return {"chunker_version": CHUNKER_VERSION, "normalization": NORMALIZATION_VERSION}
