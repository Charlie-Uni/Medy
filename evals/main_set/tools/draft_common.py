"""Shared helpers for the main-set (spec-m1) drafting tools: corpus/page access, verbatim locating of LLM-proposed
text in norm-v1 page text, mechanical slice checks and the draft sample shape consumed by the sheets/review tools.

Nothing here writes samples.jsonl; drafts become samples only after annotator-01 confirmation and the LLM second
review (SPEC section 4)."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any

from medops.retrieval.lexical.normalization import normalize_text

REPO = pathlib.Path(__file__).resolve().parents[3]
MAIN = REPO / "evals/main_set"
CORPUS = MAIN / "corpus.json"
PAGES_DIRS = (MAIN / "pages", REPO / "evals/probe/precise_clause/v1/pages")
DRAFTS = MAIN / "drafts/main-v1"
PROBE_SAMPLES = REPO / "evals/probe/precise_clause/v2/samples.jsonl"
DEFAULT_BINARY = str(pathlib.Path.home() / ".local/bin/claude")
CAP_PER_DOCUMENT = 8  # spec-m1 section 7 item 1 (non-derived samples)
# low_trust drafts in medops_v2 (record 49): in corpus.json but not active, so they cannot be gold
INACTIVE_KEYS = {
    "tfda-label-supercillin-powder-for-oral-suspension-v",
    "tfda-label-zotan-s-r-capsules-0-2mg",
    "tfda-label-xyrizine-f-c-tablets-5mg-levocetirizine",
}
SLICES = ("drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en")
NEW_SLICES = ("version_conflict", "no_answer", "long_context")
LONG_CONTEXT_CHARS = 1500
UNIT_TOKENS = {
    "mg",
    "g",
    "kg",
    "mcg",
    "ug",
    "ml",
    "l",
    "dl",
    "iu",
    "u",
    "mmol",
    "meq",
    "mm",
    "cm",
    "kcal",
    "h",
    "hr",
    "hrs",
    "min",
    "mins",
    "sec",
    "s",
    "d",
    "wk",
    "mo",
    "yr",
    "ppm",
    "bpm",
    "msec",
    "ms",
    "gy",
    "mgy",
    "au",
}
_page_cache: dict[tuple[str, int], str | None] = {}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_corpus() -> dict[str, dict]:
    docs = json.loads(CORPUS.read_text(encoding="utf-8"))["documents"]
    return {d["document_key"]: d for d in docs}


def pages_dir(source_hash: str) -> pathlib.Path | None:
    for base in PAGES_DIRS:
        if (base / source_hash).is_dir():
            return base / source_hash
    return None


def page_text(source_hash: str, page: int) -> str | None:
    key = (source_hash, page)
    if key not in _page_cache:
        base = pages_dir(source_hash)
        path = base / f"{page}.txt" if base else None
        _page_cache[key] = normalize_text(path.read_text(encoding="utf-8")) if path and path.is_file() else None
    return _page_cache[key]


def probe_usage() -> dict[str, int]:
    """Non-derived probe samples per source_hash (they count against the per-document cap)."""
    used: dict[str, int] = {}
    for line in PROBE_SAMPLES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        if s.get("derived_from"):
            continue
        for h in {g["source_hash"] for g in s["required_gold_evidence"]}:
            used[h] = used.get(h, 0) + 1
    return used


_QUOTES = {
    "'": "['’‘`]",
    '"': '["“”]',
    "-": "[-‐‑‒–—]",
    ",": "[,，]",
    "(": "[(（]",
    ")": "[)）]",
    ":": "[:：]",
    ";": "[;；]",
}


def _tolerant_pattern(needle: str) -> str:
    parts = []
    for ch in needle:
        if ch.isspace():
            continue
        alt = None
        for canon, cls in _QUOTES.items():
            if ch == canon or re.fullmatch(cls, ch):
                alt = cls
                break
        parts.append(alt or re.escape(ch))
    return r"\s*".join(parts)


def locate(text: str, needle: str) -> tuple[str, int, str]:
    """Find `needle` in norm-v1 `text`. Returns (status, start, exact_page_substring):
    status 'exact' (unique verbatim), 'tolerant' (unique after whitespace/quote/dash tolerance), 'multi:<n>'
    (not unique) or 'missing'. The returned substring is always taken from the page text itself."""
    n = normalize_text(needle).strip()
    if not n:
        return "missing", -1, ""
    c = text.count(n)
    if c == 1:
        i = text.index(n)
        return "exact", i, n
    if c > 1:
        return f"multi:{c}", -1, n
    try:
        matches = list(re.finditer(_tolerant_pattern(n), text))
    except re.error:
        return "missing", -1, ""
    if len(matches) == 1:
        m = matches[0]
        return "tolerant", m.start(), text[m.start() : m.end()]
    if len(matches) > 1:
        return f"multi:{len(matches)}", -1, n
    return "missing", -1, ""


_LATIN = re.compile(r"[A-Za-z][A-Za-z\-\./']*[A-Za-z]|[A-Za-z]{2,}")
_NUM_UNIT = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|g|kg|mcg|μg|µg|ug|mL|ml|L|dL|IU|U|mmol|mEq|%|毫克|公克|克|微克|毫升|公升|單位|单位|國際單位)"
    r"|(?:每日|每天|一日|一天|每週|每周|每次|每晚|每小時|每 ?\d+ ?小時)"
    r"|\b(?:once|twice|three times|four times)\b\s*(?:daily|a day|per day|weekly)?"
    r"|\b(?:daily|weekly|q\.?d\.?|b\.?i\.?d\.?|t\.?i\.?d\.?|q\.?i\.?d\.?)\b",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?:within|no later than|not later than|at least|after|before|prior to|every|each)\b[^.;]{0,40}?\b\d+\s*"
    r"(?:calendar |working |business )?(?:days?|hours?|weeks?|months?|years?|minutes?)\b"
    r"|\b\d+\s*(?:calendar |working |business )?(?:days?|hours?|weeks?|months?|years?)\b"
    r"|\d+\s*(?:個月|个月|天|日|小時|小时|週|周|年|分鐘|分钟)\s*(?:內|内|以內|以内|之內|之内|後|后|前)?"
    r"|(?:數|数)?(?:小時|小时|天|週|周|個月|个月)(?:內|内)",
    re.IGNORECASE,
)
_NEG = re.compile(
    r"\b(?:not|no|never|none|neither|nor|cannot|without|except|unless|excluded?|exempt(?:ed)?|prohibit(?:ed|s)?|"
    r"contraindicated|avoid(?:ed)?|unnecessary|inappropriate|insufficient|only)\b"
    r"|不得|不可|不能|不應|不应|不宜|不建議|不建议|不推薦|不推荐|不需|無需|无需|不必|禁止|禁用|禁忌|勿|避免|除外|除非|不包括|不含|"
    r"不屬於|不属于|不是|不會|不会|不足|無法|无法|不予|不再|不適用|不适用|不列入|僅|仅|只",
    re.IGNORECASE,
)
_ID = re.compile(
    r"\b(?:ICH\s*)?[EMQS]\d{1,2}[A-Z]?(?:\s?\(R\d\))?\b|\bModule\s+[IVX]+\b|\b21\s*CFR\s*\d+|"
    r"\bRev(?:ision)?\s*\d\b|\bGVP\b|\bDSUR\b|\bPSUR\b|\bPBRER\b|\bICSR\b|\bSOP\b|\bMedDRA\b|\bSMQ\b|"
    r"\bPart\s+\d+\b|\b(?:§|Section|Sec\.)\s*\d+(?:\.\d+)*|\bAnnex\s+[IVX\d]+\b|\bversion\s+\d|"
    r"許可證|字第\d+號|版本|第\s*\d+(?:\.\d+)*\s*(?:條|条|章|節|节|版)|附錄|附录|附件"
)


def latin_terms(text: str) -> list[str]:
    """English terms/abbreviations in text, ignoring bare unit symbols (P2 mechanical rule)."""
    out = []
    for m in _LATIN.finditer(text):
        tok = m.group(0)
        if tok.lower().strip(".") in UNIT_TOKENS:
            continue
        if len(tok) == 1:
            continue
        out.append(tok)
    return out


def mixed_zh_en(query: str, key_text: str) -> bool:
    return bool(latin_terms(query)) or bool(latin_terms(key_text))


def slice_warnings(query: str, span: str, slices: list[str], doc: dict) -> list[str]:
    """Advisory checks (P2/P3 mechanics); the annotator and the LLM reviewer judge semantics."""
    w = []
    if "dose_unit" in slices and not _NUM_UNIT.search(span):
        w.append("dose_unit: no numeral+unit/frequency pattern in span")
    if "time_window" in slices and not _TIME.search(span):
        w.append("time_window: no time-window pattern in span")
    if "negation" in slices and not _NEG.search(span):
        w.append("negation: no negation/limitation word in span")
    if "drug_name_zh" in slices:
        if doc["language"] == "en":
            w.append("drug_name_zh: English document")
        elif not re.search(r"[一-鿿]", query):
            w.append("drug_name_zh: query has no Chinese characters")
        elif doc["doc_type"] != "label":
            w.append("drug_name_zh: document is not a label")
    if "protocol_id" in slices and not _ID.search(query):
        w.append("protocol_id: no identifier pattern in query")
    if "protocol_id" not in slices and doc["language"] == "en" and _ID.search(query) and "drug_name_zh" not in slices:
        pass  # identifiers in English-guideline queries are common; the reviewer decides (P3)
    return w


def cli_version(binary: str) -> str:
    out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60)
    return (out.stdout or out.stderr).strip().splitlines()[0]


def run_claude(
    binary: str, model: str, effort: str, system_prompt: str, prompt: str, workdir: pathlib.Path, timeout: int = 1500
) -> tuple[str, dict[str, Any]]:
    """One `claude -p` call with tools off, no session persistence and no user settings (same wire discipline as
    the probe review runner). Returns (reply_text, call_metadata); raises on a non-success reply."""
    cmd = [
        binary,
        "-p",
        "--model",
        model,
        "--effort",
        effort,
        "--tools",
        "",
        "--no-session-persistence",
        "--setting-sources",
        "",
        "--system-prompt",
        system_prompt,
        "--output-format",
        "json",
    ]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=workdir)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"claude returned non-JSON ({proc.returncode}): {(proc.stdout + proc.stderr)[-800:]}"
        ) from exc
    usage = data.get("modelUsage") or {}
    observed = next(iter(usage)) if len(usage) == 1 else None
    ok = proc.returncode == 0 and not data.get("is_error") and data.get("subtype") == "success"
    meta = {
        "cli": "claude-code",
        "model_requested": model,
        "model_observed": observed,
        "reasoning_effort_requested": effort,
        "session_id": data.get("session_id"),
        "input_tokens": sum(int(u.get("inputTokens", 0)) for u in usage.values()),
        "output_tokens": sum(int(u.get("outputTokens", 0)) for u in usage.values()),
        "cost_usd": data.get("total_cost_usd"),
        "system_prompt_sha256": sha256_bytes(system_prompt.encode("utf-8")),
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "tools_disabled": True,
    }
    if not ok:
        raise RuntimeError(f"claude call failed: {json.dumps(data)[:800]}")
    if observed != model:
        raise RuntimeError(f"observed model {observed!r} differs from requested {model!r}")
    return str(data.get("result", "")), meta


def parse_json_array(text: str) -> list[Any]:
    """Extract the first JSON array from a reply (tolerates code fences and surrounding prose)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        v = json.loads(t)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    start = t.find("[")
    if start < 0:
        raise ValueError("no JSON array in reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                v = json.loads(t[start : i + 1])
                if isinstance(v, list):
                    return v
                break
    raise ValueError("unbalanced JSON array in reply")
