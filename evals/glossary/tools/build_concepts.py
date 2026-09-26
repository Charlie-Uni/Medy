"""Concept terms for the query-rewrite glossary (ADR-0008, record 93): English multi-word terms that recur across
the English corpus documents, each with a Chinese rendering (simplified and traditional) so a Chinese question can
reach an English chunk through the lexical channel.

Two steps, both reproducible:

1. Mechanical extraction — 2- to 4-word lower-case n-grams from the extracted page texts (no digits, no stopword at
   either end), kept when they occur at least `--min-tf` times in at least `--min-df` documents, nested shorter
   grams folded into the longer one, ranked by tf * log2(1 + df); every kept term cites the corpus pages it occurs
   on (document_key + page), which `build_glossary.py` re-verifies.
2. Translation — one structured model call per batch (default gpt-6-sol) that also rejects grams that are not terms
   (`keep=false`). The Chinese renderings cannot be verified against the corpus; the concepts file records the model,
   the prompt hash and the cost so the decision-maker can spot-check a sample before the glossary is released.

Replay / main-set questions never enter this tool (INV-EVAL-01): only corpus page texts do.

    python evals/glossary/tools/build_concepts.py --corpus evals/main_set/corpus.json --pages evals/main_set/pages \
        --out evals/glossary/sources/concepts_2026-09-26.json [--dry-run] [--max-terms 500]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

STOP = set(
    """the of and a an to in for on by with or be is are as at that this which from any all such other its their
    may should shall not if when where than then also each per via has have had was were been being will would can
    could must into within without under over between about above below after before during through these those
    there here it he she they we you i his her our your one two three more most less least very only both either
    neither nor so too""".split()
)
JUNK = {
    "page",
    "www",
    "http",
    "https",
    "com",
    "europa",
    "eu",
    "rev",
    "see",
    "e.g",
    "i.e",
    "etc",
    "vol",
    "ema",
    "fda",
    "ich",
}
TOKEN = re.compile(r"[a-z][a-z-]*[a-z]|[a-z]")
TRANSLATE_SYSTEM = (
    "你是药品监管事务的双语术语专家。下面的英文短语是从 EMA GVP 模块、ICH 指南与 FDA 指南全文中机械抽取的高频 2–4 词短语。"
    "请逐条判断它是否是监管、药物警戒、临床试验或药品标签领域的固定术语或专有概念（keep=true）；普通短语、句子片段、"
    "页眉页脚残片、机构名称的碎片一律 keep=false。对 keep=true 的术语给出 zh_hans（中国大陆监管文件常用译法，简体）"
    "和 zh_hant（台湾监管文件常用译法，繁体；若与大陆用法不同用台湾用法，例如 marketing authorisation holder："
    "大陆「上市许可持有人」、台湾「藥品許可證持有者」）。译名只给术语本身，不加解释，不超过 15 个汉字；常以英文缩写通行的术语"
    "（PSUR、RMP、ICSR）仍给中文全称。keep=false 时 zh_hans 与 zh_hant 留空字符串。note 只在需要时一句话说明。只输出 JSON。"
)
SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "en": {"type": "string"},
                    "keep": {"type": "boolean"},
                    "zh_hans": {"type": "string"},
                    "zh_hant": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["en", "keep", "zh_hans", "zh_hant", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def load_english_pages(corpus_path: Path, pages_dir: Path) -> dict[str, dict[int, str]]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    out: dict[str, dict[int, str]] = {}
    for doc in corpus["documents"]:
        if doc.get("language") != "en":
            continue
        d = pages_dir / doc["source_hash"]
        if not d.is_dir():
            continue
        out[doc["document_key"]] = {
            int(f.stem): f.read_text(encoding="utf-8") for f in d.glob("*.txt") if f.stem.isdigit()
        }
    return out


def grams(text: str, sizes: tuple[int, ...] = (2, 3, 4)):
    tokens = TOKEN.findall(text.lower())
    for n in sizes:
        for i in range(len(tokens) - n + 1):
            g = tokens[i : i + n]
            if g[0] in STOP or g[-1] in STOP or any(t in JUNK or len(t) < 2 for t in g):
                continue
            if any(t in STOP for t in g[1:-1]) and n == 2:
                continue
            yield " ".join(g)


def extract(pages: dict[str, dict[int, str]], *, min_tf: int, min_df: int, max_terms: int) -> list[dict]:
    tf: Counter[str] = Counter()
    docs: dict[str, set[str]] = defaultdict(set)
    evidence: dict[str, list[dict]] = defaultdict(list)
    for key, by_page in pages.items():
        for page, text in sorted(by_page.items()):
            seen_here: set[str] = set()
            for g in grams(text):
                tf[g] += 1
                docs[g].add(key)
                if g not in seen_here and len(evidence[g]) < 3:
                    evidence[g].append({"document_key": key, "page": page})
                seen_here.add(g)
    kept = {g: c for g, c in tf.items() if c >= min_tf and len(docs[g]) >= min_df}
    # fold a shorter gram into a longer one that contains it and carries most of its occurrences
    longer = sorted(kept, key=lambda g: -len(g.split()))
    drop: set[str] = set()
    for g in kept:
        for big in longer:
            if big == g or len(big.split()) <= len(g.split()):
                continue
            if f" {g} " in f" {big} " and kept[big] >= 0.7 * kept[g]:
                drop.add(g)
                break
    ranked = sorted((g for g in kept if g not in drop), key=lambda g: -(kept[g] * math.log2(1 + len(docs[g]))))
    return [{"en": g, "tf": kept[g], "df": len(docs[g]), "evidence": evidence[g]} for g in ranked[:max_terms]]


def translate(terms: list[dict], *, model: str, batch: int) -> tuple[list[dict], float]:
    from medops.core.config import Settings
    from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
    from medops.infrastructure.llm.gateway import OPENAI_PRICES, Message, ModelRequest, PriceTable
    from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway

    settings = Settings()
    gateway = BudgetedGateway(
        OpenAIModelGateway.from_settings(settings),
        prices=PriceTable(OPENAI_PRICES),
        ledger=InMemorySpendLedger(),
        monthly_cap_usd=settings.llm_monthly_budget_usd,
    )
    cost = 0.0
    by_en = {t["en"]: t for t in terms}
    for start in range(0, len(terms), batch):
        chunk = terms[start : start + batch]
        user = json.dumps([t["en"] for t in chunk], ensure_ascii=False)
        response = gateway.complete(
            ModelRequest(
                purpose="glossary_concepts",
                model_id=model,
                messages=(Message(role="system", content=TRANSLATE_SYSTEM), Message(role="user", content=user)),
                max_output_tokens=6000,
                json_schema=SCHEMA,
                timeout_s=180,
            )
        )
        cost += response.cost_usd
        items = (response.parsed or json.loads(response.text))["items"]
        for item in items:
            t = by_en.get(item["en"])
            if t is None:
                continue
            t.update(
                {
                    "keep": bool(item["keep"]),
                    "zh_hans": item["zh_hans"].strip(),
                    "zh_hant": item["zh_hant"].strip(),
                    "note": item["note"].strip(),
                }
            )
        print(f"batch {start // batch + 1}: {len(items)} items, cost so far {cost:.3f} USD", flush=True)
    for t in terms:
        t.setdefault("keep", False)
        t.setdefault("zh_hans", "")
        t.setdefault("zh_hant", "")
        t.setdefault("note", "no translation returned")
    return terms, cost


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=REPO / "evals/main_set/corpus.json")
    ap.add_argument("--pages", type=Path, default=REPO / "evals/main_set/pages")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="gpt-6-sol")
    ap.add_argument("--max-terms", type=int, default=500)
    ap.add_argument("--min-tf", type=int, default=6)
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--batch", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true", help="extract only; print the candidates and spend nothing")
    args = ap.parse_args()
    pages = load_english_pages(args.corpus, args.pages)
    if not pages:
        raise SystemExit("no English page texts found")
    terms = extract(pages, min_tf=args.min_tf, min_df=args.min_df, max_terms=args.max_terms)
    print(
        f"documents {len(pages)}, pages {sum(len(p) for p in pages.values())}, candidate terms {len(terms)}", flush=True
    )
    if args.dry_run:
        for t in terms:
            print(f"{t['tf']:5d} {t['df']:3d}  {t['en']}")
        return 0
    terms, cost = translate(terms, model=args.model, batch=args.batch)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    out = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "adr": "docs/adr/ADR-0008-medical-glossary-sources.md",
        "corpus": {
            "path": str(args.corpus),
            "dataset_version": corpus.get("dataset_version"),
            "english_documents": len(pages),
        },
        "extraction": {
            "min_tf": args.min_tf,
            "min_df": args.min_df,
            "max_terms": args.max_terms,
            "ngram_sizes": [2, 3, 4],
        },
        "model": args.model,
        "prompt_sha256": hashlib.sha256(TRANSLATE_SYSTEM.encode("utf-8")).hexdigest(),
        "cost_usd": round(cost, 4),
        "kept": sum(1 for t in terms if t["keep"]),
        "terms": terms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "terms"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
