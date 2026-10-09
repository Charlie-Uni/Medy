"""Evidence splitting, scoring and rendering (M5-04). The released layout names and the immutable per-version
selection rules live in `focus_profiles`; this module only implements them."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from medops.domain.evidence import Evidence
from medops.harness.focus_profiles import (
    ALLOWED_EVIDENCE_FOCUS,
    EVIDENCE_FOCUS_OFF,
    EVIDENCE_FOCUS_SENTENCE,
    FOCUS_PARAMS,
    FocusParams,
)
from medops.infrastructure.llm.gateway import estimate_tokens
from medops.retrieval.lexical.normalization import normalize_text

KEEP_RATIO = FOCUS_PARAMS[EVIDENCE_FOCUS_SENTENCE].keep_ratio
MIN_CHUNK_TOKENS = 60  # a chunk this short is shown whole: trimming it saves almost nothing
TITLE_MAX_CHARS = 60  # legend titles are cut here: enough to tell sibling documents apart (record 118)
NAMED_SOURCE_RULE = "文档（若问题指明要依据某份具体文件作答，而下列文档中没有它，输出 answers_question=false）："
MIN_UNIT_TOKENS = 5  # shorter fragments ("1.", "e.g.", "See Table 2.") are merged into the following unit
MAX_UNIT_CHARS = 240  # longer runs without a sentence end (flattened tables) are cut at a clause or a space
ELISION = "[…]"

SentenceScorer = Callable[[str, Sequence[str]], list[float]]

_CLOSERS = "\"'”’」』）)]】》"
_CJK_END = re.compile(rf"[。！？；][{re.escape(_CLOSERS)}]*")
# a Latin sentence end needs whitespace after it and something that can start a sentence; "0.05" and "e.g.," never match
_LATIN_END = re.compile(rf"[.!?;][{re.escape(_CLOSERS)}]*(?=\s+[A-Z0-9\"'“‘(\[一-鿿㐀-䶿])")
_ABBREVIATION = re.compile(
    r"(?:\b(?:e\.g|i\.e|etc|vs|cf|al|fig|figs|no|nos|dr|mr|mrs|ms|prof|inc|ltd|co|approx|ref|refs|sec|vol|pp|u\.s)|\b[A-Za-z])\.$",
    re.I,
)
_CLAUSE = re.compile(r"[，,、：:]\s*|\s+")


@dataclass(frozen=True)
class RenderedEvidence:
    """The evidence part of the answer prompt plus what the answer node needs to read citations back."""

    blocks: tuple[str, ...]
    chunk_ids: dict[str, str] = field(default_factory=dict)  # alias (upper case) -> chunk id; empty when off
    legend: str = ""  # one line placed before the blocks (markers v3: each document's version, written once)
    full_tokens: int = 0  # local estimate of the evidence text before focusing
    kept_tokens: int = 0
    units: int = 0
    kept_units: int = 0

    def body(self) -> str:
        """The evidence part of the user message, after the "证据（共 N 段）：" line."""
        return (self.legend + "\n\n" if self.legend else "") + "\n\n".join(self.blocks)

    def resolve(self, cited: str) -> str:
        """A cited id as the model wrote it -> the chunk id; unknown ids are returned unchanged (and then fail the
        answer node's grounding check like any forged chunk id)."""
        if not self.chunk_ids:
            return cited
        key = cited.strip().upper()
        if key.startswith("CHUNK="):
            key = key[len("CHUNK=") :]
        return self.chunk_ids.get(key, cited)


def split_units(text: str) -> list[tuple[int, int]]:
    """Partition `text` into sentence-like units; the spans are contiguous and cover the whole text."""
    cuts: set[int] = set()
    for m in _CJK_END.finditer(text):
        cuts.add(m.end())
    for m in _LATIN_END.finditer(text):
        if text[m.start()] == "." and _ABBREVIATION.search(text[max(0, m.start() - 8) : m.start() + 1]):
            continue
        cuts.add(m.end())
    bounds = [0, *sorted(c for c in cuts if 0 < c < len(text)), len(text)]
    spans = [(a, b) for a, b in zip(bounds, bounds[1:], strict=False) if b > a]
    spans = [piece for span in spans for piece in _cut_long(text, span)]
    merged: list[tuple[int, int]] = []
    carry: int | None = None  # start of short fragments waiting for the next unit
    for a, b in spans:
        start = a if carry is None else carry
        if estimate_tokens(text[start:b].strip()) < MIN_UNIT_TOKENS:
            carry = start
            continue
        merged.append((start, b))
        carry = None
    if carry is not None:  # a short tail joins the previous unit
        if merged:
            merged[-1] = (merged[-1][0], len(text))
        else:
            merged.append((carry, len(text)))
    return merged


def _cut_long(text: str, span: tuple[int, int]) -> list[tuple[int, int]]:
    a, b = span
    out: list[tuple[int, int]] = []
    while b - a > MAX_UNIT_CHARS:
        window = text[a : a + MAX_UNIT_CHARS]
        cut = max((m.end() for m in _CLAUSE.finditer(window) if m.end() >= MAX_UNIT_CHARS // 2), default=MAX_UNIT_CHARS)
        out.append((a, a + cut))
        a += cut
    out.append((a, b))
    return out


def focus_texts(
    query: str,
    texts: Sequence[str],
    scorer: SentenceScorer,
    *,
    params: FocusParams = FOCUS_PARAMS[EVIDENCE_FOCUS_SENTENCE],
    rewritten: Sequence[str] = (),
) -> tuple[list[str], dict[str, int]]:
    """The sentence-focused rendering of each text (same order) and the counters of the selection."""
    units = [split_units(t) for t in texts]
    tokens = [[estimate_tokens(t[a:b]) for a, b in spans] for t, spans in zip(texts, units, strict=True)]
    full = sum(sum(row) for row in tokens)
    keep: list[set[int]] = [set() for _ in texts]
    scored: list[tuple[int, int]] = []  # (text index, unit index) of every unit that has to compete
    for i, row in enumerate(tokens):
        if i < params.whole_top or len(row) <= 1 or sum(row) <= MIN_CHUNK_TOKENS:
            keep[i] = set(range(len(row)))
        else:
            scored.extend((i, j) for j in range(len(row)))
    if scored:
        # the question first, then the richest rewritten queries (the last ones carry the most added terms)
        variants = list(dict.fromkeys([normalize_text(query), *(normalize_text(q) for q in reversed(rewritten))]))
        variants = variants[: params.query_variants]
        unit_texts = [texts[i][units[i][j][0] : units[i][j][1]].strip() for i, j in scored]
        by_unit: dict[tuple[int, int], float] = dict.fromkeys(scored, float("-inf"))
        for variant in variants:
            scores = scorer(variant, unit_texts)
            if len(scores) != len(scored):
                raise ValueError("sentence scorer returned a score count that differs from the input")
            for u, s in zip(scored, scores, strict=True):
                by_unit[u] = max(by_unit[u], float(s))
        for i in {i for i, _ in scored}:  # every chunk keeps its best unit and the neighbours asked for
            n = len(tokens[i])
            best = max((j for k, j in scored if k == i), key=lambda j: (by_unit[(i, j)], -j))
            keep[i].add(best)
            if params.neighbours:
                sides = [j for j in (best - 1, best + 1) if 0 <= j < n]
                if params.one_sided and sides:
                    sides = [max(sides, key=lambda j: (by_unit[(i, j)], -j))]
                for side in sides:
                    step = 1 if side > best else -1
                    keep[i].update(best + step * k for k in range(1, params.neighbours + 1) if 0 <= best + step * k < n)
        kept = sum(tokens[i][j] for i in range(len(texts)) for j in keep[i])
        budget = math.ceil(params.keep_ratio * full)
        for i, j in sorted(scored, key=lambda u: (-by_unit[u], u)):
            if kept >= budget:
                break
            if j not in keep[i]:
                keep[i].add(j)
                kept += tokens[i][j]
    rendered = [_join(t, spans, chosen) for t, spans, chosen in zip(texts, units, keep, strict=True)]
    stats = {
        "full_tokens": full,
        "kept_tokens": sum(tokens[i][j] for i in range(len(texts)) for j in keep[i]),
        "units": sum(len(row) for row in tokens),
        "kept_units": sum(len(k) for k in keep),
    }
    return rendered, stats


def _join(text: str, spans: Sequence[tuple[int, int]], chosen: set[int]) -> str:
    """Kept units in their original order; a run of adjacent units is the original text, a gap is marked."""
    if len(chosen) == len(spans):
        return text
    parts: list[str] = []
    run: tuple[int, int] | None = None
    for j, (a, b) in enumerate(spans):
        if j in chosen:
            run = (run[0], b) if run else (a, b)
            continue
        if run:
            parts.append(text[run[0] : run[1]].strip())
            run = None
        if not parts or parts[-1] != ELISION:
            parts.append(ELISION)
    if run:
        parts.append(text[run[0] : run[1]].strip())
    return " ".join(parts)


def render_evidence(
    query: str,
    evidence: Sequence[Evidence],
    *,
    mode: str = EVIDENCE_FOCUS_OFF,
    scorer: SentenceScorer | None = None,
    rewritten: Sequence[str] = (),
    titles: Mapping[str, str] | None = None,
) -> RenderedEvidence:
    if mode not in ALLOWED_EVIDENCE_FOCUS:
        raise ValueError(f"unknown evidence focus mode {mode!r}")
    texts = [e.text for e in evidence]
    full = sum(estimate_tokens(t) for t in texts)
    if mode == EVIDENCE_FOCUS_OFF:
        blocks = []
        for i, e in enumerate(evidence, 1):
            c = e.citation
            head = f"<<证据 {i} | chunk={c.chunk_id} | doc={c.doc_id} | version={c.version} | page={c.page}{' | historical' if e.historical else ''}>>"
            blocks.append(f"{head}\n{e.text}\n<<证据 {i} 结束>>")
        return RenderedEvidence(blocks=tuple(blocks), full_tokens=full, kept_tokens=full)
    stats = {"full_tokens": full, "kept_tokens": full, "units": 0, "kept_units": 0}
    params = FOCUS_PARAMS.get(mode)
    if params is not None:
        if scorer is None:
            raise ValueError(f"{mode} needs a sentence scorer")
        texts, stats = focus_texts(query, texts, scorer, params=params, rewritten=rewritten)
    markers = params.markers if params is not None else "v1"
    docs: dict[str, str] = {}
    versions: dict[str, str] = {}  # document alias -> version label (a doc id is one version of one document)
    chunk_ids: dict[str, str] = {}
    blocks = []
    for i, (e, text) in enumerate(zip(evidence, texts, strict=True), 1):
        c = e.citation
        alias = f"E{i}"
        chunk_ids[alias] = c.chunk_id
        doc = docs.setdefault(c.doc_id, f"D{len(docs) + 1}")
        versions.setdefault(doc, c.version)
        flag = " | historical" if e.historical else ""
        if markers == "v4":
            blocks.append(f"[{alias} | {doc}{flag}]\n{text}\n[/{alias}]")
        elif markers == "v3":
            blocks.append(f"[{alias} | {doc} | p={c.page}{flag}]\n{text}\n[/{alias}]")
        elif markers == "v2":
            blocks.append(f"[{alias} | {doc} | v={c.version} | p={c.page}{flag}]\n{text}\n[/{alias}]")
        else:
            head = f"<<证据 | chunk={alias} | doc={doc} | version={c.version} | page={c.page}{flag}>>"
            blocks.append(f"{head}\n{text}\n<<证据 {alias} 结束>>")
    legend = ""
    if markers == "v3":
        legend = "文档版本：" + "；".join(f"{d} v={v}" for d, v in versions.items())
    elif markers == "v4":
        missing = [doc_id for doc_id in docs if doc_id not in (titles or {})]
        if missing:
            raise ValueError(f"{mode} needs the title of every evidence document ({len(missing)} missing)")
        assert titles is not None
        assert params is not None
        lines = [
            f"{alias} = {_cut_title(titles[doc_id], params)}（v={versions[alias]}）" for doc_id, alias in docs.items()
        ]
        legend = "\n".join([NAMED_SOURCE_RULE if params.source_rule else "文档：", *lines])
    return RenderedEvidence(blocks=tuple(blocks), chunk_ids=chunk_ids, legend=legend, **stats)


def _cut_title(title: str, params: FocusParams) -> str:
    """v7 cuts at a fixed length; later versions back off to the last space so a designator is not split."""
    limit = params.title_chars
    if len(title) <= limit:
        return title
    if limit <= TITLE_MAX_CHARS:
        return title[:limit]
    head = title[:limit]
    space = head.rfind(" ")
    return (head[:space] if space >= limit - 20 else head).rstrip(" –—-:：,，(（") + "…"


def needs_titles(mode: str) -> bool:
    params = FOCUS_PARAMS.get(mode)
    return params is not None and params.markers == "v4"
