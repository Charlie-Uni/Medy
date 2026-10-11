"""norm-v1 text normalization (evals/probe/precise_clause/SPEC.md section 4.1).

Fixed order:
1. Unicode NFC (never NFKC).
2. Remove extraction whitespace between CJK/CJK and CJK/Chinese-punctuation pairs.
3. Map full-width ASCII U+FF01..U+FF5E to U+0021..U+007E and U+3000 to a space.
4. Unify micro sign U+00B5 to Greek mu U+03BC.
5. Apply the versioned unit whitelist `unit-map-v1`; no generic compatibility folding.
6. Collapse remaining whitespace runs to one space and strip.

Superscripts, subscripts and circled digits are preserved. Case is not folded.
The vectors in evals/probe/precise_clause/tests/norm_v1_vectors.json are the contract (PR-14).
"""

from __future__ import annotations

import re
import unicodedata

NORMALIZATION_VERSION = "norm-v1"
UNIT_MAP_VERSION = "unit-map-v1"

_CJK = "㐀-䶿一-鿿豈-﫿"
_ZH_PUNCT = "、-〃〈-】〔-〟！-／：-＠［-｀｛-･"
_WS_BETWEEN = re.compile(rf"(?<=[{_CJK}{_ZH_PUNCT}])\s+(?=[{_CJK}{_ZH_PUNCT}])")
_FULLWIDTH = {chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)}
_FULLWIDTH["　"] = " "
_WS_RUN = re.compile(r"\s+")

UNIT_MAP_V1: dict[str, str] = {
    "㎎": "mg",  # ㎎
    "㎍": "μg",  # ㎍ -> μg
    "㎖": "mL",  # ㎖
    "㎏": "kg",  # ㎏
    "㎜": "mm",  # ㎜
    "㎝": "cm",  # ㎝
    "㎡": "m²",  # ㎡ -> m²
    "㎕": "μL",  # ㎕ -> μL
    "㎗": "dL",  # ㎗
    "℃": "°C",  # ℃ -> °C
}


def normalize_text(text: str) -> str:
    """Apply norm-v1 to `text`."""
    s = unicodedata.normalize("NFC", text)
    s = _WS_BETWEEN.sub("", s)
    s = "".join(_FULLWIDTH.get(ch, ch) for ch in s)
    s = s.replace("µ", "μ")
    for source, target in UNIT_MAP_V1.items():
        s = s.replace(source, target)
    return _WS_RUN.sub(" ", s).strip()
