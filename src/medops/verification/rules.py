"""Deterministic support rules (M2-08, baseline 5.4 item 5): numbers, units, frequencies, time windows,
identifiers and negation polarity are decided here before any model is consulted.

Per extracted claim element:
- exact canonical match in the cited evidence with the same negation polarity  -> supported (that chunk);
- exact canonical match but opposite polarity (claim says 不得, evidence does not) -> contradicted; a bound
  phrase (不得超過 / 上限 / at most / within) is a limit, not a negation: `上限 300 mg` and `不得超過 300 mg` share
  polarity, `超過 300 mg` against `不得超過 300 mg` is opposite, and a plain value against a bound is left
  undetermined for the judge (support-rules-v2);
- no match, and the cited evidence states exactly one different value of the same family -> contradicted;
- identifier absent from the cited evidence -> not_supported (an attribution the evidence does not make);
- otherwise -> undetermined (`verdict=None`): containment or the LLM judge decides in the verifier.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from medops.domain.evidence import Evidence
from medops.domain.verification import ElementKind, Verdict
from medops.verification.elements import ExtractedElement, extract, normalize_for_match

RULES_VERSION = "support-rules-v2"

_NEGATION = re.compile(
    r"不得|不可|不應|不应|不宜|禁止|禁用|勿|不建議|不建议|無需|无需|不需要|不需|不要|不能|不推薦|不推荐|避免|除外|不適用|不适用|未|沒有|没有|無|无"
    r"|\bnot\b|\bno\b|\bnever\b|\bwithout\b|\bavoid\b|contraindicated|\bmust not\b|\bshould not\b|\bdo(?:es)? not\b"
    r"|\bcannot\b|n't\b|\bunless\b|\bexcept\b|\bnor\b",
    re.I,
)
_SENTENCE_BREAK = re.compile(r"[。！？!?；;\n]|(?<=[a-z0-9\)])\.\s")

# Bound phrases state a limit, not a negation (support-rules-v2): they are removed before negation cues are
# counted and compared as a direction of their own, so paraphrases like 上限/不得超過/at most agree.
_BOUND_UPPER = re.compile(
    r"不得超過|不得超过|不可超過|不可超过|不應超過|不应超过|不宜超過|不宜超过|不超過|不超过|不得多於|不得多于|不得高於|不得高于"
    r"|不得晚於|不得晚于|不遲於|不迟于|不晚於|不晚于|最多|至多|上限|最高|最遲|最迟|最晚"
    r"|(?:可|可以)?(?:用|使用|增加|增量|加|調整|调整)至|(?:天|日|小時|小时|週|周|月|年|工作日)(?:以|之)?[內内]"
    r"|\bno more than\b|\bnot more than\b|\b(?:must |should |shall |may |can )?not exceed(?:ing)?\b|\bat most\b"
    r"|\bup to\b|\bmaximum\b|\bno later than\b|\bnot later than\b|\bwithin\b|\bat the latest\b",
    re.I,
)
_BOUND_LOWER = re.compile(
    r"不得少於|不得少于|不少於|不少于|不低於|不低于|不得低於|不得低于|不得早於|不得早于|不早於|不早于|至少|最少|下限|最低|最早"
    r"|\bat least\b|\bnot less than\b|\bno less than\b|\bminimum\b|\bno earlier than\b|\bnot earlier than\b|\bnot before\b",
    re.I,
)
_EXCEED_UP = re.compile(
    r"超過|超过|超出|多於|多于|大於|大于|高於|高于|晚於|晚于|遲於|迟于|\bexceed(?:s|ing)?\b|\bmore than\b|\bgreater than\b|\blater than\b",
    re.I,
)
_EXCEED_DOWN = re.compile(
    r"少於|少于|低於|低于|小於|小于|早於|早于|\bless than\b|\bfewer than\b|\bbelow\b|\bearlier than\b", re.I
)

Polarity = Literal["same", "opposite", "unclear"]


@dataclass(frozen=True)
class PolaritySignature:
    negations: int  # negation cues outside bound phrases
    bound: str | None  # "upper" | "lower" | "both"
    exceed: str | None  # "up" | "down" | "both": the act of crossing a limit


def _direction(first: bool, second: bool, a: str, b: str) -> str | None:
    if first and second:
        return "both"
    return a if first else (b if second else None)


def polarity(text: str) -> PolaritySignature:
    upper, lower = bool(_BOUND_UPPER.search(text)), bool(_BOUND_LOWER.search(text))
    stripped = _BOUND_LOWER.sub(" ", _BOUND_UPPER.sub(" ", text))
    up, down = bool(_EXCEED_UP.search(stripped)), bool(_EXCEED_DOWN.search(stripped))
    return PolaritySignature(
        len(_NEGATION.findall(stripped)), _direction(upper, lower, "upper", "lower"), _direction(up, down, "up", "down")
    )


def compare_polarity(claim_text: str, evidence_text: str, *, count: bool = False) -> Polarity:
    """same: identical negation and limit semantics; opposite: a negation flip, a limit against crossing it in the
    same direction, or an upper against a lower bound; unclear: a bound on one side and a plain value on the other
    (the rules do not decide, the judge or fail-closed default does)."""
    a, b = polarity(claim_text), polarity(evidence_text)
    if (a.negations != b.negations) if count else (bool(a.negations) != bool(b.negations)):
        return "opposite"
    if a.bound == b.bound and a.exceed == b.exceed:
        return "same"
    bounds, exceeds = {a.bound, b.bound}, {a.exceed, b.exceed}
    if bounds & {"upper", "both"} and exceeds & {"up", "both"}:
        return "opposite"
    if bounds & {"lower", "both"} and exceeds & {"down", "both"}:
        return "opposite"
    if a.bound and b.bound and a.bound != b.bound:
        return "opposite"
    return "unclear"


_NUMERIC_KINDS = (ElementKind.dose, ElementKind.frequency, ElementKind.time_window)


@dataclass(frozen=True)
class RuleOutcome:
    element: ExtractedElement
    verdict: Verdict | None
    evidence_chunk_id: str | None
    reason: str


def sentence_around(text: str, start: int, end: int) -> str:
    left = 0
    for m in _SENTENCE_BREAK.finditer(text, 0, start):
        left = m.end()
    right = len(text)
    m2 = _SENTENCE_BREAK.search(text, end)
    if m2:
        right = m2.start()
    return text[left:right]


def negated(sentence: str) -> bool:
    return _NEGATION.search(sentence) is not None


def negation_count(text: str) -> int:
    return len(_NEGATION.findall(text))


def sentences(text: str) -> list[str]:
    """Sentence-ish units used for polarity comparison (same breaks as `sentence_around`)."""
    out, last = [], 0
    for m in _SENTENCE_BREAK.finditer(text):
        out.append(text[last : m.start()])
        last = m.end()
    out.append(text[last:])
    return [s for s in out if s.strip()]


def _family(canonical: str) -> str:
    kind, _, rest = canonical.partition(":")
    if kind == "dose":
        return "dose:" + rest.rsplit(":", 1)[-1]
    if kind == "freq":
        return "freq:" + ("week" if rest.endswith("/week") else "day" if rest.endswith("/day") else "once")
    if kind == "time":
        return "time:" + rest.rsplit(":", 1)[-1]
    return kind


def judge_element(
    element: ExtractedElement,
    claim_text: str,
    cited: Sequence[Evidence],
    evidence_elements: Mapping[str, Sequence[ExtractedElement]],
    *,
    single_value_contradiction: bool = True,
) -> RuleOutcome:
    claim_sentence = sentence_around(claim_text, element.start, element.end)
    same_polarity: str | None = None
    opposite: str | None = None
    unclear: str | None = None
    for ev in cited:
        for el in evidence_elements.get(ev.citation.chunk_id, ()):
            if el.canonical != element.canonical:
                continue
            relation = compare_polarity(claim_sentence, sentence_around(ev.text, el.start, el.end))
            if relation == "same":
                same_polarity = ev.citation.chunk_id
                break
            if relation == "opposite":
                opposite = ev.citation.chunk_id
            else:
                unclear = ev.citation.chunk_id
        if same_polarity:
            break
    if same_polarity:
        return RuleOutcome(element, Verdict.supported, same_polarity, "exact match with the same polarity")
    if opposite:
        return RuleOutcome(element, Verdict.contradicted, opposite, "same value, opposite negation polarity")
    if unclear:
        return RuleOutcome(element, None, None, "same value, polarity unclear (a limit against a plain value)")
    if element.kind in _NUMERIC_KINDS:
        family = _family(element.canonical)
        others = {
            el.canonical
            for ev in cited
            for el in evidence_elements.get(ev.citation.chunk_id, ())
            if el.kind is element.kind and _family(el.canonical) == family
        }
        if len(others) == 1 and single_value_contradiction:
            stated = next(iter(others))
            chunk = next(
                ev.citation.chunk_id
                for ev in cited
                for el in evidence_elements.get(ev.citation.chunk_id, ())
                if el.canonical == stated
            )
            return RuleOutcome(
                element, Verdict.contradicted, chunk, f"evidence states {stated}, claim says {element.canonical}"
            )
        return RuleOutcome(element, None, None, "no matching value in the cited evidence")
    if element.kind is ElementKind.identifier:
        return RuleOutcome(element, Verdict.not_supported, None, "identifier absent from the cited evidence")
    if element.kind is ElementKind.population:
        return RuleOutcome(element, None, None, "population term not found as an element in the cited evidence")
    # indication: containment of the normalized phrase, with the polarity of the surrounding clause
    needle = element.canonical.partition(":")[2]
    for ev in cited:
        for sentence in sentences(ev.text):
            if needle and needle in normalize_for_match(sentence):
                relation = compare_polarity(claim_sentence, _aligned_window(sentence, needle))
                if relation == "same":
                    return RuleOutcome(
                        element, Verdict.supported, ev.citation.chunk_id, "indication phrase contained in evidence"
                    )
                if relation == "opposite":
                    return RuleOutcome(
                        element,
                        Verdict.contradicted,
                        ev.citation.chunk_id,
                        "indication phrase contained but negation polarity differs",
                    )
                return RuleOutcome(element, None, None, "indication phrase contained, polarity unclear")
    return RuleOutcome(element, None, None, "indication phrase not contained in the cited evidence")


def judge_elements(
    claim_text: str, cited: Sequence[Evidence], *, single_value_contradiction: bool = True
) -> tuple[RuleOutcome, ...]:
    """`single_value_contradiction=False` leaves a numeric mismatch undetermined (for the judge) instead of calling
    it a contradiction when the cited evidence states exactly one other value (DEC-003 arm variant)."""
    ev_elements = {e.citation.chunk_id: extract(e.text) for e in cited}
    return tuple(
        judge_element(el, claim_text, cited, ev_elements, single_value_contradiction=single_value_contradiction)
        for el in extract(claim_text)
    )


def contained(claim_text: str, cited: Sequence[Evidence]) -> tuple[str, Polarity] | None:
    """Whole-statement containment: the normalized claim appears verbatim inside one sentence of a cited
    evidence text. Returns (chunk_id, polarity): `超過 300 mg` is contained in `不得超過 300 mg` with the opposite
    polarity (a contradiction, never support); `unclear` leaves the decision to the caller's next stage."""
    needle = normalize_for_match(claim_text)
    if len(needle) < 4:
        return None
    for ev in cited:
        for sentence in sentences(ev.text):
            pos = normalize_for_match(sentence).find(needle)
            if pos >= 0:
                # cues are counted in the aligned window (a short prefix plus the matched span), so a negation
                # elsewhere in a long sentence does not flip the polarity of an unrelated clause
                return ev.citation.chunk_id, compare_polarity(claim_text, _aligned_window(sentence, needle), count=True)
        if needle in normalize_for_match(ev.text):  # crosses a sentence break: compare on the whole text
            return ev.citation.chunk_id, compare_polarity(claim_text, ev.text, count=True)
    return None


