"""How verified evidence is laid out in the answer prompt (M5-04, record 113; baseline 5.11 "只把通过验证的相关句
放入上下文").

The answer prompt is the largest consumer of tokens, and about a third of it is not evidence text at all: every
block header carries two UUIDs. Three released modes (`retrieval_params/hybrid` key `evidence_focus`):

- `off` — the block layout the system has always used (full chunk text, chunk and document UUIDs in the header).
- `compact-v1` — the same blocks with short aliases (`E1`, `D1`) in place of the UUIDs. Nothing about the evidence
  is removed; the model cites aliases and the answer node maps them back to chunk ids.
- `sentfocus-v1` — `compact-v1`, and each chunk shows only its most relevant sentences: the chunk is split into
  sentence units, the cross-encoder that reranked the chunks scores every unit against the question, each chunk
  keeps its best unit, and the remaining units compete across the whole evidence set until `KEEP_RATIO` of the
  evidence tokens is kept. Omitted stretches are marked `[…]` so two kept sentences are never read as adjacent.
- `sentfocus-v2` — the same selection with three guards that the offline check of v1 motivated (record 113: the
  annotated answer text was hidden in 6% of the cases, mostly English evidence under a Chinese question and
  answers spanning two sentences): a unit's score is its best score over the question and the richest rewritten
  query (glossary terms carry the English vocabulary); every chunk keeps the neighbours of its best unit; the
  first-ranked chunk is shown whole.
- `sentfocus-v3` — `sentfocus-v2` without the whole first chunk (the neighbour rule alone keeps most answer texts;
  the whole chunk cost three points of the token cut).
- `sentfocus-v4` — `sentfocus-v2` keeping only the better-scoring neighbour of the best unit (record 116: v2's
  two-sided rule left three of four sentences and stopped 2.3 points short of the token gate).
- `sentfocus-v5` — `sentfocus-v4` with shorter block delimiters (`[E1 | D1 | v=… | p=…]` … `[/E1]`): the same
  fields, about 2.7 points more of the token cut; aliases and elision marks unchanged.

What does not change in any mode: `AgentState.evidence` keeps the full chunk text (its hash is checked, baseline
3.3), layer-2 screening has already run on the full text, the claim verifier judges against the full cited chunk,
and citations stay chunk-level. The rules are deterministic for a fixed scorer revision; the mode enters
`model_config_version` through the released-policy suffix, so runs of different modes never share operation keys.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from medops.domain.evidence import Evidence
from medops.infrastructure.llm.gateway import estimate_tokens
from medops.retrieval.lexical.normalization import normalize_text

EVIDENCE_FOCUS_OFF = "off"
EVIDENCE_FOCUS_COMPACT = "compact-v1"
EVIDENCE_FOCUS_SENTENCE = "sentfocus-v1"
EVIDENCE_FOCUS_SENTENCE_V2 = "sentfocus-v2"
EVIDENCE_FOCUS_SENTENCE_V3 = "sentfocus-v3"
EVIDENCE_FOCUS_SENTENCE_V4 = "sentfocus-v4"
EVIDENCE_FOCUS_SENTENCE_V5 = "sentfocus-v5"


@dataclass(frozen=True)
class FocusParams:
    """Selection rules of one sentence-focus version; a version never changes once a run has used it."""

    keep_ratio: float  # share of the evidence text tokens (local estimate) kept across the whole evidence set
    neighbours: int = 0  # units kept on each side of a chunk's best unit
    one_sided: bool = (
        False  # keep only the better-scoring side of the best unit (record 116: v2's two sides cost 2.3 pp)
    )
    whole_top: int = 0  # leading chunks (reranker order) shown whole
    query_variants: int = 1  # the question plus this many rewritten queries, scored with max
    markers: str = (
        "v1"  # block delimiters: v1 = <<证据 | chunk=E1 …>> … <<证据 E1 结束>>; v2 = [E1 | D1 | v=… | p=…] … [/E1]
    )


FOCUS_PARAMS: dict[str, FocusParams] = {
    EVIDENCE_FOCUS_SENTENCE: FocusParams(keep_ratio=0.6),
    EVIDENCE_FOCUS_SENTENCE_V2: FocusParams(keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2),
    # v2 without the whole first chunk: its neighbour rule already keeps 98% of the answer texts at ranks 2-8 (record
    # 113), and the whole chunk cost three points of the token cut
    EVIDENCE_FOCUS_SENTENCE_V3: FocusParams(keep_ratio=0.6, neighbours=1, whole_top=0, query_variants=2),
    # v2 measured −22.7% real tokens at +4.0 pp (record 116); the two-sided neighbour rule is where the tokens went,
    # so v4 keeps the best unit and only its better-scoring neighbour
    EVIDENCE_FOCUS_SENTENCE_V4: FocusParams(
        keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2, one_sided=True
    ),
    # v4 measured 24.0% offline with 99.2% of the answer texts kept; the delimiters still cost 43 tokens a block
    # (the version label alone 15), so v5 is v4 with shorter delimiters carrying the same fields
    EVIDENCE_FOCUS_SENTENCE_V5: FocusParams(
        keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2, one_sided=True, markers="v2"
    ),
}
ALLOWED_EVIDENCE_FOCUS: frozenset[str] = frozenset({EVIDENCE_FOCUS_OFF, EVIDENCE_FOCUS_COMPACT, *FOCUS_PARAMS})

KEEP_RATIO = FOCUS_PARAMS[EVIDENCE_FOCUS_SENTENCE].keep_ratio
MIN_CHUNK_TOKENS = 60  # a chunk this short is shown whole: trimming it saves almost nothing
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
    full_tokens: int = 0  # local estimate of the evidence text before focusing
    kept_tokens: int = 0
    units: int = 0
    kept_units: int = 0

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
    docs: dict[str, str] = {}
    chunk_ids: dict[str, str] = {}
    blocks = []
    for i, (e, text) in enumerate(zip(evidence, texts, strict=True), 1):
        c = e.citation
        alias = f"E{i}"
        chunk_ids[alias] = c.chunk_id
        doc = docs.setdefault(c.doc_id, f"D{len(docs) + 1}")
        flag = " | historical" if e.historical else ""
        if params is not None and params.markers == "v2":
            blocks.append(f"[{alias} | {doc} | v={c.version} | p={c.page}{flag}]\n{text}\n[/{alias}]")
        else:
            head = f"<<证据 | chunk={alias} | doc={doc} | version={c.version} | page={c.page}{flag}>>"
            blocks.append(f"{head}\n{text}\n<<证据 {alias} 结束>>")
    return RenderedEvidence(blocks=tuple(blocks), chunk_ids=chunk_ids, **stats)
