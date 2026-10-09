"""Safety-set CLI. Checks and reports live in medops.evals.safety; runtime in medops.evals.runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import uuid
from datetime import date

import psycopg

from medops.core.config import Settings
from medops.core.telemetry import configure_telemetry, flush, telemetry_options
from medops.domain.state import VersionSet
from medops.evals.datasets import bind_run_dataset, load_frozen_dataset
from medops.evals.run_conditions import (
    FactGuard,
    attempt_accounting,
    bind_conditions,
    make_conditions,
    policy_snapshot,
    validate_attempts,
)
from medops.evals.runtime import EXIT_STALLED, Plane, with_database
from medops.evals.safety import judge, report_markdown, run_sample, summarize
from medops.evals.safety_data import PRODUCTION_DB, SAFETY_DB, admin_dsn, load_drafts
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.production import (
    production_model_config_version,
)
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_retrieval_inputs,
)
from medops.retrieval.versioning import compute_retrieval_version
from medops.skills.catalog import default_registry
from medops.skills.production import doc_type_lookup, evidence_lookup

REPO = pathlib.Path(__file__).resolve().parents[3]


def rejudge(out_dir: pathlib.Path) -> int:
    """Recompute every check from the stored observations with the current drafts (expectations corrected by the
    reviewer or annotator-01) — no GPU, no model calls; admin lookups only."""
    rows_path = out_dir / "rows.jsonl"
    stored = {}
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            stored[r["sample_id"]] = r
    samples = {s["sample_id"]: s for s in load_drafts(include_withdrawn=True)}  # a stored run may hold withdrawn ids
    admins = {}

    class _AdminPlane:
        def __init__(self, name: str):
            self.name = name
            self.admin = psycopg.connect(admin_dsn(name))
            self.admin.read_only = True

        resolve_chunks = Plane.resolve_chunks
        docs_for_hashes = Plane.docs_for_hashes
        canary_chunks = Plane.canary_chunks

    rows = []
    stale: list[str] = []
    for sid, r in stored.items():
        s = samples.get(sid)
        if s is None:
            continue
        if s["query"] != r.get("query"):
            stale.append(sid)  # rewritten after the run: needs a real rerun (--only <id> --resume)
            continue
        plane = admins.setdefault(r["database"], _AdminPlane(r["database"]))
        obs = {
            k: r.get(k)
            for k in (
                "outcome",
                "reason_codes",
                "detail",
                "claims",
                "cited_chunks",
                "evidence_chunks",
                "candidates",
                "flagged_evidence",
                "historical_notice",
                "retrieval_calls",
            )
        }
        r.pop("not_exercised", None)
        r.pop("injected_retrieved", None)
        obs["output_texts"] = r.get("output_texts") or list(r.get("claims") or []) + [r.get("detail") or ""]
        checks = judge(s, obs, plane)
        r.update(
            expected=s["expected"],
            checks=checks,
            passed=all(c["ok"] for c in checks),
            failed_checks=[c["check"] for c in checks if not c["ok"]],
            slices=s.get("slices", []),
        )
        for k in ("target_cited", "injected_retrieved", "not_exercised"):
            if k in obs:
                r[k] = obs[k]
        rows.append(r)
    versions = (
        VersionSet(**rows[0]["versions"])
        if rows and rows[0].get("versions")
        else VersionSet(
            policy_version="policy-m2-smoke-1",
            retrieval_version=PRODUCTION_RETRIEVAL_VERSION,
            model_config_version=production_model_config_version(),
        )
    )
    summary = summarize(rows, versions, out_dir.name)
    summary["rejudged_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    summary["stale_rows"] = stale
    if stale:
        print(
            f"stale rows skipped (their sample input changed since this run; a resume is bound to the original "
            f"inputs, so judge them in a new run directory): {stale}",
            flush=True,
        )
    (out_dir / "results.json").write_text(
        json.dumps({**summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / "report.md").write_text(report_markdown(summary, rows), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k in ("n", "passed", "gates", "failed_checks")}, ensure_ascii=False
        )
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument(
        "--dataset",
        type=pathlib.Path,
        default=None,
        help="frozen safety-set directory (samples.jsonl + manifest.json); default: the current drafts",
    )
    ap.add_argument("--device", default="mps")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 24))
    ap.add_argument("--only", default="")
    ap.add_argument("--category", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--released",
        action="store_true",
        help="apply the policies released in the production plane (retrieval params, glossary, translation); default: repository constants",
    )
    ap.add_argument("--gpu-timeout", type=float, default=120.0)
    ap.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="hard cap for model charges in this invocation; checked before every provider call",
    )
    ap.add_argument("--max-consecutive-failures", type=int, default=10)
    ap.add_argument(
        "--rejudge",
        action="store_true",
        help="recompute checks from rows.jsonl with the current drafts; no model calls",
    )
    args = ap.parse_args()
    if args.max_cost_usd is not None and args.max_cost_usd <= 0:
        ap.error("--max-cost-usd must be positive")
    if args.rejudge:
        previous = args.out / "results.json"
        previous_dataset = (json.loads(previous.read_text()).get("dataset") or {}) if previous.exists() else {}
        if (
            args.dataset
            or (args.out / "dataset_binding.json").exists()
            or (args.out / "run_conditions.json").exists()
            or previous_dataset.get("dataset_hash")
        ):
            raise SystemExit(
                "rejudge cannot overwrite a frozen-dataset or runtime-bound run; create a separate diagnostic"
            )
        return rejudge(args.out)
    if args.out.exists() and not args.resume:
        raise SystemExit("refusing to overwrite an existing run directory (pass --resume)")
    frozen = load_frozen_dataset(args.dataset, expected_id="safety_set") if args.dataset else None
    if frozen is not None:
        bind_run_dataset(args.out, frozen)
    elif (args.out / "dataset_binding.json").exists():
        raise SystemExit("this run is bound to a frozen dataset; supply the same --dataset")
    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "rows.jsonl"
    done: dict[str, dict] = {}
    attempts: list[dict] = []
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                attempts.append(r)
                done[r["sample_id"]] = r
    done = {sid: row for sid, row in done.items() if "system_failure" not in row.get("reason_codes", [])}
    if args.dataset:
        samples = [
            json.loads(line)
            for line in (args.dataset / "samples.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        samples = load_drafts()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        missing = wanted - {s["sample_id"] for s in samples}
        if missing:
            raise SystemExit(f"unknown safety sample ids: {sorted(missing)}")
        samples = [s for s in samples if s["sample_id"] in wanted]
    if args.category:
        cats = {x.strip() for x in args.category.split(",") if x.strip()}
        missing = cats - {s["category"] for s in samples}
        if missing:
            raise SystemExit(f"unknown safety categories in selected samples: {sorted(missing)}")
        samples = [s for s in samples if s["category"] in cats]

    settings = Settings()
    configure_telemetry(**telemetry_options(settings))
    if settings.database_admin_url is None:
        print("DATABASE_ADMIN_URL is needed for the retrieval preflight and fact guard", file=sys.stderr)
        return 2
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    gpu = PinnedThread(args.gpu_timeout)
    provider = PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    from medops.application.policy_loader import ReleasedPolicySet, load_released

    released = ReleasedPolicySet.empty()
    if args.released:
        with psycopg.connect(with_database(settings.database_url.get_secret_value(), PRODUCTION_DB)) as rconn:
            released = load_released(rconn)
    rerank_output = released.rerank_output(RERANK_OUTPUT)
    reranker = PinnedReranker(gpu.call(lambda: BgeRerankerV2M3(device=args.device, output=rerank_output)), gpu)
    budgeted_gateway = build_budgeted_gateway(settings, run_cap_usd=args.max_cost_usd)
    gateway = MeteredGateway(budgeted_gateway)
    app_url = settings.database_url.get_secret_value()
    from medops.retrieval.glossary_store import load_versioned_glossary

    plane_kwargs = (
        {
            "answer_system": released.answer_system(ANSWER_SYSTEM),
            "config": released.hybrid_config(production_hybrid_config()),
            "glossary": load_versioned_glossary(
                settings.glossary_dir or REPO / "evals/glossary", released.glossary_version()
            ),
            "multi_query": released.multi_query(),
            "doc_focus": released.doc_focus(),
            "source_constraint": released.source_constraint(),
            "query_translation": released.query_translation(),
            "evidence_focus": released.evidence_focus(),
            "answer_models": released.answer_models(),
        }
        if args.released
        else {}
    )
    planes = {
        name: Plane(
            name,
            app_url,
            provider,
            reranker,
            gateway,
            args.as_of,
            admin_url=with_database(settings.database_admin_url.get_secret_value(), name),
            **plane_kwargs,
        )
        for name in (PRODUCTION_DB, SAFETY_DB)
    }
    from medops.evals.preflight import save_preflight

    preflight_reference = save_preflight(args.out, {name: plane.index_preflight for name, plane in planes.items()})
    registry = default_registry()
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
                    query_translation=released.query_translation(),
                )
            )
            if args.released
            else PRODUCTION_RETRIEVAL_VERSION
        ),
        skill_version_set=registry.version_set(),
        model_config_version=production_model_config_version() + released.model_config_suffix(),
    )
    conditions = make_conditions(
        root=REPO,
        runner=pathlib.Path(__file__),
        samples=samples,
        versions=versions.model_dump(mode="json"),
        facts={
            name: {"database_identity": plane.index_preflight["database_identity"], **plane.fact_snapshot}
            for name, plane in planes.items()
        },
        configuration={
            "as_of": args.as_of.isoformat(),
            "device": args.device,
            "gpu_timeout_s": args.gpu_timeout,
            "released": args.released,
            "monthly_budget_usd": settings.llm_monthly_budget_usd,
            "policy_snapshot": policy_snapshot(released),
            "answer_system_sha256": hashlib.sha256(planes[PRODUCTION_DB].deps.answer_system.encode()).hexdigest(),
        },
        inputs={
            "dataset_hash": frozen["dataset_hash"] if frozen else None,
            "dataset_version": frozen["dataset_version"] if frozen else None,
            "scoring": "safety-checks-code-bound-v1",
        },
    )
    conditions_hash = bind_conditions(args.out, conditions)
    validate_attempts(attempts, conditions)
    fact_guard = FactGuard(
        {name: plane.fact_snapshot for name, plane in planes.items()},
        {name: plane.current_fact_snapshot for name, plane in planes.items()},
    )
    fact_guard.check(force=True)
    prod = planes[PRODUCTION_DB]
    prod_lookups = (evidence_lookup(prod.conn_for_user, as_of=args.as_of), doc_type_lookup(prod.conn_for_user))
    consecutive = 0
    with rows_path.open("a", encoding="utf-8") as out:
        for i, s in enumerate(samples, 1):
            if s["sample_id"] in done:
                continue
            fact_guard.check()
            row = run_sample(s, planes, gateway, registry, versions, prod_lookups)
            row.update(attempt_id=str(uuid.uuid4()), run_conditions_sha256=conditions_hash)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            attempts.append(row)
            done[row["sample_id"]] = row
            if gpu.stalled:
                fact_guard.check(force=True)
                print(
                    f"gpu stalled beyond {args.gpu_timeout}s: exiting {EXIT_STALLED} for the supervisor",
                    flush=True,
                )
                return EXIT_STALLED
            consecutive = consecutive + 1 if "system_failure" in row["reason_codes"] else 0
            print(
                f"{i}/{len(samples)} {row['sample_id']} [{row['category']}] -> {row['api_outcome']} {row['reason_codes']} {'PASS' if row['passed'] else 'FAIL ' + ','.join(row['failed_checks'])} calls={row['model_calls']} ${row['cost_usd']:.4f} {row['latency_s']}s",
                flush=True,
            )
            if args.max_cost_usd is not None and budgeted_gateway.run_cap_blocked:
                fact_guard.check(force=True)
                print(f"run cost cap {args.max_cost_usd} USD reached: exiting 77", flush=True)
                return 77
            if consecutive >= args.max_consecutive_failures:
                fact_guard.check(force=True)
                print("consecutive system failures: exiting 76", flush=True)
                return 76
    fact_guard.check(force=True)
    rows = [done[s["sample_id"]] for s in samples if s["sample_id"] in done]
    dataset_info = (
        {"version": frozen["dataset_version"], "dataset_hash": frozen["dataset_hash"], "path": str(args.dataset)}
        if frozen
        else {"version": samples[0]["dataset_version"] if samples else None, "dataset_hash": None, "path": "drafts"}
    )
    summary = summarize(rows, versions, args.out.name, dataset_info)
    summary["preflight_reference"] = preflight_reference
    accounting = attempt_accounting(attempts)
    summary.update(
        run_conditions_sha256=conditions_hash,
        fact_guard_checks=fact_guard.checks,
        attempt_accounting=accounting,
        retained_outcome_cost_usd=summary["total_cost_usd"],
        total_cost_usd=accounting["cost_usd"],
        total_model_calls=accounting["model_calls"],
        run_cost_cap_usd=args.max_cost_usd,
    )
    (args.out / "results.json").write_text(
        json.dumps({**summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (args.out / "report.md").write_text(report_markdown(summary, rows), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k in ("n", "passed", "gates", "total_cost_usd")}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        flush()
