"""DEC-002 vector-channel run (ADR-0007 pre-registration): bge-m3 dense retrieval through the pgvector
adapter on the frozen probe set, reported per gate scope, department and slice, with the same discipline as
the DEC-001 harness (frozen run_manifest before any query, seeded pass order, warm-up excluded from latency,
admin-side leak check, strict recall against the server's own gold->chunk mapping).

The vector channel has no hard gate of its own; ADR-0007 pre-registers a diagnostic threshold (cross-lingual
strict macro Recall@20 >= 50%) and the end-to-end hybrid gates of baseline M1-21. Reuses the loaders, pass
executor, summariser and leak check of `dec001_run` so the numbers are computed by the same code.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg

from medops.core.canonical import canonical_json
from medops.evals.experiments.dec001_run import (
    CROSS_LINGUAL,
    LANGUAGE_MATCHED,
    MIN_SLICE_SUPPORT,
    Query,
    QueryOutcome,
    _git_head,
    _sha256,
    execute_passes,
    leak_check,
    load_mapping,
    load_queries,
    resolve_servers,
    summarize,
)
from medops.evals.safety_data import with_database
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.contracts import VectorSearchResult, VectorVersions
from medops.retrieval.vector.embedding import EmbeddingProvider

CANDIDATE = "V"
CROSS_LINGUAL_DIAGNOSTIC_THRESHOLD = 0.50  # ADR-0007 diagnostic threshold, not a hard gate


def server_facts(admin_dsn: str, embedding_version: str) -> dict[str, Any]:
    with psycopg.connect(admin_dsn) as conn:
        with conn.transaction():
            conn.execute("set transaction read only")
            version = conn.execute("show server_version").fetchone()
            exts = conn.execute("select extname, extversion from pg_extension where extname = 'vector'").fetchall()
            meta = conn.execute(
                "select model_id, model_revision, dimension, normalization, max_seq_length, framework, chunk_count, built_by, built_at "
                "from embedding_index_meta where embedding_version = %s",
                (embedding_version,),
            ).fetchone()
            docs = conn.execute(
                "select status::text, parse_quality::text, count(*) from documents group by 1, 2 order by 1, 2"
            ).fetchall()
            chunks = conn.execute("select count(*) from chunks").fetchone()
            migration = conn.execute("select version_num from alembic_version").fetchone()
            index_def = conn.execute(
                "select indexdef from pg_indexes where indexname = %s", (pg_vector.INDEX_NAME,)
            ).fetchone()
    if meta is None:
        raise RuntimeError(f"embedding index '{embedding_version}' is not built on {urlsplit(admin_dsn).hostname}")
    return {
        "postgresql": version[0] if version else None,
        "migration": migration[0] if migration else None,
        "extensions": {name: ver for name, ver in exts},
        "index": {
            "embedding_version": embedding_version,
            "model_id": meta[0],
            "model_revision": meta[1],
            "dimension": meta[2],
            "normalization": meta[3],
            "max_seq_length": meta[4],
            "framework": meta[5],
            "chunk_count": meta[6],
            "built_by": meta[7],
            "built_at": meta[8].isoformat(),
            "hnsw_index": index_def[0] if index_def else None,
        },
        "documents_by_status_quality": [{"status": s, "parse_quality": q, "count": n} for s, q, n in docs],
        "chunks": chunks[0] if chunks else None,
    }


def build_manifest(
    *,
    run_id: str,
    repo: Path,
    dataset_dir: Path,
    mapping_path: Path,
    app_dsn: str,
    admin_dsn: str,
    provider: EmbeddingProvider,
    as_of: date,
    k: int,
    warmup: int,
    measured: int,
    seed: int,
    device: str,
    purpose: str,
    plan_cache_mode: pg_vector.PlanCacheMode = "auto",
) -> dict[str, Any]:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen":
        raise RuntimeError("dataset is not frozen")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if mapping["dataset_hash"] != manifest["dataset_hash"]:
        raise RuntimeError("mapping dataset_hash differs from the frozen dataset")
    statuses = [e["status"] for e in mapping["entries"]]
    spec = provider.spec
    return {
        "run_id": run_id,
        "status": "frozen_before_run",
        "purpose": purpose,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "git_head": _git_head(repo),
        "protocol": "docs/adr/ADR-0007-embedding-and-reranker-selection.md",
        "dataset": {
            "version": manifest["dataset_version"],
            "dataset_hash": manifest["dataset_hash"],
            "manifest_sha256": _sha256(dataset_dir / "manifest.json"),
            "samples_sha256": _sha256(dataset_dir / "samples.jsonl"),
        },
        "measurement": {
            "k": k,
            "as_of": as_of.isoformat(),
            "query_order": "sorted sample_id, shuffled per pass with random.Random(seed + pass_index)",
            "random_seed": seed,
            "concurrency": 1,
            "warmup_full_passes": warmup,
            "measured_full_passes": measured,
            "latency_clock": "perf_counter_ns around run_vector_search (query embedding on the provider device + database roundtrip)",
            "p95_estimator": "nearest-rank ceil(0.95*n), warmup excluded",
            "tie_break": "cosine distance ascending, then chunk_id ascending",
            "min_slice_support": MIN_SLICE_SUPPORT,
            "cross_lingual_diagnostic_threshold": CROSS_LINGUAL_DIAGNOSTIC_THRESHOLD,
            "hnsw_query_settings": {
                "iterative_scan": "relaxed_order",
                "ef_search": "max(40, 4k) capped at 1000",
                "plan_cache_mode": plan_cache_mode,
                "force_prepared": plan_cache_mode != "auto",
            },
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "device": device,
        },
        "candidates": {
            CANDIDATE: {
                "server": f"{urlsplit(admin_dsn).hostname or 'localhost'}:{urlsplit(admin_dsn).port or 5432}",
                "database": urlsplit(admin_dsn).path.lstrip("/"),
                "app_role_user": urlsplit(app_dsn).username,
                "mapping_file": str(mapping_path.relative_to(repo))
                if mapping_path.is_relative_to(repo)
                else str(mapping_path),
                "mapping_sha256": _sha256(mapping_path),
                "mapping_counts": {"mapped": statuses.count("mapped"), "unmappable": statuses.count("unmappable")},
                "provider_spec": spec.model_dump(),
                "retriever_version": (
                    pg_vector.GENERIC_PLAN_RETRIEVER_VERSION
                    if plan_cache_mode == "force_generic_plan"
                    else (
                        pg_vector.CUSTOM_PLAN_RETRIEVER_VERSION
                        if plan_cache_mode == "force_custom_plan"
                        else pg_vector.RETRIEVER_VERSION
                    )
                ),
                **server_facts(admin_dsn, spec.embedding_version),
            }
        },
    }


def db_searcher(
    app_dsn: str,
    provider: EmbeddingProvider,
    as_of: date,
    plan_cache_mode: pg_vector.PlanCacheMode = "auto",
) -> Callable[[Query, int], VectorSearchResult]:
    conn = psycopg.connect(app_dsn)
    expected: dict[str, VectorVersions] = {}

    def search(q: Query, k: int) -> VectorSearchResult:
        with conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (q.dept,))
            retriever = pg_vector.PgVectorRetriever(
                conn,
                provider,
                as_of=as_of,
                plan_cache_mode=plan_cache_mode,
            )
            if "v" not in expected:
                expected["v"] = retriever.configured
            return run_vector_search(retriever, q.query, k, expected=expected["v"])

    search.close = conn.close  # type: ignore[attr-defined]
    return search


def plan_evidence(
    app_dsn: str,
    provider: EmbeddingProvider,
    queries: Sequence[Query],
    as_of: date,
    k: int,
    plan_cache_mode: pg_vector.PlanCacheMode = "auto",
) -> list[dict[str, Any]]:
    """Standalone EXPLAIN under each department; not EXPLAIN EXECUTE of the cached search statement."""
    out = []
    seen: set[str] = set()
    with psycopg.connect(app_dsn) as conn:
        for q in queries:
            if q.dept in seen:
                continue
            seen.add(q.dept)
            with conn.transaction():
                conn.execute("select set_config('medops.dept', %s, true)", (q.dept,))
                plan = pg_vector.PgVectorRetriever(
                    conn,
                    provider,
                    as_of=as_of,
                    plan_cache_mode=plan_cache_mode,
                ).explain(q.query, k)
            out.append(
                {
                    "sample_id": q.sample_id,
                    "dept": q.dept,
                    "method": "standalone_explain_not_cached_search_plan",
                    "plan": json.loads(plan),
                }
            )
    return out


def _table(rows: Sequence[Mapping[str, Any]], key: str) -> str:
    """Rows are `scoring.LabelledRecall` dicts; groups under the pre-registered support are marked diagnostic."""
    lines = [f"| {key} | n | strict macro Recall@20 |", "| --- | ---: | ---: |"]
    for r in rows:
        recall = r.get("recall")
        shown = "" if recall is None else f"{recall:.3f}"
        if r.get("diagnostic_only") and recall is not None:
            shown += " (diagnostic: n < 8)"
        lines.append(f"| {r['label']} | {r['support']} | {shown} |")
    return "\n".join(lines)


def write_report(out_dir: Path, manifest: Mapping[str, Any], results: Mapping[str, Any]) -> None:
    s = results["candidates"][CANDIDATE]
    scopes = s["scopes"]
    lm, cl = scopes[LANGUAGE_MATCHED], scopes[CROSS_LINGUAL]
    cross = cl["strict_macro_recall"]
    verdict = "meets" if cross is not None and cross >= CROSS_LINGUAL_DIAGNOSTIC_THRESHOLD else "below"
    md = [
        f"# DEC-002 vector channel run `{manifest['run_id']}`",
        "",
        f"Protocol: {manifest['protocol']} · dataset {manifest['dataset']['version']} `{manifest['dataset']['dataset_hash'][:12]}…` · "
        f"k={manifest['measurement']['k']} · as_of={manifest['measurement']['as_of']} · device={manifest['environment']['device']}",
        "",
        f"Provider: `{manifest['candidates'][CANDIDATE]['provider_spec']['model_id']}` @ `{manifest['candidates'][CANDIDATE]['provider_spec']['model_revision'][:12]}` "
        f"({manifest['candidates'][CANDIDATE]['provider_spec']['embedding_version']}), index chunks {manifest['candidates'][CANDIDATE]['index']['chunk_count']}",
        "",
        "## Strict macro Recall@20 by gate scope",
        "",
        "| scope | queries | Recall@20 |",
        "| --- | ---: | ---: |",
        f"| language_matched | {lm['queries']} | {lm['strict_macro_recall']:.3f} |",
        f"| cross_lingual | {cl['queries']} | {cl['strict_macro_recall']:.3f} |",
        f"| selected frozen | {s['queries']} | {s['strict_macro_recall']:.3f} |",
        "",
        f"Diagnostic threshold (ADR-0007): cross_lingual Recall@20 >= {CROSS_LINGUAL_DIAGNOSTIC_THRESHOLD:.2f} → **{verdict}** ({cross:.3f}).",
        "",
        "## language_matched by department / slice",
        "",
        _table(lm["by_department"], "department"),
        "",
        _table(lm["by_slice"], "slice"),
        "",
        "## cross_lingual by department / slice",
        "",
        _table(cl["by_department"], "department"),
        "",
        _table(cl["by_slice"], "slice"),
        "",
        "## Integrity",
        "",
        f"- leak violations: {len(s['leak_violations'])}",
        f"- non-reproducible queries: {len(s['not_reproducible_queries'])}",
        f"- candidate_exhausted queries: {s['candidate_exhausted_queries']} · zero-result queries: {s['zero_result_queries']}",
        f"- latency ms (measured passes, embedding + database): p95 {s['latency_ms']['p95']:.1f} · mean {s['latency_ms']['mean']:.1f} · max {s['latency_ms']['max']:.1f}",
        f"- run_manifest sha256: `{results['run_manifest_sha256']}`",
        "",
    ]
    selection = manifest["measurement"].get("query_selection")
    if selection:
        md.extend(
            [
                "## Query selection",
                "",
                f"- scope: {selection['scope']} · source queries: {selection['source_queries']} · "
                f"selected: {selection['selected_queries']} · excluded without gold: "
                f"{len(selection['excluded_no_gold_sample_ids'])}",
                f"- unmappable gold: {selection['unmappable_gold_policy']}",
                "- Only one pass: repeatability was not assessed."
                if manifest["measurement"]["warmup_full_passes"] + manifest["measurement"]["measured_full_passes"] < 2
                else "- Repeatability compares every saved ranking, including warmup passes.",
                "",
            ]
        )
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")


def run(
    *,
    repo: Path,
    dataset_dir: Path,
    out_dir: Path,
    mapping_path: Path,
    app_dsn: str,
    admin_dsn: str,
    provider: EmbeddingProvider,
    as_of: date,
    k: int,
    warmup: int,
    measured: int,
    seed: int,
    device: str,
    purpose: str,
    plan_cache_mode: pg_vector.PlanCacheMode = "auto",
    gold_only: bool = False,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite an existing run directory: {out_dir}")
    all_queries = load_queries(dataset_dir)
    excluded = [q.sample_id for q in all_queries if not q.gold_ids]
    if excluded and not gold_only:
        raise ValueError("vector Recall requires gold evidence for every query; use --gold-only for an explicit subset")
    queries = [q for q in all_queries if q.gold_ids]
    if not queries:
        raise ValueError("vector Recall requires at least one query with gold evidence")
    if warmup < 0 or measured < 1:
        raise ValueError("warmup must be nonnegative and measured must be positive")
    manifest = build_manifest(
        run_id=out_dir.name,
        repo=repo,
        dataset_dir=dataset_dir,
        mapping_path=mapping_path,
        app_dsn=app_dsn,
        admin_dsn=admin_dsn,
        provider=provider,
        as_of=as_of,
        k=k,
        warmup=warmup,
        measured=measured,
        seed=seed,
        device=device,
        purpose=purpose,
        plan_cache_mode=plan_cache_mode,
    )
    manifest["measurement"]["query_selection"] = {
        "scope": "gold_only" if gold_only else "all",
        "source_queries": len(all_queries),
        "selected_queries": len(queries),
        "selected_sample_ids": [q.sample_id for q in queries],
        "excluded_no_gold_sample_ids": excluded,
        "unmappable_gold_policy": "keep in the recall denominator as misses",
    }
    out_dir.mkdir(parents=True)
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    (out_dir / "run_manifest.json").write_bytes(manifest_bytes)
    results: dict[str, Any] = {
        "run_id": out_dir.name,
        "run_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "candidates": {},
    }
    mapping = load_mapping(mapping_path)
    started = time.perf_counter()
    search = db_searcher(app_dsn, provider, as_of, plan_cache_mode)
    try:
        outcomes: dict[str, QueryOutcome] = execute_passes(
            queries, search, k=k, warmup=warmup, measured=measured, seed=seed
        )
    finally:
        search.close()  # type: ignore[attr-defined]
    rankings_bytes = (canonical_json({sid: asdict(out) for sid, out in outcomes.items()}) + "\n").encode("utf-8")
    (out_dir / "rankings.json").write_bytes(rankings_bytes)
    results["rankings_sha256"] = hashlib.sha256(rankings_bytes).hexdigest()
    summary = summarize(CANDIDATE, queries, outcomes, mapping)
    per_query = summary.pop("_per_query_recall")
    summary["leak_violations"] = leak_check(admin_dsn, outcomes, as_of)
    summary["wall_seconds_all_passes"] = round(time.perf_counter() - started, 1)
    results["candidates"][CANDIDATE] = summary
    results["plan_evidence"] = plan_evidence(app_dsn, provider, queries, as_of, k, plan_cache_mode)
    results["finished_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_query_recall.json").write_text(
        json.dumps({"candidate": CANDIDATE, "k": k, "recall": per_query}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    write_report(out_dir, manifest, results)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-002 vector-channel run (frozen manifest first)")
    parser.add_argument("--dataset", type=Path, default=Path("evals/probe/precise_clause/v3"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--measured", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--mapping", type=Path, required=True, help="gold->chunk mapping of the server's database")
    parser.add_argument("--database", default="medops_v2")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--purpose", required=True)
    parser.add_argument(
        "--plan-cache-mode",
        choices=("auto", "force_generic_plan", "force_custom_plan"),
        default="auto",
        help="PostgreSQL plan policy for the vector statement; forced modes have separate retriever versions",
    )
    parser.add_argument("--gold-only", action="store_true", help="Explicitly report only queries with required gold")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[4]
    plan = json.loads(
        (repo / "evals/experiments/lexical/preparation-v1/experiment_plan.json").read_text(encoding="utf-8")
    )
    server = resolve_servers(repo, {"A": args.mapping}, plan)["A"]
    app_dsn = with_database(server.app_dsn, args.database)
    admin_dsn = with_database(server.admin_dsn, args.database)
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    provider = BgeM3EmbeddingProvider(device=args.device)
    results = run(
        repo=repo,
        dataset_dir=args.dataset,
        out_dir=args.out,
        mapping_path=args.mapping,
        app_dsn=app_dsn,
        admin_dsn=admin_dsn,
        provider=provider,
        as_of=args.as_of,
        k=args.k,
        warmup=args.warmup,
        measured=args.measured,
        seed=args.seed,
        device=args.device,
        purpose=args.purpose,
        plan_cache_mode=args.plan_cache_mode,
        gold_only=args.gold_only,
    )
    s = results["candidates"][CANDIDATE]
    print(
        json.dumps(
            {
                "run_id": results["run_id"],
                "language_matched": s["scopes"][LANGUAGE_MATCHED]["strict_macro_recall"],
                "cross_lingual": s["scopes"][CROSS_LINGUAL]["strict_macro_recall"],
                "leaks": len(s["leak_violations"]),
                "not_reproducible": len(s["not_reproducible_queries"]),
                "p95_ms": s["latency_ms"]["p95"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
