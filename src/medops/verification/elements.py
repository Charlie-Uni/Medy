"""Deterministic key-element extraction (M2-07; baseline 5.4 item 2).

Kinds: dose (number + dose unit, ranges kept), frequency (给药频次), time_window (时限/时间窗), identifier
(法规条号、指南编号、章节号、许可证字号、试验注册号), population (人群) and indication (适应证). Each element
carries a `canonical` form that the numeric rules compare (`dose:100:mass` means 100 mg; `freq:3/day`;
`time:48:h`; `id:21 cfr 312.32`; `pop:pediatric`; `ind:<normalized text>`). Overlapping matches are resolved
by a fixed priority so that `一天三次` is a frequency, not a one-day window. Nothing here uses a model.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from medops.domain.common import DomainModel, NonEmptyStr
from medops.domain.verification import ElementKind

EXTRACTOR_VERSION = "elements-rules-v1"


class ExtractedElement(DomainModel):
    kind: ElementKind
    text: NonEmptyStr
    canonical: NonEmptyStr
    start: int = Field(ge=0)
    end: int = Field(gt=0)


# ------------------------------------------------------------------------------------ dose

_NUM = r"\d+(?:[.,]\d+)?"
# (family, factor to the family's base unit). Longer spellings first so the alternation is unambiguous.
_UNITS: tuple[tuple[str, str, float], ...] = (
    ("mg/kg", "mass_per_kg", 1.0),
    ("mcg/kg", "mass_per_kg", 0.001),
    ("µg/kg", "mass_per_kg", 0.001),
    ("μg/kg", "mass_per_kg", 0.001),
    ("mg/m²", "mass_per_m2", 1.0),
    ("mg/m2", "mass_per_m2", 1.0),
    ("mmol/L", "mmol_per_l", 1.0),
    ("mEq/L", "meq_per_l", 1.0),
    ("mcg", "mass", 0.001),
    ("µg", "mass", 0.001),
    ("μg", "mass", 0.001),
    ("ug", "mass", 0.001),
    ("mg", "mass", 1.0),
    ("kg", "mass", 1_000_000.0),
    ("ng", "mass", 0.000001),
    ("g", "mass", 1000.0),
    ("mL", "volume", 1.0),
    ("ml", "volume", 1.0),
    ("dL", "volume", 100.0),
    ("dl", "volume", 100.0),
    ("L", "volume", 1000.0),
    ("IU", "iu", 1.0),
    ("U", "iu", 1.0),
    ("mmol", "mmol", 1.0),
    ("mEq", "meq", 1.0),
    ("%", "percent", 1.0),
    ("毫克", "mass", 1.0),
    ("微克", "mass", 0.001),
    ("公克", "mass", 1000.0),
    ("克", "mass", 1000.0),
    ("毫升", "volume", 1.0),
    ("國際單位", "iu", 1.0),
    ("国际单位", "iu", 1.0),
    ("單位", "iu", 1.0),
    ("单位", "iu", 1.0),
)
_UNIT_BY_TEXT = {u: (fam, f) for u, fam, f in _UNITS}
_UNIT_ALT = "|".join(re.escape(u) for u in (t[0] for t in _UNITS))
_DOSE = re.compile(
    rf"(?P<num>{_NUM})(?:\s*[-–~至到]\s*(?P<num2>{_NUM}))?\s*(?P<unit>{_UNIT_ALT})(?![A-Za-z])(?!/min)",
)

# ------------------------------------------------------------------------------------ frequency

_ZH_DIGITS = {
    "一": 1,
    "二": 2,
    "兩": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_FREQ_ZH = re.compile(r"(?:一|每)(?P<period>天|日|週|周|晚|小時|小时)\s*(?P<n>[一二三四五六七八九十兩两\d]+)\s*次")
_FREQ_ZH_EVERY_H = re.compile(r"每\s*(?P<h>\d+)\s*(?:小時|小时)\s*(?:一次|1次)")
_FREQ_ZH_ONCE = re.compile(r"單次|单次|一次性|頓服|顿服|單一劑量|单一剂量")
_FREQ_EN = re.compile(
    r"\b(?P<abbr>qd|od|bid|bd|tid|tds|qid|qds)\b"
    r"|\bq\s*(?P<qh>\d+)\s*h\b"
    r"|\b(?P<w>once|twice|three times|four times|\d+ times)\s+(?:a|per)\s+(?P<per>day|week)\b"
    r"|\b(?P<w2>once|twice|three times|four times|\d+ times)\s+(?P<daily>daily|weekly)\b"
    r"|\bevery\s+(?P<eh>\d+)\s+hours?\b"
    r"|\b(?P<sd>single dose)\b",
    re.I,
)
_ABBR = {"qd": 1, "od": 1, "bid": 2, "bd": 2, "tid": 3, "tds": 3, "qid": 4, "qds": 4}
_WORDS = {"once": 1, "twice": 2, "three times": 3, "four times": 4}

# ------------------------------------------------------------------------------------ time window

_TIME_UNITS_ZH = {
    "分鐘": "min", "分钟": "min", "小時": "h", "小时": "h", "天": "d", "日": "d", "工作日": "wd", "個工作天": "wd",
    "个工作日": "wd", "周": "wk", "週": "wk", "星期": "wk", "個月": "mo", "个月": "mo", "月": "mo", "年": "yr",
}  # fmt: skip
_TIME_ZH = re.compile(
    r"(?P<n>\d+|[一二三四五六七八九十兩两]+)\s*(?P<u>分鐘|分钟|小時|小时|個工作天|个工作日|工作日|天|日|星期|週|周|個月|个月|月|年)"
    r"(?:之?(?:内|內|以内|以內|後|后|之後|之后|前))?"
)
_TIME_EN = re.compile(
    r"(?:\bwithin\s+|\bno later than\s+|\bat least\s+|\bafter\s+|\bfor\s+|±\s*)?"
    r"(?P<n>\d+)\s*(?:-\s*)?(?P<q>calendar\s+|working\s+|business\s+)?(?P<u>minutes?|hours?|days?|weeks?|months?|years?)\b",
    re.I,
)
_TIME_EN_UNIT = {"minute": "min", "hour": "h", "day": "d", "week": "wk", "month": "mo", "year": "yr"}

# ------------------------------------------------------------------------------------ identifiers

_IDENT = re.compile(
    r"21\s*CFR\s*(?:Part\s*)?\d+(?:\.\d+)?(?:\([a-z0-9]+\))*"
    r"|\bICH\s*[EMQS]\d{1,2}[A-Z]?(?:\s*\(R\d\))?"
    r"|\b[EMQS]\d{1,2}[A-Z]?\(R\d\)"
    r"|\bGVP\s*(?:Module|模块|模組)\s*[IVX]+(?:\s*Addendum\s*[IVX]+)?"
    r"|\bArticle\s*\d+(?:\(\d+\))?(?:\([a-z]\))?"
    r"|\bArt\.?\s*\d+(?:\(\d+\))?(?:\([a-z]\))?"
    r"|\bSection\s*\d+(?:\.\d+)*"
    r"|第\s*\d+(?:\.\d+)*\s*[条條节節章項项款]"
    r"|\bNCT\d{8}\b"
    r"|\bEudraCT\s*\d{4}-\d{6}-\d{2}"
    r"|\bRev\.?\s*\d+\b"
    r"|[衛卫]署[藥药][製制輸输]字第\s*\d+\s*號"
    r"|\bSOP[-\s]?[A-Z0-9][A-Z0-9-]{2,}"
    r"|\b\d+\.\d+\.\d+(?:\.\d+)*\b",
    re.I,
)

# ------------------------------------------------------------------------------------ population / indication

_POP: tuple[tuple[str, str], ...] = (
    (r"新生兒|新生儿|neonat\w*|newborn", "neonate"),
    (r"早產|早产|preterm|premature", "preterm"),
    (r"嬰兒|婴儿|infants?", "infant"),
    (r"兒童|儿童|小兒|小儿|孩童|小孩|p(?:a)?ediatric|children|child\b", "pediatric"),
    (r"青少年|adolescents?", "adolescent"),
    (r"老年|老人|高齡|高龄|elderly|geriatric|older (?:patients|adults|people)", "elderly"),
    (r"孕婦|孕妇|妊娠|懷孕|怀孕|pregnan\w*", "pregnant"),
    (r"哺乳|授乳|breast-?feeding|lactating|lactation", "lactating"),
    (r"腎功能不全|肾功能不全|腎功能損害|肾功能损害|renal impairment|renal insufficiency", "renal_impairment"),
    (r"肝功能不全|肝功能損害|肝功能损害|hepatic impairment|hepatic insufficiency", "hepatic_impairment"),
    (r"透析|dialysis", "dialysis"),
)
_POP_RE = [(re.compile(p, re.I), tag) for p, tag in _POP]
_IND = re.compile(
    r"(?:適應症|适应症)\s*[:：]?\s*(?P<zh>[^，,。；;.\n]{2,40})"
    r"|(?<![禁適适使])(?:用於治療|用于治疗|用於|用于|適用於|适用于)\s*(?P<zh2>[^，,。；;.\n]{2,40})"
    r"|(?:indicated for|for the treatment of|treatment of)\s+(?P<en>[^,.;\n]{3,60})",
    re.I,
)

_PRIORITY = {
    ElementKind.frequency: 0,
    ElementKind.identifier: 1,
    ElementKind.dose: 2,
    ElementKind.time_window: 3,
    ElementKind.population: 4,
    ElementKind.indication: 5,
}


_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")


def _num(text: str) -> float:
    """`1,500` is a thousands separator, `0,5` a decimal comma (both occur in the corpus)."""
    if _THOUSANDS.fullmatch(text):
        return float(text.replace(",", ""))
    return float(text.replace(",", "."))


def _fmt(value: float) -> str:
    return f"{value:.6g}"


def _zh_int(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    total = 0
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        total = (_ZH_DIGITS[left] if left else 1) * 10 + (_ZH_DIGITS[right] if right else 0)
        return total
    if all(ch in _ZH_DIGITS for ch in text):
        return sum(_ZH_DIGITS[ch] for ch in text) if len(text) == 1 else None
    return None


def _candidates(text: str) -> Iterable[ExtractedElement]:
    for m in _DOSE.finditer(text):
        fam, factor = _UNIT_BY_TEXT[m.group("unit")]
        v1 = _num(m.group("num")) * factor
        canonical = f"dose:{_fmt(v1)}:{fam}"
        if m.group("num2"):
            canonical = f"dose:{_fmt(v1)}-{_fmt(_num(m.group('num2')) * factor)}:{fam}"
        yield ExtractedElement(
            kind=ElementKind.dose, text=m.group(0), canonical=canonical, start=m.start(), end=m.end()
        )
    for m in _FREQ_ZH.finditer(text):
        n = _zh_int(m.group("n"))
        if n is None:
            continue
        per = {"天": "day", "日": "day", "晚": "day", "週": "week", "周": "week", "小時": "hour", "小时": "hour"}[
            m.group("period")
        ]
        yield ExtractedElement(
            kind=ElementKind.frequency, text=m.group(0), canonical=f"freq:{n}/{per}", start=m.start(), end=m.end()
        )
    for m in _FREQ_ZH_EVERY_H.finditer(text):
        h = int(m.group("h"))
        if h > 0:
            yield ExtractedElement(
                kind=ElementKind.frequency,
                text=m.group(0),
                canonical=f"freq:{_fmt(24 / h)}/day",
                start=m.start(),
                end=m.end(),
            )
    for m in _FREQ_ZH_ONCE.finditer(text):
        yield ExtractedElement(
            kind=ElementKind.frequency, text=m.group(0), canonical="freq:once", start=m.start(), end=m.end()
        )
    for m in _FREQ_EN.finditer(text):
        freq_canonical = _en_freq(m)
        if freq_canonical:
            yield ExtractedElement(
                kind=ElementKind.frequency, text=m.group(0), canonical=freq_canonical, start=m.start(), end=m.end()
            )
    for m in _IDENT.finditer(text):
        yield ExtractedElement(
            kind=ElementKind.identifier,
            text=m.group(0),
            canonical="id:" + _norm_id(m.group(0)),
            start=m.start(),
            end=m.end(),
        )
    for m in _TIME_ZH.finditer(text):
        n = _zh_int(m.group("n"))
        if n is None:
            continue
        yield ExtractedElement(
            kind=ElementKind.time_window,
            text=m.group(0),
            canonical=f"time:{n}:{_TIME_UNITS_ZH[m.group('u')]}",
            start=m.start(),
            end=m.end(),
        )
    for m in _TIME_EN.finditer(text):
        unit = _TIME_EN_UNIT[m.group("u").lower().rstrip("s")]
        if (m.group("q") or "").strip().lower() in ("working", "business") and unit == "d":
            unit = "wd"
        yield ExtractedElement(
            kind=ElementKind.time_window,
            text=m.group(0),
            canonical=f"time:{int(m.group('n'))}:{unit}",
            start=m.start(),
            end=m.end(),
        )
    for rx, tag in _POP_RE:
        for m in rx.finditer(text):
            yield ExtractedElement(
                kind=ElementKind.population, text=m.group(0), canonical=f"pop:{tag}", start=m.start(), end=m.end()
            )
    for m in _IND.finditer(text):
        body = m.group("zh") or m.group("zh2") or m.group("en") or ""
        body = body.strip()
        if len(body) >= 2:
            yield ExtractedElement(
                kind=ElementKind.indication,
                text=m.group(0),
                canonical="ind:" + normalize_for_match(body),
                start=m.start(),
                end=m.end(),
            )


def _en_freq(m: re.Match[str]) -> str | None:
    if m.group("abbr"):
        return f"freq:{_ABBR[m.group('abbr').lower()]}/day"
    if m.group("qh"):
        h = int(m.group("qh"))
        return f"freq:{_fmt(24 / h)}/day" if h else None
    if m.group("eh"):
        h = int(m.group("eh"))
        return f"freq:{_fmt(24 / h)}/day" if h else None
    if m.group("sd"):
        return "freq:once"
    word = (m.group("w") or m.group("w2") or "").lower()
    n = _WORDS.get(word)
    if n is None:
        digits = re.match(r"(\d+) times", word)
        n = int(digits.group(1)) if digits else None
    if n is None:
        return None
    per = "week" if (m.group("per") or m.group("daily") or "").lower().startswith("week") else "day"
    return f"freq:{n}/{per}"


def _norm_id(text: str) -> str:
    t = text.replace("（", "(").replace("）", ")").replace("　", " ")
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = re.sub(r"\s*\(\s*", "(", t)
    t = re.sub(r"\s*\)\s*", ")", t)
    t = re.sub(r"^art\.? ", "article ", t)
    return t


def normalize_for_match(text: str) -> str:
    """Case-folded, whitespace-free, punctuation-light form for containment checks (not norm-v1)."""
    t = text.lower()
    t = re.sub(r"[\s，,。．.、；;：:（）()\[\]「」『』“”\"'‘’!！?？]", "", t)
    return t


def extract(text: str) -> tuple[ExtractedElement, ...]:
    """All non-overlapping key elements in `text`, highest priority first on overlap, then by position."""
    ranked = sorted(_candidates(text), key=lambda e: (_PRIORITY[e.kind], e.start, -(e.end - e.start)))
    kept: list[ExtractedElement] = []
    for cand in ranked:
        if any(cand.start < k.end and k.start < cand.end for k in kept):
            continue
        kept.append(cand)
    return tuple(sorted(kept, key=lambda e: e.start))
