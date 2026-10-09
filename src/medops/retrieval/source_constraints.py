"""High-confidence named-source constraints, disabled until released as a retrieval parameter.

`doc_focus-v1` boosts every recognized identifier.  That is useful for recall but cannot enforce source identity:
an identifier can name the requested document, a reference discussed by another document, or text embedded in a
combined publication.  This module resolves only high-confidence source requests and supports narrowly reviewed
equivalent carriers.  An unresolved request means "the requested source is not visible", never "it exists elsewhere".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from medops.retrieval.doc_focus import DocRef, document_keys, norm, query_key_mentions, query_keys

SOURCE_CONSTRAINT_VERSION = "source-constraint-v1"

_RELATIONSHIP = re.compile(r"(?:关系|關係|有何关联|有何關聯|relationship|relate(?:d|s)?\s+to)", re.I)
_DISCUSSION_REFERENCE = re.compile(
    r"(?:(?:对|對)\s*ICH\s*[A-Z0-9()]+\s*(?:及|和|与|與|、|/|and|or)?[^，,？?]{0,30}(?:讨论|討論)"
    r"|discussion\s+of\s+ICH\s*[A-Z0-9()]+)",
    re.I,
)
_ADOPT_REFERENCE = re.compile(r"(?:采用|採用|采纳|採納|adopt(?:s|ed)?)", re.I)
_HOST_CONTEXT = re.compile(r"(?:本文件|this document)", re.I)
_FDA_HOST = re.compile(r"\bFDA\b|美国食品药品监督管理局|美國食品藥品監督管理局", re.I)
_QUOTED = re.compile(r"《([^》]{6,160})》|[“\"]([^”\"]{15,180})[”\"]")
_PRODUCT_LABEL = re.compile(r"(?:根据|根據|按照|依據|依据|按)\s*([^，,。？?]{2,40}?(?:仿單|仿单|說明書|说明书))", re.I)
_GENERIC_LABEL_NAMES = {"膜衣", "糖衣", "腸溶", "肠溶", "持續", "持续", "口溶"}


@dataclass(frozen=True)
class SourceConstraint:
    required: bool
    document_ids: tuple[str, ...] = ()
    document_keys: tuple[str, ...] = ()
    requested_keys: tuple[str, ...] = ()
    referenced_keys: tuple[str, ...] = ()
    missing: bool = False
    used_equivalent_carrier: bool = False


def _quoted_titles(query: str) -> list[str]:
    titles = []
    for match in _QUOTED.finditer(unicodedata.normalize("NFKC", query)):
        title = next(group for group in match.groups() if group is not None).strip()
        # Avoid treating a quoted term such as “reasonable possibility” as a document title.
        if len(re.findall(r"[A-Za-z]+", title)) >= 4 or len(re.findall(r"[一-鿿]", title)) >= 6:
            titles.append(title)
    return titles


def _requested_mentions(query: str):
    mentions = query_key_mentions(query)
    if not mentions or (_RELATIONSHIP.search(query) and len(mentions) > 1):
        return [], mentions
    normalized = unicodedata.normalize("NFKC", query)
    lower = normalized.lower()
    if _HOST_CONTEXT.search(normalized):
        return [], mentions
    # "A cites B": A is the host.  "B, as cited/included in A": A is the host.
    cite = re.search(r"引用|引述|援引|cites?\s+(?:from\s+)?", normalized, re.I)
    as_cited = re.search(r"as cited in|included with|included in", lower)
    if cite:
        before = [mention for mention in mentions if mention.end <= cite.start()]
        if before:
            host = before[-1]
            return [host], [mention for mention in mentions if mention != host]
    if as_cited:
        after = [mention for mention in mentions if mention.start >= as_cited.end()]
        if after:
            host = after[0]
            return [host], [mention for mention in mentions if mention != host]
    if "合订文件" in normalized or "合訂文件" in normalized:
        revised = [mention for mention in mentions if "r" in mention.key]
        if revised:
            return [revised[0]], [mention for mention in mentions if mention != revised[0]]
    if _DISCUSSION_REFERENCE.search(normalized) or (
        _ADOPT_REFERENCE.search(normalized) and _FDA_HOST.search(normalized)
    ):
        return [], mentions
    # The leading / first identifier is the requested source.  Later identifiers are references unless the query is
    # a relationship question (handled above).  This covers "According to X", "X 的...", and "what does X use".
    return [mentions[0]], mentions[1:]


def _authority_matches(authority: str | None, doc: DocRef) -> bool:
    document_key = doc.document_key
    title = doc.title.upper()
    if authority == "ich":
        return document_key.startswith("ich-") or title.startswith("ICH ")
    if authority == "fda":
        return document_key.startswith("fda-") or "FDA" in title
    if authority == "ema":
        return document_key.startswith("ema-") or "GOOD PHARMACOVIGILANCE PRACTICES" in title
    return True


def _qualifier_matches(query: str, doc: DocRef) -> bool:
    """Keep a qualified companion document from satisfying an unqualified source request."""
    annex = re.search(r"\bAnnex\s+([IVX]+|\d+)\b", doc.title, re.I)
    if annex and not re.search(r"(?:\bAnnex\s+|附件|附录|附錄)", query, re.I):
        return False
    return True


def _label_name_matches(query: str, doc: DocRef) -> bool:
    for key in document_keys(doc.title, doc.doc_type):
        if not key.startswith("name:"):
            continue
        name = key.split(":", 1)[1]
        if name not in _GENERIC_LABEL_NAMES and name in norm(query):
            return True
    return False


def _equivalent_carriers(query: str, requested_keys: set[str], docs: list[DocRef]) -> list[DocRef]:
    # Human-reviewed source contract: the GVP VI addendum quotes the E2B(R2) A.1.12 Linked reports rule.  The
    # exception is deliberately topic-scoped; it does not make the whole addendum equivalent to E2B(R2).
    compact = norm(query)
    if "ich:e2br2" in requested_keys and ("a112" in compact or "linkedreports" in compact):
        return [
            doc
            for doc in docs
            if doc.document_key == "ema-gvp-module-vi-addendum-i"
            or re.search(r"\bGVP Module VI Addendum I\b(?!I)", doc.title, re.I)
        ]
    return []


def resolve_source_constraint(query: str, docs: list[DocRef]) -> SourceConstraint:
    """Resolve a strict source request against only documents visible to the caller.

    No match reports a generic missing constraint.  Callers must not reveal document ids, titles, departments or
    whether another principal could see the requested source.
    """
    requested, referenced = _requested_mentions(query)
    requested_keys = {mention.key for mention in requested}
    matched: dict[str, DocRef] = {}
    for mention in requested:
        for doc in docs:
            if (
                mention.key in document_keys(doc.title, doc.doc_type)
                and _authority_matches(mention.authority, doc)
                and _qualifier_matches(query, doc)
            ):
                matched[doc.doc_id] = doc

    titles = _quoted_titles(query)
    for title in titles:
        needle = norm(title)
        for doc in docs:
            if needle and needle in norm(doc.title):
                matched[doc.doc_id] = doc

    product_phrase = _PRODUCT_LABEL.search(query)
    for doc in docs:
        if _label_name_matches(query, doc):
            matched[doc.doc_id] = doc

    equivalent = _equivalent_carriers(query, requested_keys, docs) if not matched else []
    for doc in equivalent:
        matched[doc.doc_id] = doc

    required = bool(requested or titles or product_phrase or matched)
    selected = sorted(matched.values(), key=lambda doc: (doc.title, doc.doc_id))
    return SourceConstraint(
        required=required,
        document_ids=tuple(doc.doc_id for doc in selected),
        document_keys=tuple(doc.document_key or doc.doc_id for doc in selected),
        requested_keys=tuple(sorted(requested_keys)),
        referenced_keys=tuple(sorted({mention.key for mention in referenced} | (query_keys(query) - requested_keys))),
        missing=required and not selected,
        used_equivalent_carrier=bool(equivalent),
    )
