"""First live asks through the M2 harness (Intent -> Retrieve -> Verify -> Safety -> Answer | Escalate) on
samples of the current `main-v4-provisional`, with the production retrieval stack on medops_v2 and the OpenAI gateway.

    python evals/harness/tools/smoke_ask.py --out evals/harness/runs/2026-09-23-smoke-ask-v1 \
        [--answer-model gpt-6-sol] [--judge-model gpt-6-luna] [--device mps] [--per-dept 5 --no-answer 3 --conflict 2]

Evidence for M2-04/05 (answers only from rechecked evidence, claim-citation structure, post-verification) and
ADR-0010/0011 (gateway, budget, judge policy). The report records outcome, reason codes, whether the cited
chunks include the sample's gold chunk (mapping), attempts, tokens, cost and latency per sample. Second human
review of the dataset is pending, so nothing here is a gate result; it is a smoke with real components.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import random
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import date

import psycopg

from medops.core.canonical import canonical_hash
from medops.core.config import Settings
from medops.core.telemetry import configure_telemetry, flush, telemetry_options
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.evals.answer_review import capture_snapshot
from medops.evals.datasets import bind_run_dataset, load_frozen_dataset, sha256_file
from medops.evals.evidence import all_required_evidence
from medops.evals.main_scoring import (
    SCORING_BINDING,
    SCORING_VERSION,
    abstention_metrics,
    bind_run_scoring,
    main_success,
    validate_expectations,
    validate_row_scoring,
)
from medops.evals.run_conditions import (
    FactGuard,
    attempt_accounting,
    bind_conditions,
    fact_snapshot,
    fact_snapshot_from_dsn,
    make_conditions,
    policy_snapshot,
    validate_attempts,
)
from medops.evals.runtime import EXIT_STALLED, with_database
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.assembly import build_retrieval
from medops.harness.dependencies import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL
from medops.harness.runtime import initial_state, run_ask
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
)
from medops.verification.verifier import VERIFIER_VERSION

REPO = pathlib.Path(__file__).resolve().parents[3]
DATASET = REPO / "evals/main_set/main-v4-provisional"  # default; --dataset can pin a historical frozen version
MAPPING = REPO / "evals/experiments/e2e/main-v4-provisional/chunk_mapping.chunker-v2.main-v4-provisional.json"


def mapping_for(dataset: pathlib.Path) -> pathlib.Path:
    """The gold -> chunk mapping published for a frozen main-set version (medops.evals.probe.chunk_mapping)."""
    return REPO / "evals/experiments/e2e" / dataset.name / f"chunk_mapping.chunker-v2.{dataset.name}.json"


def _mps_empty_cache() -> None:
    import torch

    torch.mps.empty_cache()


def pick_samples(
    rng: random.Random,
    per_dept: int,
    no_answer: int,
    conflict: int,
    *,
    everything: bool = False,
    dataset: pathlib.Path = DATASET,
) -> list[dict]:
    samples = [
        json.loads(line)
        for line in (dataset / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if everything:
        return samples
    new = [s for s in samples if s["sample_id"].startswith("ms-")]
    chosen: list[dict] = []
    for dept in ("MA", "PV", "CO"):
        pool = [
            s
            for s in new
            if s["dept"] == dept and s.get("answerable", True) and not s.get("conflict") and not s.get("derived_from")
        ]
        chosen += rng.sample(pool, min(per_dept, len(pool)))
    na_pool = [s for s in new if s.get("answerable", True) is False]
    chosen += na_pool if no_answer < 0 else rng.sample(na_pool, min(no_answer, len(na_pool)))
    chosen += rng.sample([s for s in new if s.get("conflict") and not s.get("derived_from")], conflict)
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument(
        "--dataset", type=pathlib.Path, default=DATASET, help="frozen main-set directory (default main-v4-provisional)"
    )
    ap.add_argument(
        "--mapping",
        type=pathlib.Path,
        default=None,
        help="gold->chunk mapping; default evals/experiments/e2e/<dataset>/chunk_mapping.chunker-v2.<dataset>.json",
    )
    ap.add_argument("--answer-model", default=PRODUCTION_ANSWER_MODEL)
    ap.add_argument("--judge-model", default=PRODUCTION_JUDGE_MODEL)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--database", default="medops_v2")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 23))
    ap.add_argument("--per-dept", type=int, default=5)
    ap.add_argument("--no-answer", type=int, default=3, help="-1 = every no-answer sample")
    ap.add_argument("--conflict", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--all", action="store_true", help="run every sample of the dataset (614)")
    ap.add_argument("--resume", action="store_true", help="continue an existing run directory from its rows.jsonl")
    ap.add_argument(
        "--released",
        action="store_true",
        help="apply the policies released in the target database (retrieval params, glossary, translation); default: repository constants",
    )
    ap.add_argument("--ids", default="", help="comma-separated sample ids to run (overrides the sampling options)")
    ap.add_argument("--gpu-timeout", type=float, default=120.0, help="seconds a single embedding/rerank call may take")
    ap.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="hard cap for model charges in this invocation; checked before every provider call",
    )
    ap.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=10,
        help="exit 76 after this many system_failure samples in a row (provider outage); the supervisor resumes later",
    )
    args = ap.parse_args()
    if args.max_cost_usd is not None and args.max_cost_usd <= 0:
        ap.error("--max-cost-usd must be positive")
    if args.out.exists() and not args.resume:
        raise SystemExit("refusing to overwrite an existing run directory (pass --resume to continue it)")
    dataset_manifest = load_frozen_dataset(args.dataset, expected_id="precise_clause_main")
    validate_expectations(
        [
            {"kind": "no_answer", "expected_behaviour": s["expected_behaviour"]}
            for s in (
                json.loads(line)
                for line in (args.dataset / "samples.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if not s.get("answerable", True)
        ]
    )
    bind_run_dataset(args.out, dataset_manifest)
    bind_run_scoring(args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "rows.jsonl"
    done_rows: dict[str, dict] = {}
    attempts: list[dict] = []
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                validate_row_scoring([r])
                attempts.append(r)
                done_rows[r["sample_id"]] = r
    redo = {sid for sid, r in done_rows.items() if "system_failure" in r["reason_codes"]}
    settings = Settings()
    configure_telemetry(**telemetry_options(settings))
    if settings.database_admin_url is None:
        print("DATABASE_ADMIN_URL is needed for the retrieval preflight", file=sys.stderr)
        return 2
    from medops.retrieval.integrity import require_retrieval_integrity

    app_dsn = with_database(settings.database_url.get_secret_value(), args.database)
    conn = psycopg.connect(app_dsn, connect_timeout=5)
    try:
        admin_dsn_value = with_database(settings.database_admin_url.get_secret_value(), args.database)
        with psycopg.connect(
            admin_dsn_value,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        ) as admin_conn:
            admin_conn.read_only = True
            admin_conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            index_preflight = require_retrieval_integrity(admin_conn, plane=args.database, request_conn=conn)
            facts = fact_snapshot(admin_conn)
        conn.rollback()
    except Exception:
        conn.close()
        raise
    from medops.evals.preflight import save_preflight

    preflight_reference = save_preflight(args.out, {args.database: index_preflight})
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    gpu = PinnedThread(args.gpu_timeout)
    provider = PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    from medops.application.policy_loader import ReleasedPolicySet, load_released

    released = load_released(conn) if args.released else ReleasedPolicySet.empty()
    conn.rollback()
    rerank_output = released.rerank_output(RERANK_OUTPUT)
    reranker = PinnedReranker(gpu.call(lambda: BgeRerankerV2M3(device=args.device, output=rerank_output)), gpu)
    as_of = args.as_of

    @contextmanager
    def conn_for_user(user: UserContext):
        with conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
            yield conn

    def doc_titles(user: UserContext, doc_ids) -> dict[str, str]:
        from medops.retrieval.doc_focus import load_titles

        with conn_for_user(user) as c:
            return load_titles(c, doc_ids)

    budgeted_gateway = build_budgeted_gateway(settings, run_cap_usd=args.max_cost_usd)
    gateway = MeteredGateway(budgeted_gateway)
    from medops.retrieval.glossary_store import load_versioned_glossary
    from medops.retrieval.query_translation import QueryTranslator

    translation = released.query_translation()
    retrieval = build_retrieval(
        conn_for_user=conn_for_user,
        as_of=as_of,
        provider=provider,
        reranker=reranker,
        config=released.hybrid_config(production_hybrid_config()),
        glossary=load_versioned_glossary(settings.glossary_dir or REPO / "evals/glossary", released.glossary_version()),
        multi_query=released.multi_query(),
        doc_focus=released.doc_focus(),
        source_constraint=released.source_constraint(),
        translator=QueryTranslator(gateway, translation).translate if translation != "off" else None,
    )
    deps = HarnessDeps(
        retrieval=retrieval,
        gateway=gateway,
        answer_model_id=args.answer_model,
        judge_model_id=args.judge_model,
        as_of=as_of,
        evidence_focus=released.evidence_focus(),
        sentence_scorer=reranker.score,
        doc_titles=doc_titles,
        answer_model_by_intent=released.answer_models(),
        answer_system=released.answer_system(ANSWER_SYSTEM),
    )
    from medops.retrieval.production import production_retrieval_inputs
    from medops.retrieval.versioning import compute_retrieval_version

    versions = VersionSet(
        policy_version=released.policy_version("policy-m2-smoke-1"),
        retrieval_version=(
            compute_retrieval_version(
                production_retrieval_inputs(
                    released.hybrid_config(production_hybrid_config()),
                    rerank_output=rerank_output,
                    glossary_version=released.glossary_version(),
                    multi_query=released.multi_query(),
                    doc_focus=released.doc_focus(),
                    source_constraint=released.source_constraint(),
                    query_translation=translation,
                )
            )
            if args.released
            else PRODUCTION_RETRIEVAL_VERSION
        ),
        model_config_version=f"answer={args.answer_model};judge={args.judge_model};{VERIFIER_VERSION}"
        + released.model_config_suffix(),
    )
    mapping_path = args.mapping or mapping_for(args.dataset)
    mapping_doc = json.loads(mapping_path.read_text(encoding="utf-8"))
    if mapping_doc.get("dataset_hash") != dataset_manifest.get("dataset_hash"):
        print(
            f"mapping {mapping_path.name} was built for another dataset_hash than {args.dataset.name}", file=sys.stderr
        )
        return 2
    mapping = {e["gold_id"]: e for e in mapping_doc["entries"]}
    samples = pick_samples(
        random.Random(args.seed),
        args.per_dept,
        args.no_answer,
        args.conflict,
        everything=args.all,
        dataset=args.dataset,
    )
    if args.ids:
        wanted = {sid.strip() for sid in args.ids.split(",") if sid.strip()}
        samples = [
            s
            for s in pick_samples(random.Random(args.seed), 0, 0, 0, everything=True, dataset=args.dataset)
            if s["sample_id"] in wanted
        ]
        missing = wanted - {s["sample_id"] for s in samples}
        if missing:
            raise SystemExit(f"unknown sample ids: {sorted(missing)}")
    conditions = make_conditions(
        root=REPO,
        runner=pathlib.Path(__file__),
        samples=samples,
        versions=versions.model_dump(mode="json"),
        facts={args.database: {"database_identity": index_preflight["database_identity"], **facts}},
        configuration={
            "as_of": args.as_of.isoformat(),
            "device": args.device,
            "gpu_timeout_s": args.gpu_timeout,
            "released": args.released,
            "monthly_budget_usd": settings.llm_monthly_budget_usd,
            "policy_snapshot": policy_snapshot(released),
            "answer_system_sha256": hashlib.sha256(deps.answer_system.encode()).hexdigest(),
        },
        inputs={
            "dataset_hash": dataset_manifest["dataset_hash"],
            "dataset_version": dataset_manifest["dataset_version"],
            "mapping_sha256": sha256_file(mapping_path),
            "scoring": SCORING_BINDING,
        },
    )
    conditions_hash = bind_conditions(args.out, conditions)
    validate_attempts(attempts, conditions)
    fact_guard = FactGuard(
        {args.database: facts},
        {args.database: lambda: fact_snapshot_from_dsn(admin_dsn_value)},
    )
    fact_guard.check(force=True)
    consecutive_failures = 0
    if done_rows:
        print(f"resuming: {len(done_rows) - len(redo)} rows kept, {len(redo)} system_failure rows redone", flush=True)
    for s in samples:
        if s["sample_id"] in done_rows and s["sample_id"] not in redo:
            continue
        fact_guard.check()
        user = UserContext(
            user_id=hashlib.sha256(f"smoke:{s['sample_id']}".encode()).hexdigest()[:16],
            dept=Dept(s["dept"]),
            roles=("analyst",),
            acl_scopes=frozenset({f"{s['dept']}:read"}),
        )
        state = initial_state(user=user, query=s["query"], versions=versions)
        before = (gateway.cost_usd, gateway.tokens, gateway.calls)
        t0 = time.perf_counter()
        run = run_ask(state, deps)
        latency = time.perf_counter() - t0
        gold_chunks: set[str] = set()
        gold_groups: list[list[str]] = []
        for g in s.get("required_gold_evidence", []):
            entry = mapping.get(g["gold_id"])
            group = list(entry["chunk_ids"]) if entry and entry["status"] == "mapped" else []
            gold_groups.append(group)
            if entry and entry["status"] == "mapped":
                gold_chunks.update(entry["chunk_ids"])
        cited = [c.chunk_id for c in run.state.answer.citations] if run.state.answer else []
        row = {
            "attempt_id": str(uuid.uuid4()),
            "trace_id": run.state.trace_id,
            "observed_at": dt.datetime.now(dt.UTC).isoformat(),
            "run_conditions_sha256": conditions_hash,
            "scoring_version": SCORING_VERSION,
            **capture_snapshot(args.out, s, run.state, run.outcome, conn_for_user),
            "sample_input_sha256": canonical_hash(s),
            "versions": versions.model_dump(mode="json"),
            "expected_behaviour": s.get("expected_behaviour"),
            "sample_id": s["sample_id"],
            "dept": s["dept"],
            "kind": "no_answer"
            if s.get("answerable", True) is False
            else ("conflict" if s.get("conflict") else "answerable"),
            "imported": s["sample_id"].startswith("pc-"),
            "derived": bool(s.get("derived_from")),
            "language": s.get("language"),
            "slices": s["slices"],
            "query": s["query"],
            "outcome": run.outcome,
            "reason_codes": [c.value for c in run.state.escalation.reason_codes] if run.state.escalation else [],
            "escalation_detail": run.state.escalation.detail[:200] if run.state.escalation else "",
            "claims": [c.text for c in run.state.answer.claims] if run.state.answer else [],
            "cited_chunks": cited,
            "gold_chunks": sorted(gold_chunks),
            "required_gold_groups": gold_groups,
            "evidence_rule": "gold-groups-v1",
            "gold_cited": all_required_evidence(gold_groups, cited),
            "evidence_count": len(run.state.evidence),
            "evidence_chunks": [e.citation.chunk_id for e in run.state.evidence],
            "flagged_evidence": list(run.flagged_evidence),
            "verify_elements": [
                {
                    "kind": e.kind.value,
                    "verdict": e.verdict.value,
                    "text": e.text[:160],
                    "chunk": e.evidence_chunk_id,
                    "reason": e.reason[:120],
                }
                for e in (run.state.verify_result.elements if run.state.verify_result else ())
            ],
            "attempts": [f"{a.node}:{a.outcome}" for a in run.attempts],
            "tokens_used": run.state.budget.used,
            "model_calls": gateway.calls - before[2],
            "model_tokens": gateway.tokens - before[1],
            "cost_usd": round(gateway.cost_usd - before[0], 6),
            "latency_s": round(latency, 2),
        }
        row["success"] = main_success(row, row["outcome"], cited, row["reason_codes"])
        done_rows[row["sample_id"]] = row
        attempts.append(row)
        with rows_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"{s['sample_id']} [{row['kind']}] -> {run.outcome} {row['reason_codes']} gold_cited={row['gold_cited']} calls={row['model_calls']} ${row['cost_usd']:.4f} {latency:.1f}s",
            flush=True,
        )
        consecutive_failures = consecutive_failures + 1 if "system_failure" in row["reason_codes"] else 0
        if consecutive_failures >= args.max_consecutive_failures:
            fact_guard.check(force=True)
            print(
                f"{consecutive_failures} consecutive system failures (provider outage?): exiting 76 for the supervisor to resume later",
                flush=True,
            )
            conn.close()
            os._exit(76)
        if args.max_cost_usd is not None and budgeted_gateway.run_cap_blocked:
            fact_guard.check(force=True)
            print(f"run cost cap {args.max_cost_usd} USD reached: exiting 77 (resume with authorization)", flush=True)
            conn.close()
            return 77
        if gpu.stalled:
            fact_guard.check(force=True)
            print(
                f"gpu stalled beyond {args.gpu_timeout}s: exiting {EXIT_STALLED} for the supervisor to resume",
                flush=True,
            )
            conn.close()
            os._exit(EXIT_STALLED)
        if args.device == "mps":
            gpu.call(_mps_empty_cache)
    fact_guard.check(force=True)
    conn.close()
    rows = [done_rows[s["sample_id"]] for s in samples if s["sample_id"] in done_rows]
    answerable = [r for r in rows if r["kind"] == "answerable"]
    accounting = attempt_accounting(attempts)
    summary = {
        "run_conditions_sha256": conditions_hash,
        "fact_guard_checks": fact_guard.checks,
        "attempt_accounting": accounting,
        "preflight_reference": preflight_reference,
        "index_preflight": index_preflight,
        "scoring": SCORING_BINDING,
        "abstention_metrics": abstention_metrics(rows),
        "run": args.out.name,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "dataset": {
            "version": dataset_manifest["dataset_version"],
            "dataset_hash": dataset_manifest.get("dataset_hash"),
            "second_human_review": dataset_manifest.get("second_human_review", {}).get("status", "pending"),
        },
        "versions": versions.model_dump(),
        "n": len(rows),
        "answer_review_capture": {
            "captured": sum(bool(r.get("answer_review_input")) for r in rows),
            "missing": sum(not r.get("answer_review_input") for r in rows),
            "status": "pending_separate_semantic_review",
        },
        "answered": sum(r["outcome"] == "answered" for r in rows),
        "answerable_answered_rate": round(
            sum(r["outcome"] == "answered" for r in answerable) / max(1, len(answerable)), 3
        ),
        "answerable_gold_cited_rate": round(sum(r["gold_cited"] for r in answerable) / max(1, len(answerable)), 3),
        "no_answer_abstained_rate": round(
            sum(r["success"] for r in rows if r["kind"] == "no_answer")
            / max(1, sum(1 for r in rows if r["kind"] == "no_answer")),
            3,
        ),
        "answerable_false_abstention_rate": round(
            sum(r["outcome"] == "escalated" and set(r["reason_codes"]) == {"insufficient_evidence"} for r in answerable)
            / max(1, len(answerable)),
            3,
        ),
        "conflict_answered_with_gold": [r["gold_cited"] for r in rows if r["kind"] == "conflict"],
        "total_cost_usd": accounting["cost_usd"],
        "run_cost_cap_usd": args.max_cost_usd,
        "total_model_calls": accounting["model_calls"],
        "retained_outcome_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
        "mean_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 2),
        "p95_latency_s": sorted(r["latency_s"] for r in rows)[int(0.95 * (len(rows) - 1))],
        "reason_code_counts": {},
        "rows": rows,
    }
    for r in rows:
        for c in r["reason_codes"]:
            summary["reason_code_counts"][c] = summary["reason_code_counts"].get(c, 0) + 1
    (args.out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Harness smoke `{args.out.name}` ({dataset_manifest['dataset_version']}, second human review {summary['dataset']['second_human_review']})",
        "",
        f"- samples {summary['n']} · answered {summary['answered']} · answerable answered {summary['answerable_answered_rate']} · gold cited among answerable {summary['answerable_gold_cited_rate']} · no-answer abstained {summary['no_answer_abstained_rate']} · false abstention on answerable {summary['answerable_false_abstention_rate']} · cost ${summary['total_cost_usd']} · calls {summary['total_model_calls']} · mean latency {summary['mean_latency_s']}s · p95 {summary['p95_latency_s']}s",
        f"- scoring {SCORING_VERSION}; detailed abstention numerators/denominators in results.json",
        f"- answer model {args.answer_model} · judge {args.judge_model} · {VERIFIER_VERSION} · retrieval {PRODUCTION_RETRIEVAL_VERSION[:12]}…",
        "",
        "| sample | kind | dept | outcome | reason codes | gold cited | claims | calls | cost | latency |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['sample_id']} | {r['kind']} | {r['dept']} | {r['outcome']} | {', '.join(r['reason_codes']) or '—'} | {'yes' if r['gold_cited'] else ('—' if r['kind'] == 'no_answer' else 'no')} | {len(r['claims'])} | {r['model_calls']} | ${r['cost_usd']:.4f} | {r['latency_s']}s |"
        )
    lines.append("")
    (args.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "n",
                    "answered",
                    "answerable_answered_rate",
                    "answerable_gold_cited_rate",
                    "no_answer_abstained_rate",
                    "answerable_false_abstention_rate",
                    "total_cost_usd",
                    "mean_latency_s",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        flush()
