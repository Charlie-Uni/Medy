"""Zero-cost check of the answer-context layouts (M5-04, record 113) on a stored main-set run.

No model API is called. For every row of the stored run the evidence set is re-read from the database, the three
layouts (`off`, `compact-v1`, `sentfocus-v1`) are rendered exactly as the answer node would, and the tool reports

- tokens: the answer prompt under each layout, and the cut as a share of the tokens the stored run really spent on
  the item (all model calls); a proxy tokenizer (`tiktoken` o200k_base) is used when importable, the repository's
  conservative estimate otherwise — the provider's own count is only known after a paid run;
- time: the local sentence scoring per question;
- retention: whether the annotated gold key text of a gold chunk in the evidence, and the sentence each stored
  claim leaned on, are still visible after sentence focusing.

The layout parameters are constants of `medops.harness.evidence_focus`, fixed before this tool was first run; the
tool measures them and offers no way to sweep them (INV-EVAL-01: evaluation material does not shape a candidate).

python evals/harness/tools/focus_check.py --run evals/harness/runs/<stored run> --out evals/harness/runs/<name> \
    [--dataset evals/main_set/main-v3-provisional] [--mapping <chunk mapping>] [--device mps] [--limit N]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import statistics
import sys
import time
import unicodedata
from datetime import date

import psycopg

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/safety_set/tools"))
from common import PRODUCTION_DB, admin_dsn  # noqa: E402

from medops.domain.common import DocStatus  # noqa: E402
from medops.domain.evidence import Citation, Evidence  # noqa: E402
from medops.harness import evidence_focus as ef  # noqa: E402
from medops.harness.nodes import ANSWER_SYSTEM  # noqa: E402
from medops.infrastructure.llm.gateway import estimate_tokens  # noqa: E402
from medops.retrieval.production import require_index_coverage  # noqa: E402

MODES = (ef.EVIDENCE_FOCUS_OFF, ef.EVIDENCE_FOCUS_COMPACT, *ef.FOCUS_PARAMS)


def read_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tokenizer() -> tuple[str, object]:
    try:
        import tiktoken
    except ImportError:
        return "estimate_tokens (repository estimate)", estimate_tokens
    enc = tiktoken.get_encoding("o200k_base")
    return "tiktoken o200k_base (proxy; the provider's tokenizer is not public)", lambda s: len(enc.encode(s))


def squash(text: str) -> str:
    """Whitespace- and width-insensitive form for "is this annotated text still visible" comparisons."""
    return "".join(unicodedata.normalize("NFKC", text).split()).lower()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_evidence(conn: psycopg.Connection, chunk_ids: list[str]) -> dict[str, Evidence]:
    rows = conn.execute(
        """select c.chunk_id::text, c.doc_id::text, c.page, coalesce(c.section, ''), c.content, c.chunk_content_hash,
                  d.version, d.effective_from
           from chunks c join documents d on d.doc_id = c.doc_id where c.chunk_id = any(%s::uuid[])""",
        (chunk_ids,),
    ).fetchall()
    out = {}
    for chunk_id, doc_id, page, section, content, content_hash, version, effective in rows:
        out[chunk_id] = Evidence(
            citation=Citation(
                doc_id=doc_id,
                version=version,
                effective_date=effective or date(2000, 1, 1),
                page=page,
                section=section,
                chunk_id=chunk_id,
            ),
            text=content,
            evidence_text_hash=sha(content),
            chunk_content_hash=content_hash,
            status=DocStatus.active,
        )
    return out


def prompt_text(query: str, rendered: ef.RenderedEvidence) -> str:
    user = f"问题：{query}\n\n证据（共 {len(rendered.blocks)} 段）：\n\n" + rendered.body()
    return ANSWER_SYSTEM + user


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=pathlib.Path, required=True, help="stored main-set run (rows.jsonl)")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--dataset", type=pathlib.Path, default=REPO / "evals/main_set/main-v3-provisional")
    ap.add_argument(
        "--mapping",
        type=pathlib.Path,
        default=REPO / "evals/experiments/e2e/main-v3-provisional/chunk_mapping.chunker-v2.main-v3-provisional.json",
    )
    ap.add_argument("--device", default="mps")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--glossary",
        default="glossary-20260926-e4daca58a8e4",
        help="glossary version of the released rewrite (its queries feed sentfocus-v2); 'glossary-none' to skip",
    )
    ap.add_argument("--modes", default=",".join(MODES), help="comma-separated subset of the layouts")
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("refusing to overwrite an existing output directory")
    modes = tuple(m for m in MODES if m in {x.strip() for x in args.modes.split(",")})
    sentence_modes = [m for m in modes if m in ef.FOCUS_PARAMS]

    rows = list({r["sample_id"]: r for r in read_jsonl(args.run / "rows.jsonl")}.values())
    rows = [r for r in rows if r.get("evidence_chunks")]
    if args.limit:
        rows = rows[: args.limit]
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    if mapping["dataset_hash"] != manifest["dataset_hash"]:
        raise SystemExit("chunk mapping belongs to another dataset version")
    gold_chunks = {e["gold_id"]: set(e["chunk_ids"]) for e in mapping["entries"] if e["status"] == "mapped"}
    samples = {s["sample_id"]: s for s in read_jsonl(args.dataset / "samples.jsonl")}

    with psycopg.connect(admin_dsn(PRODUCTION_DB)) as conn:
        conn.read_only = True
        require_index_coverage(conn, plane=PRODUCTION_DB)
        evidence = load_evidence(conn, sorted({c for r in rows for c in r["evidence_chunks"]}))

    from medops.retrieval.glossary_store import load_versioned_glossary
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.rewrite import rewrite

    glossary = (
        load_versioned_glossary(REPO / "evals/glossary", args.glossary) if args.glossary != "glossary-none" else None
    )
    reranker = BgeRerankerV2M3(device=args.device)
    tok_name, count = tokenizer()

    out_rows: list[dict] = []
    seconds: dict[str, list[float]] = {m: [] for m in sentence_modes}
    for n, r in enumerate(rows, 1):
        items = [evidence[c] for c in r["evidence_chunks"] if c in evidence]
        if not items:
            continue
        rewritten = rewrite(r["query"], glossary=glossary).queries if glossary else ()
        rendered = {}
        for mode in modes:
            t0 = time.perf_counter()
            rendered[mode] = ef.render_evidence(
                r["query"], items, mode=mode, scorer=reranker.score, rewritten=rewritten
            )
            if mode in seconds:
                seconds[mode].append(time.perf_counter() - t0)
        chunk_order = [e.citation.chunk_id for e in items]
        focused = {m: dict(zip(chunk_order, rendered[m].blocks, strict=True)) for m in sentence_modes}
        row = {
            "sample_id": r["sample_id"],
            "language": r["language"],
            "kind": r["kind"],
            "outcome": r["outcome"],
            "gold_cited": bool(r.get("gold_cited")),
            "model_tokens": r["model_tokens"],
            "prompt_tokens": {m: count(prompt_text(r["query"], rendered[m])) for m in modes},
            "focus": {
                m: {
                    "evidence_tokens_full": rendered[m].full_tokens,
                    "evidence_tokens_kept": rendered[m].kept_tokens,
                    "units": rendered[m].units,
                    "kept_units": rendered[m].kept_units,
                    "seconds": round(seconds[m][-1], 3),
                }
                for m in sentence_modes
            },
            "gold": [],
            "claims": [],
        }
        # retention of the annotated gold key text, for gold chunks that are in the evidence
        for g in samples.get(r["sample_id"], {}).get("required_gold_evidence", []):
            key = squash(g["key_text"])
            for chunk_id in sorted(gold_chunks.get(g["gold_id"], set()) & set(chunk_order)):
                if key not in squash(evidence[chunk_id].text):
                    continue  # the key text straddles a chunk boundary: not decidable on this chunk alone
                row["gold"].append(
                    {
                        "gold_id": g["gold_id"],
                        "chunk": chunk_id,
                        "kept": {m: key in squash(focused[m][chunk_id]) for m in sentence_modes},
                    }
                )
        # retention of the sentence each stored claim leaned on: the unit of the cited chunk the cross-encoder ranks
        # first for the claim text must still be visible
        if r["outcome"] == "answered" and sentence_modes:
            for claim in r.get("claims", []):
                for chunk_id in r.get("cited_chunks", []):
                    if chunk_id not in chunk_order:
                        continue
                    text = evidence[chunk_id].text
                    units = [text[a:b].strip() for a, b in ef.split_units(text)]
                    scores = reranker.score(claim, units)
                    best = units[max(range(len(units)), key=lambda j: scores[j])]
                    row["claims"].append(
                        {
                            "chunk": chunk_id,
                            "kept": {m: squash(best) in squash(focused[m][chunk_id]) for m in sentence_modes},
                        }
                    )
        out_rows.append(row)
        if n % 100 == 0:
            print(f"{n}/{len(rows)}", flush=True)

    def total(mode: str) -> int:
        return sum(x["prompt_tokens"][mode] for x in out_rows)

    spent = sum(x["model_tokens"] for x in out_rows)
    off = total(ef.EVIDENCE_FOCUS_OFF) if ef.EVIDENCE_FOCUS_OFF in modes else 0
    gold = [g for x in out_rows for g in x["gold"]]
    claims = [c for x in out_rows for c in x["claims"]]
    wins = [x for x in out_rows if x["outcome"] == "answered" and x["gold_cited"] and x["gold"]]

    def retention(mode: str) -> dict:
        hidden = [x["sample_id"] for x in wins if not any(g["kept"][mode] for g in x["gold"])]
        kept_gold = sum(g["kept"][mode] for g in gold)
        kept_claims = sum(c["kept"][mode] for c in claims)
        return {
            "gold_key_text": {"n": len(gold), "kept": kept_gold, "rate": rate(kept_gold, len(gold))},
            "claim_support_sentence": {"n": len(claims), "kept": kept_claims, "rate": rate(kept_claims, len(claims))},
            "stored_successes_with_gold_in_evidence": len(wins),
            "stored_successes_whose_gold_text_is_hidden": hidden,
            "by_language": {
                lang: rate(
                    sum(g["kept"][mode] for x in out_rows if x["language"] == lang for g in x["gold"]),
                    sum(len(x["gold"]) for x in out_rows if x["language"] == lang),
                )
                for lang in sorted({x["language"] for x in out_rows})
            },
        }

    summary = {
        "run": args.run.name,
        "dataset_hash": manifest["dataset_hash"],
        "items": len(out_rows),
        "tokenizer": tok_name,
        "glossary_for_rewrites": args.glossary,
        "parameters": {
            "versions": {m: dataclasses.asdict(ef.FOCUS_PARAMS[m]) for m in sentence_modes},
            "min_chunk_tokens": ef.MIN_CHUNK_TOKENS,
            "min_unit_tokens": ef.MIN_UNIT_TOKENS,
            "max_unit_chars": ef.MAX_UNIT_CHARS,
            "scorer": reranker.spec.model_dump(),
        },
        "tokens": {
            "stored_run_model_tokens_per_item": round(spent / len(out_rows), 1),
            "answer_prompt_per_item": {m: round(total(m) / len(out_rows), 1) for m in modes},
            "prompt_cut_vs_off": {m: round(1 - total(m) / off, 4) for m in modes} if off else {},
            "cut_as_share_of_all_model_tokens": {m: round((off - total(m)) / spent, 4) for m in modes} if off else {},
            "note": "input side only; citing aliases instead of UUIDs also shortens the output, not counted here",
        },
        "focus": {
            m: {
                "evidence_tokens_kept_share": round(
                    sum(x["focus"][m]["evidence_tokens_kept"] for x in out_rows)
                    / sum(x["focus"][m]["evidence_tokens_full"] for x in out_rows),
                    4,
                ),
                "units_per_item": round(statistics.mean(x["focus"][m]["units"] for x in out_rows), 1),
                "kept_units_per_item": round(statistics.mean(x["focus"][m]["kept_units"] for x in out_rows), 1),
                "seconds_p50": round(pct(seconds[m], 0.5), 3),
                "seconds_p95": round(pct(seconds[m], 0.95), 3),
                "device": args.device,
            }
            for m in sentence_modes
        },
        "retention": {m: retention(m) for m in sentence_modes},
    }
    args.out.mkdir(parents=True)
    (args.out / "rows.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out_rows), encoding="utf-8"
    )
    (args.out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    t = summary["tokens"]
    lines = [
        f"# Answer-context layout check on `{args.run.name}` — {len(out_rows)} items, no model calls",
        "",
        f"Tokenizer: {tok_name}. Rewritten queries from {args.glossary}. Parameters are the constants of "
        f"`medops.harness.evidence_focus` ({json.dumps(summary['parameters']['versions'])}); scorer "
        f"{reranker.spec.model_id}.",
        "",
        "| layout | answer prompt tokens / item | cut vs off | cut as share of all model tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    for m in modes:
        cut = f"{t['prompt_cut_vs_off'][m] * 100:.1f}%" if off else "—"
        share = f"{t['cut_as_share_of_all_model_tokens'][m] * 100:.1f}%" if off else "—"
        lines.append(f"| {m} | {t['answer_prompt_per_item'][m]} | {cut} | {share} |")
    lines += [
        "",
        f"Stored run: {t['stored_run_model_tokens_per_item']} model tokens per item over all calls. The last column "
        "is the input-side cut only; the gate needs 25% on the provider's own count.",
    ]
    for m in sentence_modes:
        f, k = summary["focus"][m], summary["retention"][m]
        hidden = k["stored_successes_whose_gold_text_is_hidden"]
        lines += [
            "",
            f"## {m}",
            "",
            f"{f['evidence_tokens_kept_share'] * 100:.1f}% of the evidence tokens kept "
            f"({f['kept_units_per_item']} of {f['units_per_item']} units per item); local scoring p50 "
            f"{f['seconds_p50']} s, P95 {f['seconds_p95']} s on {args.device}.",
            "",
            "| retention | kept | n | rate |",
            "| --- | ---: | ---: | ---: |",
            f"| annotated gold key text (gold chunk in evidence) | {k['gold_key_text']['kept']} | "
            f"{k['gold_key_text']['n']} | {k['gold_key_text']['rate']} |",
            f"| sentence a stored claim leaned on | {k['claim_support_sentence']['kept']} | "
            f"{k['claim_support_sentence']['n']} | {k['claim_support_sentence']['rate']} |",
            "",
            f"Stored successes with their gold chunk in evidence: {k['stored_successes_with_gold_in_evidence']}; "
            f"of these, the gold key text is hidden for {len(hidden)}: {', '.join(hidden) or 'none'}.",
            "",
            "Gold key text kept, by language: " + ", ".join(f"{a} {b}" for a, b in k["by_language"].items()) + ".",
        ]
    lines += [
        "",
        "This is not a quality result: whether the model answers as well from the focused prompt is only known "
        "from a replay run.",
    ]
    (args.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
