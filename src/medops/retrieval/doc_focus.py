"""Named-document focus (record 94, released retrieval parameter `doc_focus`).

Many questions name the document they are about — a product by its Chinese brand name (拔痛酸錠), an ICH guideline
by its code (ICH E6(R3)), a GVP module by its number (GVP Module IX Addendum I), a Taiwanese guidance by its title.
When the corpus holds that document, its own chunks are the only acceptable evidence for the question (the corpus
has sibling documents with identical sentences: generic labels of one ingredient, an ICH text and its FDA reprint),
yet a corpus-wide search ranks by text similarity alone and may surface the sibling, or nothing when the question is
in Chinese and the document in English.

With `doc_focus` on, the retrieval port derives *keys* from the titles of the documents the caller may read
(department scope applies through the connection), matches them against the normalized question, and for every
matched document (at most `MAX_FOCUS_DOCS`, otherwise the mention is ambiguous and ignored) runs the lexical and the
vector channel restricted to that document. Those rankings join the reciprocal-rank fusion next to the corpus-wide
ones; nothing is removed, the reranker still judges every candidate against the question. The rules are deterministic
and versioned (`DOC_FOCUS_VERSION` enters `retrieval_version` through `rewrite_params`).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

DOC_FOCUS_VERSION = "docfocus-v1"
MAX_FOCUS_DOCS = 3  # more matches than this means the mention is not a specific document
FOCUS_K = 20  # candidates per channel inside one focused document (the fused limit; the reranker judges the rest)
MIN_CJK_TITLE_KEY = 6

_ROMAN = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "8": "VIII",
    "9": "IX",
    "10": "X",
    "11": "XI",
    "12": "XII",
    "13": "XIII",
    "14": "XIV",
    "15": "XV",
    "16": "XVI",
}
_LABEL_NAME = re.compile(
    r"^[\s\"“〝『「]*(?:[一-鿿]{1,6}[\s\"”〞』」]+)?([一-鿿]{2,12}?)"
    r"(?=[0-9０-９]|錠|膜衣|膠囊|注射|輸注|糖漿|懸浮|散劑|軟膠|口溶|腸溶|持續|凍晶|靜脈|內服|乾粉|溶液|軟膏|點眼|粉|膠劑|乳膏|栓)"
)
_ICH_TITLE = re.compile(r"(?<![A-Za-z0-9])(E\d{1,2}[A-Z]?|M\d{1,2}[A-Z]?)\s*(\(R\d\))?(?![A-Za-z0-9])")
_ICH_QUERY = re.compile(r"(?<![A-Za-z0-9])(E\d{1,2}[A-Z]?|M\d{1,2}[A-Z]?)\s*(\(\s*R\d\s*\))?(?![A-Za-z0-9])")
_GVP_TITLE = re.compile(
    r"(?:Module\s+([IVX]+)(?:\s+Addendum\s+([IVX]+))?|Annex\s+([IVX]+)|Considerations\s+([IVX]+))", re.I
)
_GVP_QUERY = re.compile(
    r"GVP\s*(?:(Module|模块|模組)\s*([IVX]+|\d{1,2})(?:\s*(?:Addendum|附录|附錄)\s*([IVX]+|\d{1,2}))?"
    r"|(Annex|附件)\s*([IVX]+|\d{1,2})|(P\.?|Product-\s*or\s*Population-Specific\s*Considerations)\s*([IVX]+|\d{1,2}))",
    re.I,
)
_CJK = re.compile(r"[一-鿿]")


@dataclass(frozen=True)
class DocRef:
    doc_id: str
    title: str
    doc_type: str


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\s　()（）\[\]【】「」『』\"'“”‘’〝〞,，.。;；:：、\-–—／/]", "", text)


def _roman(token: str) -> str:
    token = token.upper()
    return _ROMAN.get(token, token) if token.isdigit() else token


def document_keys(title: str, doc_type: str) -> set[str]:
    """Deterministic keys a question may use to name this document (docfocus-v1)."""
    keys: set[str] = set()
    t = unicodedata.normalize("NFKC", title)
    if doc_type == "label":
        m = _LABEL_NAME.match(t)
        if m:
            keys.add("name:" + norm(m.group(1)))
        return keys
    if "GVP" in t.upper() or "pharmacovigilance practices" in t.lower():
        m = _GVP_TITLE.search(t)
        if m:
            if m.group(1):
                key = f"gvp:module {m.group(1).upper()}" + (f" addendum {m.group(2).upper()}" if m.group(2) else "")
            elif m.group(3):
                key = f"gvp:annex {m.group(3).upper()}"
            else:
                key = f"gvp:p {m.group(4).upper()}"
            keys.add(key)
        return keys
    if "ICH" in t.upper() or _ICH_TITLE.match(t.strip()):
        m = _ICH_TITLE.search(t)
        if m:
            keys.add("ich:" + norm(m.group(1) + (m.group(2) or "")))
        return keys
    if _CJK.search(t):
        core = re.split(r"[（(]", t, maxsplit=1)[0]
        core = re.sub(r"第[一二三四五六七八九十\d]+版", "", core)
        key = norm(core)
        if len(key) >= MIN_CJK_TITLE_KEY:
            keys.add("title:" + key)
    return keys


def query_keys(query: str) -> set[str]:
    q = unicodedata.normalize("NFKC", query)
    keys: set[str] = set()
    for m in _ICH_QUERY.finditer(q):
        code, rev = m.group(1), m.group(2)
        window = q[max(0, m.start() - 8) : m.start()]
        if rev or "ICH" in window.upper():
            keys.add("ich:" + norm(code + (rev or "")))
    for m in _GVP_QUERY.finditer(q):
        if m.group(1):
            key = f"gvp:module {_roman(m.group(2))}" + (f" addendum {_roman(m.group(3))}" if m.group(3) else "")
        elif m.group(4):
            key = f"gvp:annex {_roman(m.group(5))}"
        else:
            key = f"gvp:p {_roman(m.group(7))}"
        keys.add(key)
    return keys


def focus_documents(query: str, docs: Iterable[DocRef]) -> list[DocRef]:
    """Documents the question names, in title order; empty when none or when the mention is ambiguous."""
    nq = norm(query)
    qkeys = query_keys(query)
    matched: list[DocRef] = []
    for doc in docs:
        for key in document_keys(doc.title, doc.doc_type):
            if key.startswith(("ich:", "gvp:")):
                hit = key in qkeys
            else:
                hit = key.split(":", 1)[1] in nq
            if hit:
                matched.append(doc)
                break
    matched.sort(key=lambda d: (d.title, d.doc_id))
    return matched if 0 < len(matched) <= MAX_FOCUS_DOCS else []


def load_documents(conn: object) -> list[DocRef]:
    """Active documents visible on this connection (row-level security scopes them to the caller's department)."""
    rows = conn.execute("select doc_id::text, title, doc_type from documents where status = 'active'").fetchall()  # type: ignore[attr-defined]
    return [DocRef(str(r[0]), str(r[1]), str(r[2])) for r in rows]


def load_titles(conn: object, doc_ids: Sequence[str]) -> dict[str, str]:
    """Titles of the given documents as far as this connection may read them (row-level security applies)."""
    if not doc_ids:
        return {}
    rows = conn.execute(  # type: ignore[attr-defined]
        "select doc_id::text, title from documents where doc_id = any(%s::uuid[])", (list(doc_ids),)
    ).fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def as_sequence(docs: Sequence[DocRef]) -> list[str]:
    return [d.doc_id for d in docs]
