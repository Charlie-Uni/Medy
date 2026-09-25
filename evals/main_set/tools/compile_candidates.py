"""Compile a DEC-011 candidate list from seeds (M5-01, record 89).

For every seed (see `seed_candidates_v12.py`) the tool downloads the PDF, records sha256 / byte size / page count /
text-layer size, stages the file under `evals/main_set/sources_staging/<sha256>.pdf` (gitignored), scans the text for
copyright / confidentiality markers, extracts the in-document licence statement where the publisher prints one (ICH
legal notice, EMA cover ©), and — for TFDA labels — proves ADR-0003 decision-1 conditions (1) and (2) against the
same-day open-data snapshots (pdf_url appears verbatim in dataset 39; currency fields from dataset 36). It then fills
the per-source licence evidence, pre-judges the four-level status (`eligible` only when every mechanical check passes,
otherwise `needs_review`), validates against `candidate.schema.json`, appends the new candidates to the base list and
writes the sign-off sheet in batches of 50. Nothing here replaces the decision-maker's signature
(`reviewer_decision` stays null).

Usage:
  python evals/main_set/tools/compile_candidates.py --seeds seeds.jsonl \
      --base evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.1.json \
      --out  evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.2.json \
      --sheet evals/probe/precise_clause/corpus_candidates/DEC-011-candidates-v1.2.md \
      --tfda-39-zip 39.zip --tfda-39 39_2.csv --tfda-36-zip 36.zip --tfda-36 36_2.csv \
      --version v1.2 --today 2026-09-26 --cap tfda_label=66 --dropped dropped.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema
from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[3]
SCHEMA = REPO / "evals/main_set/schema/candidate.schema.json"
UA = "Mozilla/5.0 (Macintosh) MedOps-corpus-candidates/1.2 (+ADR-0003)"

ICH_LEGAL = (
    "The information, material and photographic content provided on this website are protected by copyright and may, "
    "with the exception of the ICH logo, be used, reproduced, incorporated into other works, adapted, modified, translated "
    "or distributed under a public license provided that ICH's copyright in the information and material is acknowledged "
    "at all times. […] The above-mentioned permissions do not apply to content supplied by third parties. Therefore, for "
    "documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder."
)
EMA_LEGAL = (
    "Information and documents made available on EMA's webpages are public and may be reproduced and / or distributed, "
    "totally or in part, irrespective of the means and / or the formats used, for non-commercial and commercial purposes, "
    "provided that EMA is always acknowledged as the source of the material. […] The above-mentioned permissions do not "
    "apply to content supplied by third parties. Therefore, for documents where the copyright vests in a third party, "
    "permission for reproduction must be obtained from this copyright holder."
)
FDA_PUBLIC_DOMAIN = (
    "Unless otherwise noted, the contents of the FDA website (www.fda.gov) — both text and graphics — are not copyrighted. "
    "They are in the public domain and may be republished, reprinted and otherwise used freely by anyone without the need "
    "to obtain permission from FDA. […] Credit to the U.S. Food and Drug Administration as the source is appreciated but not required."
)
TFDA_OPEN = (
    "衛生福利部食品藥物管理署網站上刊載之所有資料與素材，其得受著作權保護之範圍，採 政府資料開放授權條款-第1版 發布，以無償、非專屬、"
    "得由使用者再授權之方式提供公眾使用，使用者得不限時間及地域，重製、改作、編輯、公開傳輸或為其他方式之利用，開發各種產品或服務"
    "（簡稱加值衍生物），此一授權行為不會嗣後撤回，使用者亦無須取得本機關之書面或其他方式授權；然使用時應註明出處。 || "
    "(一)本授權範圍僅及於著作權保護之範圍，不及於其他智慧財產權利，包括但不限於專利、商標、及機關標誌之提供。"
)
TFDA_COPYRIGHT = (
    "本署網站上所刊載以本署名義公開發表之著作，在合理範圍內，得重製、公開播送或公開傳輸；利用時，並請註明出處。"
)
MCP_FOOTER = (
    "本網站所刊出內容之著作權屬於衛生福利部食品藥物管理署所有，未經本署之同意或授權，任何人不得以任何形式重製、轉載、散佈、引用、"
    "變更、播送或出版該內容之全部或局部，亦不得為其他任何違反本署著作權之行為。"
)
DATASET_9117 = (
    "授權方式 政府資料開放授權條款-第1版 || 主要欄位說明 … 許可證字號、中文品名、英文品名、仿單圖檔連結、外盒圖檔連結"
)
OGDL = (
    "各機關所提供之開放資料，授權使用者不限目的、時間及地域、非專屬、不可撤回、免授權金進行利用，利用之方式包括重製、散布、公開傳輸、"
    "公開播送、公開口述、公開上映、公開演出、編輯、改作，包括但不限於開發各種產品或服務型態之衍生物。 || 本條款與「創用CC授權 姓名標示 4.0 國際版本」相容"
)

# Markers that would defeat the source licence. "confidential" and "not for distribution" only count when written as a
# document marker (upper case, or the fixed phrases); the ordinary regulatory use of the words ("keep passwords
# confidential", "labeling not for distribution to patients") is not a restriction on the document itself.
RESTRICTION_PATTERNS = [
    ("all rights reserved", re.compile(r"all rights reserved", re.I)),
    ("confidential", re.compile(r"\bCONFIDENTIAL\b")),  # case-sensitive: the document marker, not the word
    (
        "confidential",
        re.compile(
            r"strictly confidential|confidential and proprietary|proprietary and confidential|commercial(?:ly)? in confidence|confidential\s*[–—-]+\s*(?:do not|not for)",
            re.I,
        ),
    ),
    (
        "not for distribution",
        re.compile(r"not for (?:further |public |external )?distribution(?!\s+(?:to|with|in|by)\b)", re.I),
    ),
    ("reproduced with permission", re.compile(r"reproduced (?:with|by) permission", re.I)),
    ("版權所有", re.compile(r"版權所有|版权所有")),
    ("未經同意不得", re.compile(r"未經.{0,12}?(?:同意|授權).{0,12}?不得|未经.{0,12}?(?:同意|授权).{0,12}?不得")),
    ("禁止轉載", re.compile(r"禁止.{0,6}?(?:轉載|重製|複製|转载|复制)")),
    ("©", re.compile(r"©|\(c\)\s*(?:19|20)\d\d", re.I)),
]
HARD_RESTRICTIONS = {
    "all rights reserved",
    "confidential",
    "not for distribution",
    "reproduced with permission",
    "版權所有",
    "未經同意不得",
    "禁止轉載",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, tries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:  # noqa: PERF203
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def pdf_facts(data: bytes) -> dict:
    reader = PdfReader(io.BytesIO(data))
    texts: list[str] = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a broken page must not sink the document
            texts.append("")
    meta = reader.metadata or {}

    def date(key: str) -> str | None:
        raw = meta.get(key)
        if not raw:
            return None
        m = re.search(r"(\d{4})(\d{2})(\d{2})", str(raw))
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else str(raw)[:20]

    full = "\n".join(texts)
    return {
        "pages": len(reader.pages),
        "chars": sum(len(t.strip()) for t in texts),
        "head": re.sub(r"\s+", " ", " ".join(texts[:3])),
        "full": full,
        "tail": re.sub(r"\s+", " ", " ".join(texts[-2:])),
        "created": date("/CreationDate"),
        "modified": date("/ModDate"),
    }


def scan_restrictions(full: str) -> list[tuple[str, str]]:
    flat = re.sub(r"\s+", " ", full)
    hits = []
    for name, pat in RESTRICTION_PATTERNS:
        m = pat.search(flat)
        if m:
            s = max(0, m.start() - 50)
            hits.append((name, flat[s : m.end() + 60].strip()))
    return hits


def ema_cover_quote(head: str) -> str | None:
    m = re.search(
        r"©\s*European Medicines Agency[^©]{0,120}?(?:19|20)\d\d\.?\s*Reproduction is authorised provided the source is acknowledged\.?",
        head,
    )
    if m:
        return m.group(0).strip()
    m = re.search(r".{0,120}Reproduction is authorised provided the source is acknowledged\.?", head)
    return m.group(0).strip() if m else None


def ich_notice_quote(head: str) -> str | None:
    m = re.search(r"This document is protected by copyright.{0,900}?copyright holder\.", head)
    if m:
        return m.group(0).strip()
    m = re.search(r"protected by copyright.{0,600}?(?:acknowledged at all times\.|copyright holder\.)", head)
    return ("[…] " + m.group(0).strip()) if m else None


def ema_version(head: str) -> str | None:
    ref = re.search(
        r"\b(?:EMA|EMEA|CPMP|CHMP|PRAC|HMA|EMA/HMA)[A-Za-z/]*\d{2,7}/\d{4}(?:\s*(?:Rev\.?|Corr\.?)\s*\d*)*", head
    )
    date = re.search(
        r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b",
        head,
    )
    if ref and date:
        return f"{ref.group(0).strip()} ({date.group(0)})"
    if ref:
        return ref.group(0).strip()
    return date.group(0) if date else None


def ich_dated(head: str) -> str | None:
    m = re.search(r"(?:Current Step 4 version|Step 4 version|dated)\s+(\d{1,2} \w+ \d{4})", head)
    return m.group(1) if m else None


def tw_date(head: str) -> str | None:
    m = re.search(r"(?:中華民國)?\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?", head)
    if not m:
        return None
    y = int(m.group(1)) + 1911
    return f"{y}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")


def label_version(facts: dict) -> str:
    text = facts["tail"] + " " + facts["head"]
    m = re.search(
        r"(?:版本|Rev(?:ision)?\.?|修訂日期|修訂|Revised|Date of revision|更新日期)[:：]?\s*([A-Za-z0-9./年月日-]{4,24})",
        text,
    )
    return f"文内版本行：{m.group(0).strip()[:40]}" if m else "仿單正文未见版本行"


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


class Compiler:
    def __init__(self, a: argparse.Namespace) -> None:
        self.a = a
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.staging = a.staging
        self.staging.mkdir(parents=True, exist_ok=True)
        self.today = a.today
        self.snap = self._load_snapshots() if a.tfda_39 else None
        import threading

        self.lock = threading.Lock()
        index = self.staging / "_url_index.json"
        self.url_index: dict[str, str] = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        self.dropped: list[dict] = []

    # ---------- snapshots ----------
    def _load_snapshots(self) -> dict:
        a = self.a
        with a.tfda_39.open(encoding="utf-8-sig", newline="") as f:
            labels = {r["許可證字號"]: r for r in csv.DictReader(f)}
        with a.tfda_36.open(encoding="utf-8-sig", newline="") as f:
            lic = {r["許可證字號"]: r for r in csv.DictReader(f)}
        return {
            "labels": labels,
            "lic": lic,
            "zip39": sha256(a.tfda_39_zip.read_bytes()) if a.tfda_39_zip else None,
            "csv39": sha256(a.tfda_39.read_bytes()),
            "csv39_name": a.tfda_39.name,
            "zip36": sha256(a.tfda_36_zip.read_bytes()) if a.tfda_36_zip else None,
            "csv36": sha256(a.tfda_36.read_bytes()),
            "csv36_name": a.tfda_36.name,
        }

    # ---------- evidence ----------
    def evidence(self, seed: dict, facts: dict) -> tuple[list[dict], dict]:
        g = seed["group"]
        t = self.today
        extra: dict = {}
        if g == "ich":
            ev = [
                {
                    "url": "https://www.ich.org/page/legal-mentions",
                    "locator": f"Legal Mentions（页面客户端渲染；文本经站点 JSON 接口 admin.ich.org/api/v1/nodes?alias=/page/legal-mentions 取得；{t} 主会话复核节点未更新（updated 2019-07-17），引文沿用 2026-09-09 抓取文本）",
                    "quote": ICH_LEGAL,
                }
            ]
            q = ich_notice_quote(facts["head"])
            extra["in_text_notice"] = bool(q)
            if q:
                ev.append(
                    {
                        "url": seed["pdf_url"],
                        "locator": f"PDF 前页 Legal notice（{t} pypdf 抽取）",
                        "quote": clip(q, 2000),
                    }
                )
            return ev, extra
        if g == "ema":
            ev = [
                {
                    "url": "https://www.ema.europa.eu/en/about-us/about-website/legal-notice",
                    "locator": f"Legal notice（{t} 主会话 curl 复核一致）",
                    "quote": EMA_LEGAL,
                }
            ]
            q = ema_cover_quote(facts["head"])
            extra["cover_notice"] = bool(q)
            if q:
                ev.append(
                    {
                        "url": seed["pdf_url"],
                        "locator": f"PDF 第 1 页版权声明（{t} pypdf 抽取）",
                        "quote": clip(q, 2000),
                    }
                )
            return ev, extra
        if g == "fda":
            return [
                {
                    "url": "https://www.fda.gov/about-fda/about-website/website-policies",
                    "locator": f"Website Policies: Copyright（{t} 主会话 WebFetch 复核一致）",
                    "quote": FDA_PUBLIC_DOMAIN,
                }
            ], extra
        if g == "tfda_site":
            return [
                {
                    "url": "https://www.fda.gov.tw/TC/opendata.aspx",
                    "locator": f"網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（{t} 主会话 curl 复核一致）",
                    "quote": TFDA_OPEN,
                },
                {
                    "url": "https://www.fda.gov.tw/TC/copyright.aspx",
                    "locator": f"著作權聲明（{t} 主会话 curl 复核一致）",
                    "quote": TFDA_COPYRIGHT,
                },
            ], extra
        if g == "tfda_label":
            s = self.snap
            assert s is not None, "TFDA snapshots are required for label seeds"
            row = s["labels"].get(seed["lic"], {})
            lic = s["lic"].get(seed["lic"], {})
            link = row.get("仿單圖檔連結", "")
            extra["cond1"] = link == seed["pdf_url"]
            extra["snapshot_link"] = link
            extra["lic_row"] = {
                k: lic.get(k, "")
                for k in ("許可證字號", "註銷狀態", "有效日期", "發證日期", "申請商名稱", "製造商名稱")
            }
            extra["active"] = (not lic.get("註銷狀態")) and lic.get("有效日期", "") > t.replace("-", "/")
            ev = [
                {
                    "url": "https://mcp.fda.gov.tw/im",
                    "locator": f"平台页脚（{t} 主会话 curl 复核一致）",
                    "quote": MCP_FOOTER,
                },
                {
                    "url": "https://data.gov.tw/dataset/9117",
                    "locator": f"数据集元数据（授權方式、主要欄位說明；{t} 主会话 WebFetch 复核关键字段一致）",
                    "quote": DATASET_9117,
                },
                {
                    "url": "https://data.gov.tw/license",
                    "locator": f"政府資料開放授權條款-第1版 §二(一)、§四(二)（{t} 主会话 curl 复核一致）",
                    "quote": OGDL,
                },
                {
                    "url": "https://www.fda.gov.tw/TC/opendata.aspx",
                    "locator": f"網站資料開放宣告 一、授權方式及範圍；二、相關事項說明(一)（{t} 主会话 curl 复核一致）",
                    "quote": TFDA_OPEN,
                },
                {
                    "url": "https://www.fda.gov.tw/TC/copyright.aspx",
                    "locator": f"著作權聲明（{t} 主会话 curl 复核一致）",
                    "quote": TFDA_COPYRIGHT,
                },
                {
                    "url": "https://data.fda.gov.tw/data/opendata/export/39/csv",
                    "locator": clip(
                        f"资料集 39（仿單）CSV 快照 {t} 下载：zip sha256 {s['zip39']}，内层 {s['csv39_name']} sha256 {s['csv39']}，{len(s['labels'])} 条；許可證字號 {seed['lic']} 的 仿單圖檔連結 与本条 pdf_url "
                        + (
                            "逐字相等（机械核对通过，ADR-0003 决策 1 条件 (1)(2)）"
                            if extra["cond1"]
                            else "不相等（条件 (1) 不成立）"
                        ),
                        300,
                    ),
                    "quote": link or "（快照中无该許可證字號）",
                },
                {
                    "url": "https://data.fda.gov.tw/data/opendata/export/36/csv",
                    "locator": clip(
                        f"資料集 36（全部藥品許可證）CSV 快照 {t} 下载：zip sha256 {s['zip36']}，内层 {s['csv36_name']} sha256 {s['csv36']}，{len(s['lic'])} 条；許可證字號 {seed['lic']} 的现行性字段",
                        300,
                    ),
                    "quote": json.dumps(extra["lic_row"], ensure_ascii=False),
                },
            ]
            return ev, extra
        raise ValueError(g)

    # ---------- one seed ----------
    def _load(self, url: str) -> bytes:
        """Download once per URL; re-runs read the staged copy recorded in `_url_index.json`."""
        with self.lock:
            digest = self.url_index.get(url)
        if digest and (self.staging / f"{digest}.pdf").exists():
            return (self.staging / f"{digest}.pdf").read_bytes()
        data = fetch(url)
        if data.startswith(b"%PDF"):
            digest = sha256(data)
            path = self.staging / f"{digest}.pdf"
            if not path.exists():
                path.write_bytes(data)
            with self.lock:
                self.url_index[url] = digest
        return data

    def build(self, idx: int, seed: dict) -> tuple[int, dict | None, dict | None]:
        try:
            data = self._load(seed["pdf_url"])
        except RuntimeError as exc:
            return idx, None, {"seed": seed, "why": str(exc)}
        if not data.startswith(b"%PDF"):
            return idx, None, {"seed": seed, "why": f"not a PDF (starts with {data[:12]!r})"}
        digest = sha256(data)
        try:
            facts = pdf_facts(data)
        except Exception as exc:  # noqa: BLE001
            return idx, None, {"seed": seed, "why": f"pypdf failed: {exc}"}
        if facts["chars"] < 300:  # image-only scan: ADR-0003 practice is no OCR, so it cannot enter the corpus
            return (
                idx,
                None,
                {
                    "seed": seed,
                    "why": f"无文本层（扫描件，{facts['pages']} 页 / {facts['chars']} 字符），不做 OCR",
                    "sha256": digest,
                },
            )
        hits = scan_restrictions(facts["full"])
        ev, extra = self.evidence(seed, facts)
        g = seed["group"]
        problems: list[str] = []
        hard = [h for h in hits if h[0] in HARD_RESTRICTIONS]
        soft = [h for h in hits if h[0] not in HARD_RESTRICTIONS]
        if g == "tfda_label":
            if not extra["cond1"]:
                problems.append("条件 (1) 不成立：快照字段与 pdf_url 不一致")
            if not extra["active"]:
                problems.append("許可證非现行")
            if hard or soft:
                problems.append(
                    "文本层命中版权/限制标记：" + "；".join(f"{n}「{c[:60]}」" for n, c in (hard + soft)[:2])
                )
        elif g in ("ema", "ich"):
            if hard:
                problems.append("文本层命中限制标记：" + "；".join(f"{n}「{c[:60]}」" for n, c in hard[:2]))
        else:  # fda / tfda_site
            if hard or soft:
                problems.append(
                    "文本层命中版权/限制标记：" + "；".join(f"{n}「{c[:60]}」" for n, c in (hard + soft)[:2])
                )
        status = "eligible" if not problems else "needs_review"
        # version
        ver = seed.get("version_or_date")
        if g == "ema":
            ver = ver or ema_version(facts["head"]) or "以 PDF 首页为准（未识别 EMA 文号）"
        elif g == "ich":
            d = ich_dated(facts["head"])
            ver = f"{ver}（文内 dated {d}）" if d and d not in ver else ver
        elif g == "tfda_site":
            d = tw_date(facts["head"])
            ver = f"{ver}；PDF 首页日期 {d}" if d else ver
        elif g == "tfda_label":
            lic_row = extra["lic_row"]
            ver = (
                f"{label_version(facts)}；PDF 元数据 CreationDate {facts['created'] or '无'}；許可證 {seed['lic']} "
                + ("现行" if extra["active"] else "非现行")
                + f"（有效日期 {lic_row.get('有效日期', '')}）"
            )
        ver = clip(ver or "以 PDF 为准", 120)
        # narrative fields
        dept = seed["owner_dept"]
        pages, chars = facts["pages"], facts["chars"]
        hit_note = "无" if not (hard or soft) else "；".join(n for n, _ in (hard + soft)[:3])
        if g == "ich":
            tpn = "ICH 指南正文；引用其他 ICH 指南与文献仅为引文；Legal Mentions 排除 ICH 徽标与第三方内容（渲染时排除徽标）。"
            reasoning = f"ICH 公共许可（与已签字的 E2A/E2F/E6(R3)/E8(R1) 同一依据）；文内 Legal notice {'有' if extra['in_text_notice'] else '无（同 E2A/E2F）'}；{dept} 部门检索需求；{pages} 页 / {chars} 字符文本层。"
            basis = "ICH Legal Mentions" + ("+文内公告" if extra["in_text_notice"] else "（无文内公告，同 E2A/E2F）")
        elif g == "ema":
            tpn = "EMA/HMA 自有文件；MedDRA/ICH/CIOMS 等仅为引用；Legal notice 排除第三方内容与标志（渲染时排除）。"
            reasoning = f"EMA Legal Notice 允许商业与非商业复制并要求署名（与已签字的 GVP 模块同一依据）；封面 © 声明{'有' if extra['cover_notice'] else '无（以 Legal Notice 为准）'}；{dept} 部门检索需求；{pages} 页 / {chars} 字符文本层。"
            basis = "EMA Legal Notice" + (" + 封面 © 声明" if extra["cover_notice"] else "")
        elif g == "fda":
            tpn = "美国联邦政府作品，fda.gov 公共领域声明覆盖文本与图形；文中引用的第三方文献仅为引文。"
            draft = "草案" in seed.get("version_or_date", "") or "Draft" in seed.get("version_or_date", "")
            reasoning = f"fda.gov 公共领域声明（与已签字的 FDA 指南同一依据）；{'草案指南（非最终稿），入库后 version_label 标注 Draft' if draft else '最终指南'}；{dept} 部门检索需求；{pages} 页 / {chars} 字符文本层。"
            basis = "fda.gov 公共领域政策"
        elif g == "tfda_site":
            tpn = "TFDA 以本署名義公開發表之著作；引用 ICH/WHO 等仅为引文；開放宣告排除商標與機關標誌。"
            reasoning = f"TFDA 網站資料開放宣告（政府資料開放授權條款第 1 版）与著作權聲明（与已签字的 cand-0014 同一依据）；文件无「另需同意」标记；{dept} 部门检索需求；{pages} 页 / {chars} 字符文本层。"
            basis = "TFDA 網站資料開放宣告 + 著作權聲明"
        else:
            mah = seed.get("lic_row", {}).get("申請商名稱", "")
            tpn = f"仿單正文由 MAH 撰写（{mah}），含產品名稱商標；OGDL 與 fda.gov.tw 開放宣告均不及於商標與機關標誌。文本层版权标记扫描：{hit_note}。图像层目视（ADR-0003 条件 (3)）待决策人批准后逐页执行。"
            reasoning = f"資料集 9117/39 OGDL-1.0 依据与已签字的 cand-0034/0037/0038 完全相同；条件 (1)(2) {'已机械证明' if extra['cond1'] else '未通过'}，(3) 文本层{'无限制声明' if not (hard or soft) else '命中标记待核'}、图像层待核，(4) 入库时落实；MA 部门繁体仿單需求，{seed.get('inn', '')} 单一成分，{pages} 页 / {chars} 字符文本层。"
            basis = "資料集 9117/39 OGDL-1.0（条件 1/2 机械证明；3 图像层待核）"
        if problems:
            reasoning += " 预判 needs_review：" + "；".join(problems) + "。"
        notes = f"{seed.get('notes', '')}；页数：{pages}；{self.today} 下载 sha256 {digest}，{len(data)} 字节，文本层 {chars} 字符"
        if g == "ich":
            notes += f"；文内 Legal notice: {'有' if extra['in_text_notice'] else '无'}"
        notes += "。M5-01 扩语料候选（记录 89）。"
        cand = {
            "candidate_id": "",
            "title": clip(seed["title"], 300),
            "publisher": clip(seed["publisher"], 200),
            "language": seed["language"],
            "doc_type": seed["doc_type"],
            "owner_dept": dept,
            "landing_url": seed["landing_url"],
            "pdf_url": seed["pdf_url"],
            "version_or_date": ver,
            "registry_id": seed.get("registry_id"),
            "license_status": status,
            "license_evidence": ev,
            "third_party_note": clip(tpn, 500),
            "reasoning": clip(reasoning, 800),
            "fetch_verified": True,
            "fetched_at": self.today,
            "reviewer_decision": None,
            "reviewer_note": None,
            "notes": clip(notes, 500),
        }
        cand["_group"] = g
        cand["_pages"] = pages
        cand["_basis"] = basis
        cand["_problems"] = problems
        return idx, cand, None

    # ---------- run ----------
    def run(self) -> None:
        a = self.a
        seeds = [json.loads(line) for line in a.seeds.read_text(encoding="utf-8").splitlines() if line.strip()]
        base = json.loads(a.base.read_text(encoding="utf-8"))
        known = {c["pdf_url"] for c in base["candidates"]}
        dropped: list[dict] = []
        todo = []
        for s in seeds:
            if s["pdf_url"] in known:
                dropped.append({"seed": s, "why": "already in base list"})
            else:
                todo.append(s)
        # Labels are tried per active ingredient: rank 1 first, the next rank only when the earlier one fell out
        # (scan, download failure) or was pre-judged needs_review; one label per INN reaches the list.
        plain = [s for s in todo if s["group"] != "tfda_label"]
        by_inn: dict[str, list[dict]] = {}
        for s in todo:
            if s["group"] == "tfda_label":
                by_inn.setdefault(s["inn"], []).append(s)
        for rows in by_inn.values():
            rows.sort(key=lambda s: s.get("rank", 1))
        built: dict[int, dict] = {}
        done = 0

        def report(ok: bool, s: dict) -> None:
            nonlocal done
            done += 1
            print(f"[{done:4d}] {'ok ' if ok else 'DROP'} {s['group']:10s} {s['title'][:70]}", file=sys.stderr)

        def try_inn(rows: list[dict]) -> tuple[dict | None, list[dict]]:
            fallback: dict | None = None
            drops: list[dict] = []
            for s in rows:
                _, cand, err = self.build(0, s)
                report(cand is not None, s)
                if err:
                    drops.append(err)
                    continue
                if cand["license_status"] == "eligible":
                    if fallback is not None:
                        drops.append(
                            {
                                "seed": fallback["_seed"],
                                "why": "needs_review; a later-rank label of the same INN is eligible",
                            }
                        )
                    return cand, drops
                cand["_seed"] = s
                if fallback is None:
                    fallback = cand
                else:
                    drops.append(
                        {"seed": s, "why": "needs_review; an earlier-rank label of the same INN is already listed"}
                    )
            return fallback, drops

        with ThreadPoolExecutor(max_workers=a.jobs) as pool:
            for idx, cand, err in pool.map(lambda p: self.build(*p), list(enumerate(plain))):
                report(cand is not None, plain[idx])
                if err:
                    dropped.append(err)
                else:
                    built[idx] = cand
            label_results = list(pool.map(try_inn, list(by_inn.values())))
        kept: list[dict] = [built[i] for i in sorted(built)]
        caps = dict(kv.split("=") for kv in a.cap)
        cap = int(caps.get("tfda_label", 10**9))
        eligible_labels = 0
        for (cand, drops), rows in zip(label_results, by_inn.values(), strict=True):
            dropped.extend(drops)
            if cand is None:
                continue
            if eligible_labels >= cap:
                dropped.append(
                    {
                        "seed": cand.pop("_seed", rows[0]),
                        "why": f"beyond cap tfda_label={cap} (eligible already reached)",
                    }
                )
                continue
            cand.pop("_seed", None)
            kept.append(cand)
            if cand["license_status"] == "eligible":
                eligible_labels += 1
        self.dropped = dropped
        (self.staging / "_url_index.json").write_text(
            json.dumps(self.url_index, indent=0, sort_keys=True), encoding="utf-8"
        )
        start = a.start or (max(int(c["candidate_id"][5:]) for c in base["candidates"]) + 1)
        for i, c in enumerate(kept):
            c["candidate_id"] = f"cand-{start + i:04d}"
        public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in kept]
        out = {
            "candidate_list_version": a.version,
            "policy": "ADR-0003",
            "compiled_at": self.today,
            "compiled_by": clip(a.compiled_by, 120),
            "candidates": base["candidates"] + public,
        }
        jsonschema.validate(out, self.schema)
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        a.sheet.write_text(self.sheet(kept, base), encoding="utf-8")
        if a.dropped:
            a.dropped.write_text(json.dumps(dropped, ensure_ascii=False, indent=1), encoding="utf-8")
        from collections import Counter

        print(
            json.dumps(
                {
                    "new": len(public),
                    "by_group_dept_status": {
                        f"{k[0]}/{k[1]}/{k[2]}": v
                        for k, v in sorted(
                            Counter((c["_group"], c["owner_dept"], c["license_status"]) for c in kept).items()
                        )
                    },
                    "dropped": len(dropped),
                    "total": len(out["candidates"]),
                },
                ensure_ascii=False,
                indent=1,
            )
        )

    # ---------- sheet ----------
    def sheet(self, kept: list[dict], base: dict) -> str:
        from collections import Counter

        a = self.a
        gname = {
            "ich": "ICH 指南",
            "ema": "EMA 指南 / 程序文件",
            "fda": "FDA 指南",
            "tfda_site": "TFDA 指引 / 法規 / 公告",
            "tfda_label": "TFDA 仿單",
        }
        lines = [
            f"# DEC-011 候选清单 {a.version}（M5-01 扩语料，记录 89）",
            "",
            f"编制：{self.today}。承接 v1.1（{len(base['candidates'])} 条）；本版新增 **{len(kept)} 条**候选，来源限 ADR-0003 白名单（ICH / EMA / FDA / TFDA），"
            "每条附同日下载的 SHA-256、页数与文本层字符数；TFDA 仿單另附資料集 39/36 同日快照的逐字核对与现行性字段。"
            "`预判` 是机械核对结果，`eligible` 只表示许可依据与已签字候选同源且核对全部通过；签字前请按批回复（如「批 1 确认」或列出例外）。",
            "",
            "## 分组汇总",
            "",
            "| 分组 | 条数 | 部门 | 预判 eligible | 预判 needs_review | 许可依据 | 签字后待办 |",
            "| --- | ---: | --- | ---: | ---: | --- | --- |",
        ]
        for g in ("ich", "ema", "fda", "tfda_site", "tfda_label"):
            rows = [c for c in kept if c["_group"] == g]
            if not rows:
                continue
            depts = Counter(c["owner_dept"] for c in rows)
            e = sum(c["license_status"] == "eligible" for c in rows)
            todo = (
                "逐页图像层目视（条件 3），入库时署名（条件 4）"
                if g == "tfda_label"
                else "按 pdf_url 重新下载比对 sha256；pypdf 抽取页文本"
            )
            lines.append(
                f"| {gname[g]} | {len(rows)} | {', '.join(f'{d} {n}' for d, n in sorted(depts.items()))} | {e} | {len(rows) - e} | {rows[0]['_basis'].split('（')[0]} | {todo} |"
            )
        depts = Counter(c["owner_dept"] for c in kept if c["license_status"] == "eligible")
        lines += [
            "",
            f"预判 eligible 的部门分布：{', '.join(f'{d} {n}' for d, n in sorted(depts.items()))}（决策 86 的目标是 MA 120 / PV 120 / CO 80 含现有 79 份）。",
            "",
        ]
        for b in range(0, len(kept), 50):
            batch = kept[b : b + 50]
            lines += [
                f"## 批 {b // 50 + 1}（{batch[0]['candidate_id']} – {batch[-1]['candidate_id']}，{len(batch)} 条）",
                "",
                "| 候选 | 标题 | 语言 | 部门 | 版本/日期 | 页 | 许可依据 | 预判 | 备注 |",
                "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
            ]
            for c in batch:
                note = "；".join(c["_problems"]) if c["_problems"] else ""
                lines.append(
                    f"| {c['candidate_id']} | {clip(c['title'], 90).replace('|', '／')} | {c['language']} | {c['owner_dept']} | {clip(c['version_or_date'], 60).replace('|', '／')} | {c['_pages']} | {c['_basis'].replace('|', '／')} | {c['license_status']} | {clip(note, 120).replace('|', '／')} |"
                )
            lines.append("")
        lines += []
        reasons: Counter = Counter()
        scans = []
        for d in self.dropped:
            why = d["why"]
            if why.startswith("无文本层"):
                key = "无文本层（扫描件）"
            elif why.startswith("already"):
                key = "已在清单中"
            elif why.startswith("not a PDF"):
                key = "非 PDF（docx / zip）"
            elif why.startswith("download failed"):
                key = "下载失败"
            elif "same INN" in why or "beyond cap" in why:
                key = "同成分已有候选 / 超出配额"
            else:
                key = why[:40]
            reasons[(d["seed"]["group"], key)] += 1
            if key == "无文本层（扫描件）":
                scans.append(f"{d['seed']['title'][:60]}（{d['seed']['owner_dept']}）")
        lines += ["## 未列入（机械核对未通过或不需要）", "", "| 分组 | 原因 | 条数 |", "| --- | --- | ---: |"]
        for (g, key), n in sorted(reasons.items()):
            lines.append(f"| {gname.get(g, g)} | {key} | {n} |")
        if scans:
            shown = "；".join(scans[:12]) + (f"；…等 {len(scans)} 份（全部见 dropped.json）" if len(scans) > 12 else "")
            lines += [
                "",
                "无文本层的文件（不做 OCR，按 ADR-0003 决策 2026-09-12 第 4 项；同成分已改试其他仿單）：" + shown,
            ]
        lines += [
            "",
            "## 签字",
            "",
            "决策人按批回复；每批的 `reviewer_decision` / `reviewer_note` 由实现方据回复写入下一版本文件（不覆盖本版）。",
            "",
        ]
        return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=Path, required=True)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--sheet", type=Path, required=True)
    p.add_argument("--staging", type=Path, default=REPO / "evals/main_set/sources_staging")
    p.add_argument("--tfda-39", type=Path)
    p.add_argument("--tfda-39-zip", type=Path)
    p.add_argument("--tfda-36", type=Path)
    p.add_argument("--tfda-36-zip", type=Path)
    p.add_argument("--version", default="v1.2")
    p.add_argument("--today", required=True)
    p.add_argument("--start", type=int, default=None)
    p.add_argument(
        "--cap",
        action="append",
        default=[],
        help="group=N: stop adding candidates of that group once N eligible are listed",
    )
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--dropped", type=Path, default=None)
    p.add_argument("--compiled-by", default="ADR-0003 Claude Fable 5.1（承接 v1.1；M5-01 扩语料候选，记录 89）")
    Compiler(p.parse_args()).run()


if __name__ == "__main__":
    main()
