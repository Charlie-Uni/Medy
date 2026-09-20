"""Bounded, rule-based query rewriting (M1-13; baseline 5.2; INV-HAR-05).

The rewriter turns one user query plus the trusted session entities and a versioned glossary into 1 to 3
plain-text queries for the retrievers. It is deterministic, has no model and no state:

- query 1 is always the norm-v1 normalized user query, unchanged;
- query 2 (optional) appends up to `MAX_ENTITY_TERMS` trusted session entity values (drug, protocol,
  indication, population) that the query does not already contain;
- query 3 (optional) appends up to `MAX_GLOSSARY_TERMS` glossary synonyms of terms found in the query
  (generic/brand names, abbreviations), matched only outside protected spans.

Rewrites are append-only: no token of the original is ever removed, replaced or reordered, so doses, units,
negations, time windows and identifiers survive verbatim in every query. `PROTECTED_PATTERNS` name those
spans explicitly; they gate glossary matching and are re-verified on every result (fail closed). The output
is text only: no filter expression, department, status or date can be produced from user text (baseline
5.2 "用户文本不得直接生成 SQL、过滤表达式或权限条件"); those come from the trusted identity and the request.

Session isolation: entities are an explicit argument of one call; nothing is remembered between calls. The
glossary is versioned (`Glossary.version`) and its content arrives with DEC-005; until then `Glossary.empty()`
(`glossary-none`) yields no glossary query. Both versions are returned for the trace (INV-HAR-05).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import DomainModel, NonEmptyStr
from medops.domain.intent import Entity
from medops.domain.state import MAX_REWRITTEN_QUERIES
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

REWRITER_VERSION = "qr-rules-v1"
MAX_QUERY_CHARS = 512
MAX_ENTITY_TERMS = 3
MAX_GLOSSARY_TERMS = 5
ENTITY_KINDS: tuple[str, ...] = ("drug", "protocol", "indication", "population")

_ASCII_WORD = re.compile(r"[A-Za-z0-9]")

PROTECTED_PATTERNS: dict[str, re.Pattern[str]] = {
    # numbers with their unit or count word: doses, frequencies, time windows, percentages, ages
    "number_unit": re.compile(
        r"\d+(?:[.,]\d+)?(?:\s*(?:[A-Za-zμ%²/]+(?:/[A-Za-z²]+)?|[錠片粒次天日時分週周月年歲岁小]+))?"
    ),
    # identifiers: ICH E8(R1), E6(R3), PROT-2024-017, SOP-QA-001, GVP Module IX, version numbers
    "identifier": re.compile(
        r"\b[A-Za-z]{1,8}(?:-[A-Za-z0-9]+)+\b|\b[A-Z]{1,4}\d{1,3}(?:\([A-Z]\d\))?\b|第\s*\d+\s*[號号]"
    ),
    # negation and restriction words whose loss would invert the meaning
    "negation": re.compile(
        r"禁用|禁止|不得|不可|不能|不宜|不推荐|不推薦|不建议|不建議|无需|無需|除外|避免|慎用|不要|不应|不應|不必|勿|"
        r"\b(?:do not|don't|must not|should not|cannot|not|no|never|without|except|avoid|contraindicated)\b",
        re.IGNORECASE,
    ),
}


class GlossaryEntry(DomainModel):
    term: NonEmptyStr
    synonyms: tuple[NonEmptyStr, ...] = Field(min_length=1)
    kind: Literal["generic", "brand", "abbreviation", "other"] = "other"

    @model_validator(mode="after")
    def _rules(self) -> GlossaryEntry:
        for text in (self.term, *self.synonyms):
            if normalize_text(text) != text:
                raise ValueError(f"glossary text must already be norm-v1 normalized: {text!r}")
            if any(unicodedata.category(ch).startswith("C") for ch in text):
                raise ValueError("glossary text must not contain control characters")
        if self.term in self.synonyms or len(set(self.synonyms)) != len(self.synonyms):
            raise ValueError("synonyms must be distinct from the term and from each other")
        return self


class Glossary(DomainModel):
    """A versioned term table. Content is a DEC-005 deliverable; the structure is fixed here."""

    version: NonEmptyStr
    entries: tuple[GlossaryEntry, ...] = ()

    @model_validator(mode="after")
    def _unique_terms(self) -> Glossary:
        terms = [e.term for e in self.entries]
        if len(set(terms)) != len(terms):
            raise ValueError("glossary terms must be unique")
        return self

    @classmethod
    def empty(cls) -> Glossary:
        return cls(version="glossary-none")


def load_glossary(path: Path) -> Glossary:
    return Glossary.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


class RewriteResult(DomainModel):
    """Text queries only; there is deliberately no field for filters, departments, dates or SQL."""

    queries: tuple[NonEmptyStr, ...] = Field(min_length=1, max_length=MAX_REWRITTEN_QUERIES)
    rewriter_version: NonEmptyStr
    glossary_version: NonEmptyStr
    normalization_version: NonEmptyStr
    added_entities: tuple[str, ...] = ()
    added_terms: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _rules(self) -> RewriteResult:
        if len(set(self.queries)) != len(self.queries):
            raise ValueError("rewritten queries must be distinct")
        if any(len(q) > MAX_QUERY_CHARS for q in self.queries):
            raise ValueError(f"rewritten queries must not exceed {MAX_QUERY_CHARS} characters")
        return self


# ------------------------------------------------------------------------------------ spans


def protected_spans(text: str) -> tuple[tuple[int, int, str], ...]:
    """`(start, end, kind)` of every protected span in `text`, merged and ordered."""
    found: list[tuple[int, int, str]] = []
    for kind, pattern in PROTECTED_PATTERNS.items():
        for m in pattern.finditer(text):
            if m.end() > m.start():
                found.append((m.start(), m.end(), kind))
    found.sort()
    merged: list[tuple[int, int, str]] = []
    for start, end, kind in found:
        if merged and start < merged[-1][1]:
            prev = merged[-1]
            merged[-1] = (prev[0], max(prev[1], end), prev[2])
        else:
            merged.append((start, end, kind))
    return tuple(merged)


def _inside(spans: Sequence[tuple[int, int, str]], start: int, end: int) -> bool:
    return any(s <= start and end <= e for s, e, _ in spans)


def _contains(text: str, term: str) -> bool:
    """Whole-word for ASCII terms (case-insensitive), substring for CJK terms."""
    if _ASCII_WORD.search(term):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return term in text


def _matches_outside_protected(text: str, term: str, spans: Sequence[tuple[int, int, str]]) -> bool:
    if _ASCII_WORD.search(term):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)
    else:
        pattern = re.compile(re.escape(term))
    return any(not _inside(spans, m.start(), m.end()) for m in pattern.finditer(text))


# ------------------------------------------------------------------------------------ rewrite


def _clean_entity(value: str) -> str | None:
    if any(unicodedata.category(ch).startswith("C") for ch in value):
        return None
    normalized = normalize_text(value)
    return normalized or None


def rewrite(query: str, *, entities: Sequence[Entity] = (), glossary: Glossary | None = None) -> RewriteResult:
    glossary = glossary or Glossary.empty()
    base = normalize_text(query)
    if not base:
        raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
    if len(base) > MAX_QUERY_CHARS:
        raise BusinessError(ErrorCode.invalid_request, f"query exceeds {MAX_QUERY_CHARS} characters")
    spans = protected_spans(base)
    queries: list[str] = [base]

    added_entities: list[str] = []
    for entity in entities:
        if entity.kind not in ENTITY_KINDS or len(added_entities) >= MAX_ENTITY_TERMS:
            continue
        value = _clean_entity(entity.value)
        if value is None or _contains(base, value) or value in added_entities:
            continue
        added_entities.append(value)
    if added_entities:
        queries.append(base + " " + " ".join(added_entities))

    added_terms: list[str] = []
    for entry in glossary.entries:
        if len(added_terms) >= MAX_GLOSSARY_TERMS:
            break
        if not _matches_outside_protected(base, entry.term, spans):
            continue
        for synonym in entry.synonyms:
            if len(added_terms) >= MAX_GLOSSARY_TERMS:
                break
            if _contains(base, synonym) or synonym in added_terms:
                continue
            added_terms.append(synonym)
    if added_terms:
        queries.append(base + " " + " ".join(added_terms))

    bounded = tuple(dict.fromkeys(q for q in queries if len(q) <= MAX_QUERY_CHARS))[:MAX_REWRITTEN_QUERIES]
    for candidate in bounded:
        if not candidate.startswith(base) or any(base[s:e] not in candidate for s, e, _ in spans):
            raise InfrastructureError(
                ErrorCode.internal_error, detail="rewrite altered a protected span of the query", retryable=False
            )
    return RewriteResult(
        queries=bounded,
        rewriter_version=REWRITER_VERSION,
        glossary_version=glossary.version,
        normalization_version=NORMALIZATION_VERSION,
        added_entities=tuple(added_entities),
        added_terms=tuple(added_terms),
    )
