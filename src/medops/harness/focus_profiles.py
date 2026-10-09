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
- `sentfocus-v6` — the `sentfocus-v2` selection (two-sided neighbours) with delimiters `[E1 | D1 | p=…]` … `[/E1]`
  and one legend line `文档版本：D1 v=…；D2 v=…` — each document's version label once instead of once per block.
- `sentfocus-v7` — `sentfocus-v6` whose legend names each document (`D1 = <title>（v=…）`, one line per document)
  under one rule line: a question that says which document it wants answered from is not answered when that
  document is not listed. Block headers drop the page number. The titles come from the reader's own connection.

What does not change in any mode: `AgentState.evidence` keeps the full chunk text (its hash is checked, baseline
3.3), layer-2 screening has already run on the full text, the claim verifier judges against the full cited chunk,
and citations stay chunk-level. The rules are deterministic for a fixed scorer revision; the mode enters
`model_config_version` through the released-policy suffix, so runs of different modes never share operation keys.
- `sentfocus-v8` — `sentfocus-v7` without the rule line (titles as information, no instruction) and with titles cut
  at a word boundary within 90 characters.
"""

from __future__ import annotations

from dataclasses import dataclass

EVIDENCE_FOCUS_OFF = "off"
EVIDENCE_FOCUS_COMPACT = "compact-v1"
EVIDENCE_FOCUS_SENTENCE = "sentfocus-v1"
EVIDENCE_FOCUS_SENTENCE_V2 = "sentfocus-v2"
EVIDENCE_FOCUS_SENTENCE_V3 = "sentfocus-v3"
EVIDENCE_FOCUS_SENTENCE_V4 = "sentfocus-v4"
EVIDENCE_FOCUS_SENTENCE_V5 = "sentfocus-v5"
EVIDENCE_FOCUS_SENTENCE_V6 = "sentfocus-v6"
EVIDENCE_FOCUS_SENTENCE_V7 = "sentfocus-v7"
EVIDENCE_FOCUS_SENTENCE_V8 = "sentfocus-v8"


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
    # block delimiters: v1 = <<证据 | chunk=E1 …>> … <<证据 E1 结束>>; v2 = [E1 | D1 | v=… | p=…] … [/E1];
    # v3 = [E1 | D1 | p=…] … [/E1] with one legend line giving each document's version once;
    # v4 = [E1 | D1] … [/E1] with a legend of one line per document (title, version)
    markers: str = "v1"
    source_rule: bool = True  # markers v4: put the named-source rule line above the legend (v7); v8 lists titles only
    title_chars: int = 60  # markers v4: legend titles are cut here (v8: 90, at a word boundary)


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
    # v5 met the token gate but its one-sided neighbours cost the negation slice 4.4 pp (record 117); v6 goes back
    # to v2's selection (+4.0 pp, no slice drop) and takes the tokens from the delimiters instead: the version label
    # is written once per document in a legend line (5.0 points offline, nothing removed)
    EVIDENCE_FOCUS_SENTENCE_V6: FocusParams(keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2, markers="v3"),
    # v6 met the token gate with quality intact, but ss-0088 answered in all three pilots (record 118): the model
    # cannot tell which document a block comes from. v7 is v6 with document titles in the legend and one rule line
    # (a question that names its source is answered only from that source); page numbers leave the block headers
    # to pay for the titles
    EVIDENCE_FOCUS_SENTENCE_V7: FocusParams(keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2, markers="v4"),
    # v7's rule line stopped ss-0088 but made the model abstain on five items v2 and v6 answered, and its 60-character
    # cut removed "IX" from "GVP – Module IX" (record 119). v8 gives the information without the instruction: the same
    # legend of titles, no rule line, titles cut at a word boundary within 90 characters
    EVIDENCE_FOCUS_SENTENCE_V8: FocusParams(
        keep_ratio=0.6, neighbours=1, whole_top=1, query_variants=2, markers="v4", source_rule=False, title_chars=90
    ),
}
ALLOWED_EVIDENCE_FOCUS: frozenset[str] = frozenset({EVIDENCE_FOCUS_OFF, EVIDENCE_FOCUS_COMPACT, *FOCUS_PARAMS})