_PREFIX_CHARS = 24


def _aligned_window(sentence: str, needle: str) -> str:
    """The raw-text window covering `needle` (normalized) plus up to 24 preceding characters."""
    norm = normalize_for_match(sentence)
    start = norm.find(needle)
    if start < 0:
        return sentence
    # map the normalized offset back to the raw sentence by walking characters that survive normalization
    kept = [i for i, ch in enumerate(sentence) if normalize_for_match(ch)]
    raw_start = kept[start] if start < len(kept) else 0
    raw_end = kept[min(start + len(needle), len(kept)) - 1] + 1 if kept else len(sentence)
    return sentence[max(0, raw_start - _PREFIX_CHARS) : raw_end]


_TOKEN = re.compile(r"[A-Za-z0-9]+|[㐀-鿿]")


def best_overlap(claim_text: str, cited: Sequence[Evidence]) -> tuple[float, str | None, Polarity]:
    """Highest token overlap between the claim and any single evidence sentence: (ratio, chunk_id, polarity)."""
    best: tuple[float, str | None, Polarity] = (0.0, None, "same")
    for ev in cited:
        for sentence in sentences(ev.text):
            ratio = overlap_ratio(claim_text, sentence)
            if ratio > best[0]:
                best = (ratio, ev.citation.chunk_id, compare_polarity(claim_text, sentence, count=True))
    return best


def overlap_ratio(claim_text: str, evidence_text: str) -> float:
    """Share of the claim's content tokens (latin words / digits / CJK characters) present in the evidence."""
    claim_tokens = [t.lower() for t in _TOKEN.findall(claim_text)]
    if not claim_tokens:
        return 0.0
    haystack = set(t.lower() for t in _TOKEN.findall(evidence_text))
    return sum(1 for t in claim_tokens if t in haystack) / len(claim_tokens)
