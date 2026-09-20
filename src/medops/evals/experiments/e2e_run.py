"""End-to-end retrieval run (baseline M1-21; ADR-0002 amendment 3; ADR-0007): lexical candidate + bge-m3
vector channel fused by RRF, fact-plane re-check under the application role, strict macro Recall@5 on the
re-checked top 5, reported per gate scope, department and slice, with Hit@5, fused Recall@20, dropped
candidates by reason, the invalid-version citation rate, latency, reproducibility and an admin-side leak
check. Two systems can be compared with the pre-registered paired bootstrap.

Same discipline as the DEC-001/DEC-002 harnesses: a frozen run_manifest before any query, seeded pass order,
warm-up excluded from latency, each query in its own identity-bound transaction on one ordinary-role
connection. The reranker of ADR-0007 is not part of this run (rerank_params empty); the gate is defined on
the fact-rechecked top 5.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg

from medops.core.canonical import canonical_json
from medops.evals.experiments import scoring
from medops.evals.experiments.dec001_run import (
    CROSS_LINGUAL,
    LANGUAGE_MATCHED,
    MIN_SLICE_SUPPORT,
    SLICES,
    Query,
    QueryOutcome,
    _git_head,
    _sha256,
    _with_database,
    leak_check,
    load_mapping,
    load_queries,
    make_retriever,
    resolve_servers,
)
from medops.evals.experiments.dec001_run import server_facts as lexical_facts
from medops.evals.experiments.dec002_run import server_facts as vector_facts
from medops.retrieval.hybrid import HybridConfig, retrieve_evidence
from medops.retrieval.rerank import Reranker, rerank_evidence
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.embedding import EmbeddingProvider

RECALL_AT = 5
GATE_RECALL_AT_5 = 0.85  # baseline M1-21
DEPTS = ("MA", "PV", "CO")


@dataclass
class E2EOutcome:
    sample_id: str
    dept: str
    fused: list[list[str]] = field(default_factory=list)  # per pass, fused top-N before recheck
    accepted: list[list[str]] = field(default_factory=list)  # per pass, rechecked in rank order
    lexical_top: list[str] = field(default_factory=list)
    vector_top: list[str] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    non_current_in_top5: int = 0
    reranked: list[list[str]] = field(default_factory=list)  # per pass, reranker output order (when enabled)
    latencies_ns: list[int] = field(default_factory=list)


def _rerank_label(manifest: Mapping[str, Any]) -> str:
    params = manifest["measurement"].get("rerank_params") or {}
    return f"rerank ({params.get('model_id')}, top {params.get('output')}) then " if params else ""


def _relative(path: Path, repo: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(repo.resolve())) if resolved.is_relative_to(repo.resolve()) else str(path)


def _recall(ranked: Sequence[str], required: Sequence[str]) -> float:
    return scoring.strict_recall(ranked, required)


def run_system(
    *,
    system: str,
    lexical_candidate: str,
    app_dsn: str,
    provider: EmbeddingProvider,
    queries: Sequence[Query],
    config: HybridConfig,
    as_of: date,
    warmup: int,
    measured: int,
    seed: int,
    reranker: Reranker | None = None,
) -> dict[str, E2EOutcome]:
    outcomes = {q.sample_id: E2EOutcome(q.sample_id, q.dept) for q in queries}
    by_id = {q.sample_id: q for q in queries}
    ids = sorted(by_id)
    expected: dict[str, Any] = {}
    with psycopg.connect(app_dsn) as conn:
        for pass_index in range(warmup + measured):
            order = list(ids)
            random.Random(seed + pass_index).shuffle(order)
            for sid in order:
                q = by_id[sid]
                start = time.perf_counter_ns()
                with conn.transaction():
                    conn.execute("select set_config('medops.dept', %s, true)", (q.dept,))
                    lexical = make_retriever(lexical_candidate, conn, as_of)
                    vector = pg_vector.PgVectorRetriever(conn, provider, as_of=as_of)
                    if "lex" not in expected:
                        expected["lex"] = lexical.configured
                        expected["vec"] = vector.configured
                    hybrid, rechecked = retrieve_evidence(
                        conn,
                        lexical,
                        vector,
                        q.query,
                        config=config,
                        lexical_expected=expected["lex"],
                        vector_expected=expected["vec"],
                        as_of=as_of,
                    )
                    ranked_ids: list[str] = []
                    if reranker is not None:
                        ranked = rerank_evidence(reranker, q.query, rechecked.evidence[: reranker.spec.max_input])
                        ranked_ids = [r.evidence.citation.chunk_id for r in ranked]
                elapsed = time.perf_counter_ns() - start
                out = outcomes[sid]
                out.fused.append(hybrid.fused_ids)
                out.accepted.append(list(rechecked.accepted_ids))
                if reranker is not None:
                    out.reranked.append(ranked_ids)
                out.lexical_top = [c.chunk_id for c in hybrid.lexical.candidates]
                out.vector_top = [c.chunk_id for c in hybrid.vector.candidates]
                out.dropped = {}
                for rej in rechecked.rejected:
                    out.dropped[rej.reason.value] = out.dropped.get(rej.reason.value, 0) + 1
                final = ranked_ids if reranker is not None else list(rechecked.accepted_ids)
                evidence_by_id = {e.citation.chunk_id: e for e in rechecked.evidence}
                out.non_current_in_top5 = sum(
                    1
                    for cid in final[:RECALL_AT]
                    if evidence_by_id[cid].status.value != "active" or evidence_by_id[cid].historical
                )
                if pass_index >= warmup:
                    out.latencies_ns.append(elapsed)
    return outcomes


def summarize(
    system: str, queries: Sequence[Query], outcomes: Mapping[str, E2EOutcome], mapping: Mapping[str, list[str]]
) -> dict[str, Any]:
    per5: dict[str, float] = {}
    hit5: dict[str, float] = {}
    per20: dict[str, float] = {}
    lex5: dict[str, float] = {}
    vec5: dict[str, float] = {}
    rows = []
    not_reproducible = []
    for q in queries:
        out = outcomes[q.sample_id]
        required = ["|".join(mapping.get(g, [])) for g in q.gold_ids]
        final = out.reranked[0] if out.reranked else out.accepted[0]
        top5 = final[:RECALL_AT]
        per5[q.sample_id] = _recall(top5, required)
        hit5[q.sample_id] = 1.0 if per5[q.sample_id] > 0 else 0.0
        per20[q.sample_id] = _recall(out.fused[0], required)
        lex5[q.sample_id] = _recall(out.lexical_top[:RECALL_AT], required)
        vec5[q.sample_id] = _recall(out.vector_top[:RECALL_AT], required)
        if not (
            scoring.rankings_identical(out.fused)
            and scoring.rankings_identical(out.accepted)
            and (not out.reranked or scoring.rankings_identical(out.reranked))
        ):
            not_reproducible.append(q.sample_id)
        rows.append(
            {
                "sample_id": q.sample_id,
                "dept": q.dept,
                "slices": list(q.slices),
                "gold_script": q.gold_script,
                "language": q.language,
                "scope": q.scope,
                "recall_at_5": per5[q.sample_id],
                "rechecked_recall_at_5_before_rerank": _recall(out.accepted[0][:RECALL_AT], required),
                "hit_at_5": hit5[q.sample_id],
                "fused_recall_at_20": per20[q.sample_id],
                "lexical_only_recall_at_5": lex5[q.sample_id],
                "vector_only_recall_at_5": vec5[q.sample_id],
                "dropped_by_recheck": out.dropped,
                "non_current_in_top5": out.non_current_in_top5,
                "latency_ms_measured": [round(ns / 1e6, 3) for ns in out.latencies_ns],
                "unmappable_golds": [g for g in q.gold_ids if not mapping.get(g)],
            }
        )

    def group(per: Mapping[str, float], labels: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
        return [g.__dict__ for g in scoring.grouped_recall(per, labels, min_support=MIN_SLICE_SUPPORT)]

    def block(subset: Sequence[Query]) -> dict[str, Any]:
        sids = [q.sample_id for q in subset]
        return {
            "queries": len(subset),
            "recall_at_5": scoring.macro_mean([per5[s] for s in sids]),
            "hit_at_5": scoring.macro_mean([hit5[s] for s in sids]),
            "fused_recall_at_20": scoring.macro_mean([per20[s] for s in sids]),
            "lexical_only_recall_at_5": scoring.macro_mean([lex5[s] for s in sids]),
            "vector_only_recall_at_5": scoring.macro_mean([vec5[s] for s in sids]),
            "by_department": group(per5, {d: [q.sample_id for q in subset if q.dept == d] for d in DEPTS}),
            "by_slice": group(per5, {sl: [q.sample_id for q in subset if sl in q.slices] for sl in SLICES}),
            "by_gold_script": group(per5, _by_script(subset)),
            "sample_ids": sids,
        }

    frozen = [q for q in queries if not q.provisional]
    latencies = [ns / 1e6 for out in outcomes.values() for ns in out.latencies_ns]
    total_top5 = sum(
        min(RECALL_AT, len(out.reranked[0] if out.reranked else out.accepted[0])) for out in outcomes.values()
    )
    non_current = sum(out.non_current_in_top5 for out in outcomes.values())
    dropped_total: dict[str, int] = {}
    for out in outcomes.values():
        for k, v in out.dropped.items():
            dropped_total[k] = dropped_total.get(k, 0) + v
    return {
        "system": system,
        "queries": len(queries),
        "all": block(frozen),
        "scopes": {
            LANGUAGE_MATCHED: block([q for q in frozen if q.scope == LANGUAGE_MATCHED]),
            CROSS_LINGUAL: block([q for q in frozen if q.scope == CROSS_LINGUAL]),
        },
        "invalid_version_citation_rate": (non_current / total_top5) if total_top5 else 0.0,
        "top5_evidence_total": total_top5,
        "dropped_by_recheck_total": dropped_total,
        "not_reproducible_queries": not_reproducible,
        "latency_ms": {
            "measured_executions": len(latencies),
            "p95": scoring.p95_nearest_rank(latencies) if latencies else None,
            "mean": scoring.macro_mean(latencies),
            "max": max(latencies) if latencies else None,
        },
        "per_query": rows,
        "_per_query_recall_at_5": per5,
    }


def _by_script(subset: Sequence[Query]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for q in subset:
        labels.setdefault(q.gold_script, []).append(q.sample_id)
    return labels


def gate_view(summary: Mapping[str, Any]) -> dict[str, Any]:
    all_block, lm = summary["all"], summary["scopes"][LANGUAGE_MATCHED]
    depts = {g["label"]: g["recall"] for g in all_block["by_department"]}
    checks = {
        "recall_at_5_all_ge_0.85": (all_block["recall_at_5"] or 0.0) >= GATE_RECALL_AT_5,
        "recall_at_5_language_matched_ge_0.85": (lm["recall_at_5"] or 0.0) >= GATE_RECALL_AT_5,
        "invalid_version_citation_rate_zero": summary["invalid_version_citation_rate"] == 0.0,
        "reproducible": not summary["not_reproducible_queries"],
        "zero_leaks": not summary.get("leak_violations"),
    }
    return {
        "recall_at_5_all": all_block["recall_at_5"],
        "recall_at_5_language_matched": lm["recall_at_5"],
        "recall_at_5_cross_lingual": summary["scopes"][CROSS_LINGUAL]["recall_at_5"],
        "recall_at_5_by_department": depts,
        "checks": checks,
        "passes_probe_scale_gate": all(checks.values()),
        "note": "probe-scale evidence (107 samples); the M1-21 gate is finally decided on the >=300-sample main set (M1-20)",
    }


def write_report(out_dir: Path, manifest: Mapping[str, Any], results: Mapping[str, Any]) -> None:
    lines = [
        f"# End-to-end retrieval run `{manifest['run_id']}`",
        "",
        f"Dataset {manifest['dataset']['version']} `{manifest['dataset']['dataset_hash'][:12]}…` · as_of {manifest['measurement']['as_of']} · "
        f"RRF k={manifest['measurement']['rrf_k']} · channel k={manifest['measurement']['k_lexical']}/{manifest['measurement']['k_vector']} · "
        f"fused limit {manifest['measurement']['fused_limit']} · recheck then "
        + _rerank_label(manifest)
        + f"top {RECALL_AT}",
        "",
        "## Strict macro Recall@5 after fact re-check",
        "",
        "| system | all (n) | language_matched | cross_lingual | Hit@5 all | fused Recall@20 all | lexical-only R@5 | vector-only R@5 | P95 ms | gate (probe scale) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for system, s in sorted(results["systems"].items()):
        g = results["gates"][system]
        a = s["all"]
        lines.append(
            f"| {system} | {a['recall_at_5']:.3f} ({a['queries']}) | {s['scopes'][LANGUAGE_MATCHED]['recall_at_5']:.3f} | "
            f"{s['scopes'][CROSS_LINGUAL]['recall_at_5']:.3f} | {a['hit_at_5']:.3f} | {a['fused_recall_at_20']:.3f} | "
            f"{a['lexical_only_recall_at_5']:.3f} | {a['vector_only_recall_at_5']:.3f} | {s['latency_ms']['p95']:.1f} | "
            f"{'pass' if g['passes_probe_scale_gate'] else 'fail'} |"
        )
    lines += ["", "## By department and slice (Recall@5, all frozen samples)", ""]
    for system, s in sorted(results["systems"].items()):
        lines.append(f"### {system}")
        lines.append("")
        lines.append("| group | n | Recall@5 |")
        lines.append("| --- | ---: | ---: |")
        for g in s["all"]["by_department"] + s["all"]["by_slice"] + s["all"]["by_gold_script"]:
            shown = (
                ""
                if g["recall"] is None
                else f"{g['recall']:.3f}" + (" (diagnostic: n < 8)" if g["diagnostic_only"] else "")
            )
            lines.append(f"| {g['label']} | {g['support']} | {shown} |")
        lines.append("")
        lines.append(
            f"- invalid-version citations in top 5: {s['invalid_version_citation_rate']:.4f} of {s['top5_evidence_total']} · "
            f"dropped by re-check: {json.dumps(s['dropped_by_recheck_total'], ensure_ascii=False)} · "
            f"leaks: {len(s.get('leak_violations', []))} · non-reproducible: {len(s['not_reproducible_queries'])}"
        )
        lines.append("")
    if results.get("paired"):
        lines += ["## Paired bootstrap on Recall@5 (all frozen samples)", ""]
        for label, d in results["paired"].items():
            lines.append(
                f"- {label}: {d['point']:+.2f} pp, {int(d['level'] * 100)}% CI [{d['ci_low']:+.2f}, {d['ci_high']:+.2f}] ({d['resamples']} resamples)"
            )
        lines.append("")
    lines.append(f"run_manifest sha256: `{results['run_manifest_sha256']}`")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    repo: Path,
    dataset_dir: Path,
    out_dir: Path,
    systems: Mapping[str, dict[str, Any]],  # system id -> {lexical, app_dsn, admin_dsn, mapping_path}
    provider: EmbeddingProvider,
    plan: Mapping[str, Any],
    config: HybridConfig,
    as_of: date,
    warmup: int,
    measured: int,
    seed: int,
    device: str,
    purpose: str,
    reranker: Reranker | None = None,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite an existing run directory: {out_dir}")
    manifest_in = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest_in.get("status") != "frozen":
        raise RuntimeError("dataset is not frozen")
    queries = load_queries(dataset_dir)
    systems_manifest = {}
    for sid, sys_ in sorted(systems.items()):
        mapping = json.loads(Path(sys_["mapping_path"]).read_text(encoding="utf-8"))
        if mapping["dataset_hash"] != manifest_in["dataset_hash"]:
            raise RuntimeError(f"{sid}: mapping dataset_hash differs from the frozen dataset")
        systems_manifest[sid] = {
            "lexical_candidate": sys_["lexical"],
            "server": f"{urlsplit(sys_['admin_dsn']).hostname}:{urlsplit(sys_['admin_dsn']).port or 5432}",
            "database": urlsplit(sys_["admin_dsn"]).path.lstrip("/"),
            "app_role_user": urlsplit(sys_["app_dsn"]).username,
            "mapping_file": _relative(Path(sys_["mapping_path"]), repo),
            "mapping_sha256": _sha256(Path(sys_["mapping_path"])),
            "lexical": lexical_facts(sys_["admin_dsn"], sys_["lexical"]),
            "vector": vector_facts(sys_["admin_dsn"], provider.spec.embedding_version),
        }
    manifest: dict[str, Any] = {
        "run_id": out_dir.name,
        "status": "frozen_before_run",
        "purpose": purpose,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "git_head": _git_head(repo),
        "protocol": [
            "docs/adr/ADR-0002-lexical-retrieval-selection.md",
            "docs/adr/ADR-0007-embedding-and-reranker-selection.md",
            "baseline M1-21",
        ],
        "dataset": {
            "version": manifest_in["dataset_version"],
            "dataset_hash": manifest_in["dataset_hash"],
            "manifest_sha256": _sha256(dataset_dir / "manifest.json"),
            "samples_sha256": _sha256(dataset_dir / "samples.jsonl"),
        },
        "measurement": {
            "as_of": as_of.isoformat(),
            "k_lexical": config.k_lexical,
            "k_vector": config.k_vector,
            "rrf_k": config.rrf_k,
            "fused_limit": config.limit,
            "recall_at": RECALL_AT,
            "gate_recall_at_5": GATE_RECALL_AT_5,
            "rerank_params": reranker.spec.rerank_params() if reranker is not None else {},
            "rerank_framework": getattr(reranker, "framework", None) if reranker is not None else None,
            "query_order": "sorted sample_id, shuffled per pass with random.Random(seed + pass_index)",
            "random_seed": seed,
            "warmup_full_passes": warmup,
            "measured_full_passes": measured,
            "latency_clock": "perf_counter_ns around lexical + vector + RRF + fact re-check in one identity transaction",
            "paired_bootstrap": {
                "resamples": plan["measurement"]["paired_bootstrap_resamples"],
                "seed": plan["measurement"]["paired_bootstrap_seed"],
                "confidence_level": plan["measurement"]["confidence_level"],
            },
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "device": device,
        },
        "provider_spec": provider.spec.model_dump(),
        "systems": systems_manifest,
    }
    out_dir.mkdir(parents=True)
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    (out_dir / "run_manifest.json").write_bytes(manifest_bytes)
    results: dict[str, Any] = {
        "run_id": out_dir.name,
        "run_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "systems": {},
        "gates": {},
    }
    per_query_by_system: dict[str, dict[str, float]] = {}
    for sid, sys_ in sorted(systems.items()):
        mapping = load_mapping(Path(sys_["mapping_path"]))
        outcomes = run_system(
            system=sid,
            lexical_candidate=sys_["lexical"],
            app_dsn=sys_["app_dsn"],
            provider=provider,
            queries=queries,
            config=config,
            as_of=as_of,
            warmup=warmup,
            measured=measured,
            seed=seed,
            reranker=reranker,
        )
        summary = summarize(sid, queries, outcomes, mapping)
        per_query_by_system[sid] = summary.pop("_per_query_recall_at_5")
        leak_input = {
            k: QueryOutcome(v.sample_id, v.dept, rankings=[v.reranked[0] if v.reranked else v.accepted[0]])
            for k, v in outcomes.items()
        }
        summary["leak_violations"] = leak_check(sys_["admin_dsn"], leak_input, as_of)
        results["systems"][sid] = summary
        results["gates"][sid] = gate_view(summary)
    results["paired"] = {}
    names = sorted(per_query_by_system)
    boot = manifest["measurement"]["paired_bootstrap"]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            diff = scoring.paired_bootstrap_difference(
                per_query_by_system[a],
                per_query_by_system[b],
                resamples=boot["resamples"],
                seed=boot["seed"],
                level=boot["confidence_level"],
            )
            results["paired"][f"{b} minus {a}"] = diff.__dict__
    results["finished_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "per_query_recall_at_5.json").write_text(
        json.dumps(per_query_by_system, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_report(out_dir, manifest, results)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end hybrid retrieval run with fact re-check (frozen manifest first)"
    )
    parser.add_argument("--dataset", type=Path, default=Path("evals/probe/precise_clause/v2"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--system",
        action="append",
        required=True,
        metavar="LEXICAL=MAPPING",
        help="e.g. A2=path/to/mapping.json (repeatable)",
    )
    parser.add_argument("--database", default="medops_v2")
    parser.add_argument("--rrf-k", type=float, default=60.0)
    parser.add_argument("--k-lexical", type=int, default=20)
    parser.add_argument("--k-vector", type=int, default=20)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--measured", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="rerank the re-checked evidence with bge-reranker-v2-m3 (ADR-0007 §4) before the top 5",
    )
    parser.add_argument("--rerank-output", type=int, default=8)
    parser.add_argument("--purpose", required=True)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[4]
    plan = json.loads(
        (repo / "evals/experiments/lexical/preparation-v1/experiment_plan.json").read_text(encoding="utf-8")
    )
    mappings: dict[str, Path] = {}
    for item in args.system:
        lexical, _, mapping = item.partition("=")
        if not lexical or not mapping:
            parser.error("--system needs LEXICAL=MAPPING")
        mappings[lexical] = Path(mapping)
    base_mappings = dict(mappings)
    for variant, base in (("A2", "A"), ("B2", "B")):
        if variant in mappings and base not in mappings:
            base_mappings[base] = mappings[variant]
    servers = resolve_servers(repo, base_mappings, plan)
    systems = {}
    for lexical, mapping in mappings.items():
        srv = servers[lexical]
        systems[f"{lexical}+V"] = {
            "lexical": lexical,
            "app_dsn": _with_database(srv.app_dsn, args.database),
            "admin_dsn": _with_database(srv.admin_dsn, args.database),
            "mapping_path": mapping,
        }
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    provider = BgeM3EmbeddingProvider(device=args.device)
    reranker = None
    if args.rerank:
        from medops.retrieval.rerank import BgeRerankerV2M3

        reranker = BgeRerankerV2M3(device=args.device, output=args.rerank_output)
    config = HybridConfig(k_lexical=args.k_lexical, k_vector=args.k_vector, rrf_k=args.rrf_k, limit=args.limit)
    results = run(
        repo=repo,
        dataset_dir=args.dataset,
        out_dir=args.out,
        systems=systems,
        provider=provider,
        plan=plan,
        config=config,
        as_of=args.as_of,
        warmup=args.warmup,
        measured=args.measured,
        seed=args.seed,
        device=args.device,
        purpose=args.purpose,
        reranker=reranker,
    )
    print(
        json.dumps(
            {sid: {k: v for k, v in g.items() if k != "note"} for sid, g in results["gates"].items()},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
