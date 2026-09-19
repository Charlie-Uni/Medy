"""Versioned lexical tokenizers for the DEC-001 experiments (ADR-0002 candidate A).

Every tokenizer exposes `tokenizer_version` and `dictionary_version`; both must be recorded
in index metadata and `retrieval_version` (baseline 3.6). A version mismatch between index
and query time must be rejected by the caller, never silently tolerated.

The jieba tokenizer is adapted from the legacy 文枢 project (`app/retrieval/bm25.py`) with
these deliberate changes: each instance owns a private `jieba.Tokenizer` (no shared global dictionary); norm-v1 runs first; no NFKC and no full-text lowercasing (only
ASCII-letter tokens are case-folded, as a documented tokenizer rule); identifier and numeric
tokens such as `PROT-2024-017`, `NCT04283461` and `0.5` are preserved whole in addition to
the segmenter output; there is no silent regex fallback when jieba is missing.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

_ID_TOKEN = re.compile(r"[A-Za-z]{2,}(?:-\d{2,})+|\b[A-Z]{2,}\d{5,}\b|\b\d+(?:\.\d+)?\b")
_PUNCT_ONLY = re.compile(r"^[\W_]+$")


class Tokenizer(Protocol):
    tokenizer_version: str
    dictionary_version: str
    normalization_version: str

    def tokenize(self, text: str) -> list[str]: ...


def _fold_ascii(token: str) -> str:
    return token.lower() if token.isascii() else token


class JiebaTokenizerV1:
    """jieba-based tokenizer, version `tok-jieba-v1`.

    `user_dictionary` is an optional jieba user dictionary file (medical terms, brand names).
    `dictionary_version` is derived from jieba's version plus the SHA-256 of that file so that
    any dictionary change produces a new version.
    """

    tokenizer_version = "tok-jieba-v1"
    normalization_version = NORMALIZATION_VERSION

    def __init__(self, user_dictionary: Path | None = None) -> None:
        try:
            import jieba  # noqa: WPS433 - optional heavy dependency
        except ImportError as exc:  # pragma: no cover - exercised only without jieba
            raise RuntimeError("JiebaTokenizerV1 requires the 'jieba' package; no silent fallback") from exc
        jieba.setLogLevel(60)
        # One jieba.Tokenizer per instance: the module-level API shares a single global dictionary,
        # so loading a user dictionary on one instance would silently change every other instance's
        # output while their dictionary_version stayed the same (review 04, 2026-09-10).
        self._jieba = jieba.Tokenizer()
        dict_hash = "default"
        if user_dictionary is not None:
            data = Path(user_dictionary).read_bytes()
            dict_hash = hashlib.sha256(data).hexdigest()[:16]
            self._jieba.load_userdict(str(user_dictionary))
        self.dictionary_version = f"jieba-{jieba.__version__}+{dict_hash}"

    def tokenize(self, text: str) -> list[str]:
        normalized = normalize_text(text)
        if not normalized:
            return []
        tokens: list[str] = []
        for raw in self._jieba.cut(normalized, HMM=True):
            token = raw.strip()
            if not token or _PUNCT_ONLY.match(token):
                continue
            tokens.append(_fold_ascii(token))
        # Preserve identifiers and numbers whole so precise-clause queries match exactly.
        for match in _ID_TOKEN.finditer(normalized):
            whole = _fold_ascii(match.group(0))
            if whole not in tokens:
                tokens.append(whole)
        return tokens


class RegexTokenizerV1:
    """Dependency-free tokenizer, version `tok-regex-v1`: one token per CJK character plus
    ASCII words and numbers. Intended for unit tests and as an explicit, separately versioned
    baseline; never substituted for the jieba tokenizer automatically."""

    tokenizer_version = "tok-regex-v1"
    dictionary_version = "none"
    normalization_version = NORMALIZATION_VERSION
    _PATTERN = re.compile(r"[㐀-䶿一-鿿]|[A-Za-z]+(?:-\d+)+|[A-Za-z0-9]+(?:\.\d+)?")

    def tokenize(self, text: str) -> list[str]:
        normalized = normalize_text(text)
        return [_fold_ascii(t) for t in self._PATTERN.findall(normalized)]
