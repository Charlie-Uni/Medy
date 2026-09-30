"""Retrieval-recall diagnostic on replay-v1 items (record 92): for each item, run production retrieval locally (no model
calls — the rewriter is rule-based, embeddings and reranker are local) and record whether a gold chunk is among the
fused candidates (top-20) and among the reranked evidence (top-8). Splits failures into recall / rerank / generation.

    python evals/replay/tools/recall_diag.py --out evals/harness/runs/<run> [--set evals/replay/replay-v1]
        [--labels bad] [--controls 30] [--device mps] [--as-of 2026-09-24]

Rows hold ids, ranks and latencies only; the report groups by label reason, department and slice.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys
import time
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "evals/harness/tools"))


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def classify(row: dict) -> str:
    if row["gold_rank_candidates"] is None:
        return "recall"  # gold not among the fused top-20
    if row["gold_rank_evidence"] is None:
        return "rerank"  # in the top-20, pushed out of the top-8
    return "generation"  # in context; the answer / verify stage failed


def render(rows: list[dict], meta: dict) -> str:
    bad = [r for r in rows if r["label"] == "bad"]
    good = [r for r in rows if r["label"] == "good"]
    lines = [f"# Recall diagnostic {meta['run']} ({meta['date']})", ""]
    lines += [
        f"- replay set {meta['dataset_version']} ({meta['dataset_hash'][:8]}…), subset items with label bad: {len(bad)}; good controls: {len(good)}",
        f"- retrieval: production hybrid config, rerank_output {meta['rerank_output']}, glossary {meta.get('glossary', 'glossary-none')}, multi_query {meta.get('multi_query', False)}, doc_focus {meta.get('doc_focus', False)}, query_translation {meta.get('query_translation', 'off')}, as_of {meta['as_of']}, device {meta['device']}; no model calls",
        "",
    ]
    lines += ["## Failed items by stage", "", "| stage | n | share |", "| --- | ---: | ---: |"]
    c = Counter(classify(r) for r in bad)
    for k in ("recall", "rerank", "generation"):
        lines.append(f"| {k} | {c[k]} | {100 * c[k] / max(1, len(bad)):.0f}% |")
    lines += [
        "",
        f"Good controls: gold in top-20 {sum(r['gold_rank_candidates'] is not None for r in good)}/{len(good)}, in top-8 {sum(r['gold_rank_evidence'] is not None for r in good)}/{len(good)}; gold rank distribution {dict(sorted(Counter(r['gold_rank_evidence'] for r in good).items(), key=lambda kv: str(kv[0])))}",
        "",
    ]
    lines += [
        "## By label reason",
        "",
        "| reason | n | recall | rerank | generation |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for reason in sorted({r["label_reason"] or "" for r in bad}):
        rs = [r for r in bad if (r["label_reason"] or "") == reason]
        cc = Counter(classify(r) for r in rs)
        lines.append(f"| {reason} | {len(rs)} | {cc['recall']} | {cc['rerank']} | {cc['generation']} |")
    lines += [
        "",
        "## By department",
        "",
        "| dept | n | recall | rerank | generation |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for d in ("MA", "PV", "CO"):
        rs = [r for r in bad if r["dept"] == d]
        cc = Counter(classify(r) for r in rs)
        lines.append(f"| {d} | {len(rs)} | {cc['recall']} | {cc['rerank']} | {cc['generation']} |")
    lines += [
        "",
        "## Recall failures by slice",
        "",
        "| slice | failed items with slice | of which recall |",
        "| --- | ---: | ---: |",
    ]
    for s in sorted({s for r in bad for s in r["slices"]}):
        rs = [r for r in bad if s in r["slices"]]
        lines.append(f"| {s} | {len(rs)} | {sum(classify(r) == 'recall' for r in rs)} |")
    if any("query_cjk" in r for r in bad):
        cross = [
            r for r in bad if classify(r) == "recall" and r.get("query_cjk", 0) >= 0.5 and r.get("gold_cjk", 1) < 0.2
        ]
        lines += [
            "",
            f"Cross-lingual recall failures (Chinese query, English gold chunk): {len(cross)} of {c['recall']}",
            "",
        ]
    lines += [
        "",
        "## Items",
        "",
        "| item | label | reason | dept | gold rank top-20 | gold rank top-8 | stage |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['replay_id']} | {r['label']} | {r['label_reason']} | {r['dept']} | {r['gold_rank_candidates'] or ''} | {r['gold_rank_evidence'] or ''} | {classify(r) if r['label'] == 'bad' else ''} |"
        )
    return "\n".join(lines) + "\n"


def main_set_items(main_set: pathlib.Path, mapping_doc: dict) -> list[dict]:
    """Every gold-bearing sample of a frozen main set as a diagnostic item. A gold maps to the chunk ids that cover
    its key text (SPEC section 6); an unmappable gold keeps an empty set and counts as a miss, never as a skip."""
    chunks_for = {e["gold_id"]: list(e["chunk_ids"]) for e in mapping_doc["entries"]}
    out = []
    for line in (main_set / "samples.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sample = json.loads(line)
        golds = sample.get("required_gold_evidence") or []
        if not golds:
            continue  # no-answer samples are judged by abstention, not recall (spec-m1)
        sets = [chunks_for.get(g["gold_id"], []) for g in golds]
        out.append(
            {
                "replay_id": sample["sample_id"],
                "label": "conflict" if "version_conflict" in sample.get("slices", []) else "answerable",
                "label_reason": "main-set",
                "dept": sample["dept"],
                "kind": "conflict" if "version_conflict" in sample.get("slices", []) else "answerable",
                "slices": sample.get("slices", []),
                "language": sample.get("language"),
                "query": sample["query"],
                "gold_chunks": [c for st in sets for c in st],
                "golds": sets,
                "historical": False,
            }
        )
    return out


def main_set_metrics(rows: list[dict]) -> dict:
    """Strict macro Recall@k = mean over samples of (golds hit in top-k / golds); Hit@5 = share of samples with any
    gold in the top 5. top-5 / top-8 are taken from the reranked evidence, top-20 from the fused candidates."""

    def block(rs: list[dict]) -> dict:
        n = len(rs)
        if not n:
            return {"n": 0}
        return {
            "n": n,
            "recall_at_5": round(sum(r["golds_hit_top5"] / r["golds"] for r in rs) / n, 4),
            "hit_at_5": round(sum(1 for r in rs if r["golds_hit_top5"]) / n, 4),
            "recall_at_8": round(sum(r["golds_hit_top8"] / r["golds"] for r in rs) / n, 4),
            "recall_at_20": round(sum(r["golds_hit_top20"] / r["golds"] for r in rs) / n, 4),
        }

    slices = sorted({sl for r in rows for sl in r.get("slices", [])})
    return {
        "all": block(rows),
        "per_dept": {d: block([r for r in rows if r["dept"] == d]) for d in sorted({r["dept"] for r in rows})},
        "per_language": {
            lg: block([r for r in rows if r.get("language") == lg])
            for lg in sorted({str(r.get("language")) for r in rows})
        },
        "per_slice": {sl: block([r for r in rows if sl in r.get("slices", [])]) for sl in slices},
        "per_kind": {k: block([r for r in rows if r["kind"] == k]) for k in sorted({r["kind"] for r in rows})},
    }


def render_main_set(m: dict) -> str:
    lines = ["", "## Main set (strict macro recall over gold-bearing samples)", ""]
    lines.append("| group | n | Recall@5 | Hit@5 | Recall@8 | Recall@20 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")

    def row(name: str, b: dict) -> str:
        return (
            f"| {name} | {b['n']} | {b.get('recall_at_5', '')} | {b.get('hit_at_5', '')} | "
            f"{b.get('recall_at_8', '')} | {b.get('recall_at_20', '')} |"
        )

    lines.append(row("all", m["all"]))
    for group in ("per_kind", "per_dept", "per_language", "per_slice"):
        for name, b in m[group].items():
            lines.append(row(f"{group[4:]}={name}", b))
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--set", type=pathlib.Path, default=REPO / "evals/replay/replay-v1")
    ap.add_argument("--labels", default="bad", help="comma-separated labels to diagnose (default bad)")
    ap.add_argument("--controls", type=int, default=30, help="number of good items to run as controls")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date(2026, 9, 24))
    ap.add_argument("--gpu-timeout", type=float, default=120.0)
    ap.add_argument("--glossary", default="glossary-none", help="released glossary version to rewrite with (record 93)")
    ap.add_argument("--glossary-dir", type=pathlib.Path, default=REPO / "evals/glossary")
    ap.add_argument("--multi-query", action="store_true", help="search every rewritten query and fuse (record 93)")
    ap.add_argument(
        "--doc-focus", action="store_true", help="search the named corpus document on its own and fuse (record 94)"
    )
    ap.add_argument(
        "--translate",
        default="off",
        help="query translation model id (record 95); needs OPENAI_API_KEY, costs about 0.0002 USD per item",
    )
    ap.add_argument(
        "--main-set",
        type=pathlib.Path,
        default=None,
        help="frozen main-set directory: run every gold-bearing sample and report strict macro Recall@5 / Hit@5 (M5-03)",
    )
    ap.add_argument("--mapping", type=pathlib.Path, default=None, help="gold->chunk mapping for --main-set")
    ap.add_argument("--items", type=int, default=0, help="smoke: only the first N items")
    args = ap.parse_args()

    sr = _load(REPO / "evals/harness/tools/safety_run.py", "safety_run")
    sa = sr._load_smoke_ask()
    import psycopg

    from medops.core.config import Settings
    from medops.domain.common import Dept
    from medops.domain.identity import UserContext
    from medops.harness.nodes import ANSWER_SYSTEM
    from medops.harness.retrieval_port import RetrievalRequest
    from medops.retrieval.glossary_store import load_versioned_glossary
    from medops.retrieval.production import RERANK_OUTPUT, production_hybrid_config
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    if args.main_set is not None:
        manifest = json.loads((args.main_set / "manifest.json").read_text(encoding="utf-8"))
        mapping_path = args.mapping or (
            REPO / "evals/experiments/e2e" / args.main_set.name / f"chunk_mapping.chunker-v2.{args.main_set.name}.json"
        )
        mapping_doc = json.loads(mapping_path.read_text(encoding="utf-8"))
        if mapping_doc.get("dataset_hash") != manifest.get("dataset_hash"):
            raise SystemExit(f"{mapping_path.name} was built for another dataset_hash than {args.main_set.name}")
        wanted = {"answerable", "conflict"}
        todo = main_set_items(args.main_set, mapping_doc)
    else:
        manifest = json.loads((args.set / "manifest.json").read_text(encoding="utf-8"))
        items = {
            json.loads(line)["replay_id"]: json.loads(line)
            for line in (args.set / "items.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        subset = json.loads((args.set / "subset.json").read_text(encoding="utf-8"))["replay_ids"]
        wanted = set(args.labels.split(","))
        todo = [items[i] for i in subset if items[i]["label"] in wanted]
        todo += [items[i] for i in subset if items[i]["label"] == "good" and "good" not in wanted][: args.controls]
    if args.items:
        todo = todo[: args.items]

    settings = Settings()
    app_url = settings.database_url.get_secret_value()
    gpu = sa.GpuThread(args.gpu_timeout)
    provider = sa._PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    reranker = sa._PinnedReranker(gpu.call(lambda: BgeRerankerV2M3(device=args.device, output=RERANK_OUTPUT)), gpu)

    class NoGateway:
        def complete(self, *a, **k):
            raise RuntimeError("the diagnostic never calls the model")

    gateway: object = NoGateway()
    if args.translate != "off":
        from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
        from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable
        from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway

        gateway = sa._Meter(
            BudgetedGateway(
                OpenAIModelGateway.from_settings(settings),
                prices=PriceTable(OPENAI_PRICES),
                ledger=InMemorySpendLedger(),
                monthly_cap_usd=settings.llm_monthly_budget_usd,
            )
        )

    plane = sr.Plane(
        sr.PRODUCTION_DB,
        app_url,
        provider,
        reranker,
        gateway,
        args.as_of,
        sa,
        config=production_hybrid_config(),
        answer_system=ANSWER_SYSTEM,
        glossary=load_versioned_glossary(args.glossary_dir, args.glossary),
        multi_query=args.multi_query,
        doc_focus=args.doc_focus,
        query_translation=args.translate,
    )

    def cjk_ratio(text: str) -> float:
        letters = [ch for ch in text if ch.isalpha()]
        return sum("一" <= ch <= "鿿" for ch in letters) / max(1, len(letters))

    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with (
        psycopg.connect(sr.admin_dsn(sr.PRODUCTION_DB)) as admin,
        (args.out / "rows.jsonl").open("w", encoding="utf-8") as fh,
    ):
        for it in todo:
            user = UserContext(
                user_id=hashlib.sha256(f"replay:{it['replay_id']}".encode()).hexdigest()[:16],
                dept=Dept(it["dept"]),
                roles=("analyst",),
                acl_scopes=frozenset({f"{it['dept']}:read"}),
            )
            t0 = time.perf_counter()
            outcome = plane.retrieval.retrieve(
                RetrievalRequest(
                    query=it["query"],
                    user=user,
                    historical_requested=bool(it.get("historical")),
                    as_of=args.as_of,
                    session_entities=(),
                )
            )
            cands = [c.chunk_id for c in outcome.candidates]
            ev = [e.citation.chunk_id for e in outcome.evidence]
            gold = set(it["gold_chunks"])
            golds = it.get("golds") or [[c] for c in it["gold_chunks"]]  # one chunk-id set per required gold
            hits = {
                k: sum(1 for g in golds if any(c in lst[:k] for c in g)) for k, lst in ((5, ev), (8, ev), (20, cands))
            }
            row = {
                "replay_id": it["replay_id"],
                "label": it["label"],
                "label_reason": it.get("label_reason"),
                "dept": it["dept"],
                "kind": it["kind"],
                "slices": it.get("slices", []),
                "n_candidates": len(cands),
                "n_evidence": len(ev),
                "gold_rank_candidates": next((i + 1 for i, c in enumerate(cands) if c in gold), None),
                "gold_rank_evidence": next((i + 1 for i, c in enumerate(ev) if c in gold), None),
                "golds": len(golds),
                "golds_hit_top5": hits[5],
                "golds_hit_top8": hits[8],
                "golds_hit_top20": hits[20],
                "language": it.get("language"),
                "degraded": bool(outcome.degraded),
                "rewrites": len(outcome.rewritten_queries),
                "query_cjk": round(cjk_ratio(it["query"]), 2),
                "latency_s": round(time.perf_counter() - t0, 1),
            }
            if gold:
                got = admin.execute(
                    "select content from chunks where chunk_id = %s::uuid", (next(iter(gold)),)
                ).fetchone()
                if got:
                    row["gold_cjk"] = round(cjk_ratio(got[0]), 2)
                    row["gold_chars"] = len(got[0])
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(
                f"{row['replay_id']} {row['label']} top20={row['gold_rank_candidates']} top8={row['gold_rank_evidence']} {row['latency_s']}s",
                flush=True,
            )
    meta = {
        "run": args.out.name,
        "date": dt.date.today().isoformat(),
        "dataset_version": manifest["dataset_version"],
        "dataset_hash": manifest["dataset_hash"],
        "rerank_output": RERANK_OUTPUT,
        "as_of": args.as_of.isoformat(),
        "device": args.device,
        "labels": sorted(wanted),
        "controls": args.controls,
        "glossary": args.glossary,
        "multi_query": args.multi_query,
        "doc_focus": args.doc_focus,
        "query_translation": args.translate,
        "model_cost_usd": round(float(getattr(gateway, "cost", 0.0)), 4),
    }
    results = {"meta": meta, "by_stage": dict(Counter(classify(r) for r in rows if r["label"] == "bad"))}
    if args.main_set is not None:
        results["main_set"] = main_set_metrics(rows)
    (args.out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = render(rows, meta)
    if args.main_set is not None:
        report += render_main_set(results["main_set"])
    (args.out / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"n": len(rows), "by_stage": dict(Counter(classify(r) for r in rows if r["label"] == "bad"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
