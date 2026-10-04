"""Replay a candidate policy against the released policy on the frozen replay set (M4-07 / M4-08, record 82).

    python evals/replay/tools/replay_run.py --out evals/harness/runs/<run> --candidate-file cand.json \
        [--set evals/replay/replay-v1] [--subset | --full] [--items N] [--runs 3] [--device mps] [--max-cost-usd 6] \
        [--estimate] [--resume] [--skip-safety]

Two arms on the same items, `runs` independent runs each (model non-determinism is the randomness; retrieval is
deterministic): `baseline` = what production applies today (the released pointers on top of the repository
constants) and `candidate` = baseline plus the candidate diff (`retrieval_params/hybrid`, `prompt/answer_system`,
the targets the runtime can apply). Main items succeed when the run meets the item's expectation (the replay set's
label rule); safety items go through the safety runner's own per-sample checks. The report (`results.json`) carries
per-arm / per-run success, latency, tokens and cost, the paired comparison with a bootstrap 95% CI, every non-target
slice (< 30 items marked `diagnostic_only`), safety as the worst run per category, and the gate verdict computed by
`medops.loop.gate` — the same function the release route trusts.

The frozen items never enter candidate generation (INV-EVAL-01): this tool only *reads* the set. Secrets stay in the
environment; rows hold ids, outcomes, counts and latencies.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys
import time
from collections import defaultdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "evals/harness/tools"))

import psycopg  # noqa: E402

from medops.application.policy_loader import (  # noqa: E402
    ReleasedPolicy,
    ReleasedPolicySet,
    check_restates_release,
    load_released,
    validate_diff,
)
from medops.core.config import Settings  # noqa: E402
from medops.domain.common import Dept  # noqa: E402
from medops.domain.identity import UserContext  # noqa: E402
from medops.domain.state import VersionSet  # noqa: E402
from medops.harness.nodes import ANSWER_SYSTEM  # noqa: E402
from medops.harness.production import production_model_config_version  # noqa: E402
from medops.harness.runtime import initial_state, run_ask  # noqa: E402
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger  # noqa: E402
from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable  # noqa: E402
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway  # noqa: E402
from medops.loop.gate import compute_gate  # noqa: E402
from medops.retrieval.glossary_store import load_versioned_glossary  # noqa: E402
from medops.retrieval.production import (  # noqa: E402
    RERANK_OUTPUT,
    production_hybrid_config,
    production_retrieval_inputs,
)
from medops.retrieval.versioning import compute_retrieval_version  # noqa: E402
from medops.skills.catalog import default_registry  # noqa: E402
from medops.skills.production import doc_type_lookup, evidence_lookup  # noqa: E402

AVG_COST_MAIN = 0.0076  # USD per main item, v2 full run (4.65 / 614)
AVG_COST_SAFETY = 0.0038  # USD per safety item, safety r2 (0.64 / 170)


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def needs_run(done: dict[str, dict[str, Any]], key: str) -> bool:
    """On --resume a row is redone when it is missing or when the stored row is a system failure (infrastructure,
    not the candidate). Main and safety items follow the same rule — record 97: the safety loop used to keep the
    failed rows of a collapsed run, which left the gate's safety blockers in place after a resume."""
    row = done.get(key)
    return row is None or "system_failure" in row.get("reason_codes", [])


def seed_baseline_rows(
    prev: pathlib.Path, rows_path: pathlib.Path, *, versions: dict[str, Any], dataset_hash: str, subset: bool, runs: int
) -> int:
    """Copy the baseline-arm rows of a finished run into this run so a new candidate pays for one arm only (M5-04).
    Refused unless the earlier run used the same replay set (hash and subset flag) and the same baseline versions;
    rows keep their measured cost / latency and carry `reused_from` so the report can say where they came from."""
    res = json.loads((prev / "results.json").read_text(encoding="utf-8"))
    g = res["gate"]
    if g["replay_set"]["dataset_hash"] != dataset_hash or bool(g["replay_set"]["subset"]) != subset:
        raise SystemExit(f"--baseline-from {prev}: replay set differs from this run")
    if json.loads(json.dumps(g["arms"]["baseline"]["versions"])) != json.loads(json.dumps(versions)):
        raise SystemExit(f"--baseline-from {prev}: baseline versions differ (released state changed?)")
    have = {f"{r['arm']}|{r['run']}|{r['replay_id']}" for r in read_jsonl(rows_path)} if rows_path.exists() else set()
    n = 0
    with rows_path.open("a", encoding="utf-8") as fh:
        for r in read_jsonl(prev / "rows.jsonl"):
            key = f"{r['arm']}|{r['run']}|{r['replay_id']}"
            if r["arm"] != "baseline" or int(r["run"]) > runs or key in have:
                continue
            fh.write(json.dumps({**r, "reused_from": prev.name}, ensure_ascii=False) + "\n")
            have.add(key)
            n += 1
    return n


def main_success(item: dict[str, Any], outcome: str, cited: list[str]) -> bool:
    gold = bool(set(item["gold_chunks"]) & set(cited))
    kind = item["kind"]
    if kind == "answerable" or kind == "conflict":
        return outcome == "answered" and gold
    return outcome != "answered"  # no_answer


def arm_versions(name: str, released: ReleasedPolicySet, base_policy_version: str) -> VersionSet:
    hybrid = released.hybrid_config(production_hybrid_config())
    rerank_output = released.rerank_output(RERANK_OUTPUT)
    return VersionSet(
        policy_version=released.policy_version(base_policy_version) + f";arm={name}",
        retrieval_version=compute_retrieval_version(
            production_retrieval_inputs(
                hybrid,
                rerank_output=rerank_output,
                glossary_version=released.glossary_version(),
                multi_query=released.multi_query(),
                doc_focus=released.doc_focus(),
                query_translation=released.query_translation(),
            )
        ),
        skill_version_set=default_registry().version_set(),
        model_config_version=production_model_config_version() + released.model_config_suffix(),
    )


def arm_settings(released: ReleasedPolicySet) -> dict[str, Any]:
    """What an arm actually runs with; printed for both arms before any paid row (record 107: a stale candidate
    file once replaced the released bundle in the candidate arm and nobody saw it until the report)."""
    hybrid = released.hybrid_config(production_hybrid_config())
    return {
        "hybrid": dataclasses.asdict(hybrid),
        "rerank_output": released.rerank_output(RERANK_OUTPUT),
        "glossary": released.glossary_version(),
        "multi_query": released.multi_query(),
        "doc_focus": released.doc_focus(),
        "query_translation": released.query_translation(),
        "evidence_focus": released.evidence_focus(),
        "answer_prompt_overridden": released.get("prompt", "answer_system") is not None,
    }


def candidate_set(baseline: ReleasedPolicySet, spec: dict[str, Any]) -> ReleasedPolicySet:
    kind, name, diff = spec["kind"], spec["name"], spec["diff"]
    validate_diff(kind, name, diff, base=baseline.hybrid_config(production_hybrid_config()))
    check_restates_release(baseline, kind, name, diff)  # a stale candidate would run without the released keys
    pid = spec.get("policy_id") or hashlib.sha256(json.dumps(diff, sort_keys=True).encode()).hexdigest()[:32]
    kept = tuple(p for p in baseline.policies if (p.kind, p.name) != (kind, name))
    return ReleasedPolicySet(kept + (ReleasedPolicy(pid, kind, name, spec.get("version", "candidate"), dict(diff)),))


def pctl(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    import math

    return s[max(0, math.ceil(p * len(s)) - 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--set", type=pathlib.Path, default=REPO / "evals/replay/replay-v1")
    ap.add_argument("--subset", action="store_true", default=True)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--items", type=int, default=0, help="smoke: only the first N main items and N safety items")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--candidate-file", type=pathlib.Path, required=True, help="JSON {kind, name, diff[, policy_id]}")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date(2026, 9, 24))
    ap.add_argument("--max-cost-usd", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip-safety", action="store_true")
    ap.add_argument(
        "--baseline-from",
        type=pathlib.Path,
        default=None,
        help="reuse the baseline-arm rows of a finished run on the same replay set and released state (pays for the candidate arm only)",
    )
    ap.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=10,
        help="exit 76 after this many system_failure rows in a row (provider outage, machine sleep); resume later",
    )
    ap.add_argument("--gpu-timeout", type=float, default=120.0)
    args = ap.parse_args()

    manifest = json.loads((args.set / "manifest.json").read_text(encoding="utf-8"))
    items = read_jsonl(args.set / "items.jsonl")
    safety_items = read_jsonl(args.set / "safety_items.jsonl")
    if not args.full:
        subset = set(json.loads((args.set / "subset.json").read_text(encoding="utf-8"))["replay_ids"])
        items = [it for it in items if it["replay_id"] in subset]
    safety_items = [it for it in safety_items if it["label"] != "not_exercised"]
    if args.items:
        items, safety_items = items[: args.items], safety_items[: args.items]
    if args.skip_safety:
        safety_items = []
    paid_arms = 1 if args.baseline_from else 2
    est = args.runs * paid_arms * (len(items) * AVG_COST_MAIN + len(safety_items) * AVG_COST_SAFETY)
    print(
        f"items={len(items)} safety={len(safety_items)} runs={args.runs} paid arms={paid_arms} estimated cost ≈ {est:.2f} USD",
        flush=True,
    )
    if args.estimate:
        return 0
    if args.out.exists() and not args.resume:
        raise SystemExit("refusing to overwrite an existing run directory (pass --resume)")
    args.out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(args.candidate_file.read_text(encoding="utf-8"))

    settings = Settings()
    sr = _load(REPO / "evals/harness/tools/safety_run.py", "safety_run")
    sa = sr._load_smoke_ask()
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    app_url = settings.database_url.get_secret_value()
    with psycopg.connect(sa._with_database(app_url, sr.PRODUCTION_DB)) as conn:
        baseline = load_released(conn)
    candidate = candidate_set(baseline, spec)
    arms = {"baseline": baseline, "candidate": candidate}
    base_policy_version = "policy-m3-api-1"
    for name, rel in arms.items():
        print(f"arm {name}: {json.dumps(arm_settings(rel), ensure_ascii=False, sort_keys=True)}", flush=True)

    gpu = sa.GpuThread(args.gpu_timeout)
    provider = sa._PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    rerankers: dict[int, Any] = {}
    gateway = sa._Meter(
        BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
    )
    registry = default_registry()
    planes: dict[str, dict[str, Any]] = {}
    versions: dict[str, VersionSet] = {}
    for name, rel in arms.items():
        out = rel.rerank_output(RERANK_OUTPUT)
        if out not in rerankers:
            rerankers[out] = sa._PinnedReranker(
                gpu.call(lambda o=out: BgeRerankerV2M3(device=args.device, output=o)), gpu
            )
        cfg = rel.hybrid_config(production_hybrid_config())
        prompt = rel.answer_system(ANSWER_SYSTEM)
        glossary = load_versioned_glossary(settings.glossary_dir or REPO / "evals/glossary", rel.glossary_version())
        planes[name] = {
            db: sr.Plane(
                db,
                app_url,
                provider,
                rerankers[out],
                gateway,
                args.as_of,
                sa,
                config=cfg,
                answer_system=prompt,
                glossary=glossary,
                multi_query=rel.multi_query(),
                doc_focus=rel.doc_focus(),
                query_translation=rel.query_translation(),
                evidence_focus=rel.evidence_focus(),
            )
            for db in (sr.PRODUCTION_DB, sr.SAFETY_DB)
        }
        versions[name] = arm_versions(name, rel, base_policy_version)
    drafts = {s["sample_id"]: s for s in sr.load_drafts(include_withdrawn=True)}  # frozen sets keep withdrawn ids

    rows_path = args.out / "rows.jsonl"
    if args.baseline_from:
        reused = seed_baseline_rows(
            args.baseline_from,
            rows_path,
            versions=versions["baseline"].model_dump(mode="json"),
            dataset_hash=manifest["dataset_hash"],
            subset=not args.full,
            runs=args.runs,
        )
        print(f"reused {reused} baseline rows from {args.baseline_from.name}", flush=True)
    done: dict[str, dict[str, Any]] = {}
    if rows_path.exists():
        for r in read_jsonl(rows_path):
            done[f"{r['arm']}|{r['run']}|{r['replay_id']}"] = r
    started = dt.datetime.now(dt.UTC)
    with rows_path.open("a", encoding="utf-8") as fh:
        streak = 0  # consecutive system_failure rows (provider outage or a sleeping machine)
        for run in range(1, args.runs + 1):
            for arm in ("baseline", "candidate"):
                prod = planes[arm][sr.PRODUCTION_DB]
                lookups = (evidence_lookup(prod.conn_for_user, as_of=args.as_of), doc_type_lookup(prod.conn_for_user))
                for it in items:
                    key = f"{arm}|{run}|{it['replay_id']}"
                    if not needs_run(done, key):
                        continue
                    user = UserContext(
                        user_id=hashlib.sha256(f"replay:{it['replay_id']}".encode()).hexdigest()[:16],
                        dept=Dept(it["dept"]),
                        roles=("analyst",),
                        acl_scopes=frozenset({f"{it['dept']}:read"}),
                    )
                    plane = prod
                    deps = plane.deps
                    hist = it.get("historical") or {}
                    if hist.get("as_of"):
                        a = dt.date.fromisoformat(hist["as_of"])
                        deps = dataclasses.replace(plane.deps, as_of=a, retrieval=plane.retrieval_for(a))
                    state = initial_state(
                        user=user, query=it["query"], versions=versions[arm], historical_requested=bool(hist)
                    )
                    before = (gateway.cost, gateway.tokens, gateway.calls)
                    t0 = time.perf_counter()
                    r = run_ask(state, deps)
                    st = r.state
                    cited = [c.chunk_id for c in st.answer.citations] if st.answer else []
                    row = {
                        "replay_id": it["replay_id"],
                        "arm": arm,
                        "run": run,
                        "kind": it["kind"],
                        "dept": it["dept"],
                        "language": it.get("language"),
                        "slices": it.get("slices", []),
                        "outcome": r.outcome,
                        "reason_codes": [c.value for c in st.escalation.reason_codes] if st.escalation else [],
                        "cited_chunks": cited,
                        "gold_cited": bool(set(it["gold_chunks"]) & set(cited)),
                        "success": main_success(it, r.outcome, cited),
                        "expected_label": it["label"],
                        "model_calls": gateway.calls - before[2],
                        "model_tokens": gateway.tokens - before[1],
                        "cost_usd": round(gateway.cost - before[0], 6),
                        "latency_s": round(time.perf_counter() - t0, 2),
                    }
                    done[key] = row
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(
                        f"run {run} {arm} {it['replay_id']} -> {r.outcome} success={row['success']} ${row['cost_usd']:.4f} {row['latency_s']}s",
                        flush=True,
                    )
                    if gpu.stalled:
                        print("gpu stalled: exiting for the supervisor", flush=True)
                        return sa.GpuThread.EXIT_STALLED
                    streak = streak + 1 if "system_failure" in row["reason_codes"] else 0
                    if streak >= args.max_consecutive_failures:
                        print(f"{streak} consecutive system failures: exiting 76 (resume redoes them)", flush=True)
                        return 76
                    if gateway.cost > args.max_cost_usd:
                        print(f"cost cap {args.max_cost_usd} USD reached: stopping (resume later)", flush=True)
                        return 77
                for it in safety_items:
                    key = f"{arm}|{run}|{it['replay_id']}"
                    if not needs_run(done, key):
                        continue
                    sample = drafts[it["source"]["sample_id"]]
                    before = (gateway.cost, gateway.tokens, gateway.calls)
                    srow = sr.run_sample(sample, planes[arm], gateway, registry, versions[arm], lookups)
                    row = {
                        "replay_id": it["replay_id"],
                        "arm": arm,
                        "run": run,
                        "category": it["category"],
                        "dept": it["dept"],
                        "outcome": srow["api_outcome"],
                        "reason_codes": srow["reason_codes"],
                        "success": bool(srow["passed"]),
                        "failed_checks": srow["failed_checks"],
                        "model_calls": gateway.calls - before[2],
                        "model_tokens": gateway.tokens - before[1],
                        "cost_usd": round(gateway.cost - before[0], 6),
                        "latency_s": srow["latency_s"],
                    }
                    done[key] = row
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(
                        f"run {run} {arm} {it['replay_id']} [{it['category']}] -> {'PASS' if row['success'] else 'FAIL'} ${row['cost_usd']:.4f}",
                        flush=True,
                    )
                    streak = streak + 1 if "system_failure" in row["reason_codes"] else 0
                    if streak >= args.max_consecutive_failures:
                        print(f"{streak} consecutive system failures: exiting 76 (resume redoes them)", flush=True)
                        return 76
                    if gateway.cost > args.max_cost_usd:
                        print(f"cost cap {args.max_cost_usd} USD reached: stopping (resume later)", flush=True)
                        return 77

    # ---- report
    main_ids = [it["replay_id"] for it in items]
    by_arm_run: dict[str, list[dict[str, float]]] = {"baseline": [], "candidate": []}
    tokens_by_arm_run: dict[str, list[dict[str, float]]] = {"baseline": [], "candidate": []}
    safety_by_arm_run: dict[str, list[dict[str, dict[str, float]]]] = {"baseline": [], "candidate": []}
    aggregates: dict[str, list[dict[str, Any]]] = {"baseline": [], "candidate": []}
    for run in range(1, args.runs + 1):
        for arm in ("baseline", "candidate"):
            rows = [done[f"{arm}|{run}|{i}"] for i in main_ids if f"{arm}|{run}|{i}" in done]
            by_arm_run[arm].append({r["replay_id"]: 1.0 if r["success"] else 0.0 for r in rows})
            tokens_by_arm_run[arm].append({r["replay_id"]: float(r["model_tokens"]) for r in rows})
            cats: dict[str, dict[str, float]] = defaultdict(dict)
            srows = [
                done[f"{arm}|{run}|{it['replay_id']}"]
                for it in safety_items
                if f"{arm}|{run}|{it['replay_id']}" in done
            ]
            for r in srows:
                cats[r["category"]][r["replay_id"]] = 1.0 if r["success"] else 0.0
            safety_by_arm_run[arm].append(dict(cats))
            lat = [r["latency_s"] for r in rows]
            aggregates[arm].append(
                {
                    "run": run,
                    "n": len(rows),
                    "success_rate": round(sum(r["success"] for r in rows) / max(1, len(rows)), 4),
                    "safety_n": len(srows),
                    "safety_pass_rate": round(sum(r["success"] for r in srows) / max(1, len(srows)), 4)
                    if srows
                    else None,
                    "latency_p50_s": pctl(lat, 0.5),
                    "latency_p95_s": pctl(lat, 0.95),
                    "tokens": sum(r["model_tokens"] for r in rows + srows),
                    "cost_usd": round(sum(r["cost_usd"] for r in rows + srows), 4),
                    "system_failures": sum("system_failure" in r["reason_codes"] for r in rows),
                }
            )
    slices = {
        it["replay_id"]: {
            "dept": it["dept"],
            "kind": it["kind"],
            "language": it.get("language"),
            "slice": it.get("slices", []),
        }
        for it in items
    }
    complete_safety = (
        bool(safety_items)
        and all(len(r) >= 1 for r in safety_by_arm_run["candidate"])
        and not args.items
        and not args.skip_safety
    )
    gate = compute_gate(
        baseline_runs=by_arm_run["baseline"],
        candidate_runs=by_arm_run["candidate"],
        slices=slices,
        safety_baseline_runs=safety_by_arm_run["baseline"],
        safety_candidate_runs=safety_by_arm_run["candidate"],
        safety_complete=complete_safety,
        seed=args.seed,
        profile=spec.get("gate_profile", "quality"),
        baseline_tokens=tokens_by_arm_run["baseline"],
        candidate_tokens=tokens_by_arm_run["candidate"],
    ).as_dict()
    gate["replay_set"] = {
        "dataset_version": manifest["dataset_version"],
        "dataset_hash": manifest["dataset_hash"],
        "subset": not args.full,
        "items": len(items),
        "safety_items": len(safety_items),
    }
    gate["arms"] = {
        "baseline": {
            "released": [dataclasses.asdict(p) for p in baseline.policies],
            "versions": versions["baseline"].model_dump(),
        },
        "candidate": {"diff": spec, "versions": versions["candidate"].model_dump()},
    }
    results = {
        "run": args.out.name,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "smoke": bool(args.items),
        "aggregates": aggregates,
        "gate": gate,
        "total_cost_usd": round(gateway.cost, 4),
        "baseline_reused_from": args.baseline_from.name if args.baseline_from else None,
    }
    (args.out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(render(results), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": gate["passed"],
                "target_delta_pp": gate["target"]["delta_pp"],
                "ci95": gate["target"]["ci95_pp"],
                "blockers": gate["blockers"],
                "cost": results["total_cost_usd"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def render(res: dict[str, Any]) -> str:
    g = res["gate"]
    lines = [f"# Replay {res['run']} ({res['started_at'][:10]}){' — SMOKE' if res['smoke'] else ''}", ""]
    lines += [
        f"- replay set {g['replay_set']['dataset_version']} ({g['replay_set']['dataset_hash'][:8]}…), {'subset' if g['replay_set']['subset'] else 'full'}: {g['replay_set']['items']} items + {g['replay_set']['safety_items']} safety items",
        f"- candidate diff: `{json.dumps(g['arms']['candidate']['diff'], ensure_ascii=False)}`",
        f"- cost {res['total_cost_usd']} USD",
        "",
    ]
    if res.get("baseline_reused_from"):
        lines.insert(
            -1,
            f"- baseline arm reused from `{res['baseline_reused_from']}` (same replay set and released state); cost above is the candidate arm only",
        )
    lines += [
        "## Runs",
        "",
        "| arm | run | n | success | safety pass | p50 s | p95 s | tokens | cost | system failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, runs in res["aggregates"].items():
        for a in runs:
            lines.append(
                f"| {arm} | {a['run']} | {a['n']} | {a['success_rate']} | {a['safety_pass_rate']} | {a['latency_p50_s']} | {a['latency_p95_s']} | {a['tokens']} | {a['cost_usd']} | {a['system_failures']} |"
            )
    t = g["target"]
    th = g["thresholds"]
    if t.get("profile") == "cost":
        target_line = (
            f"- profile cost: tokens/item baseline {t['tokens_baseline']} → candidate {t['tokens_candidate']} "
            f"({100 * t['token_reduction']:.1f}% less, need ≥ {100 * th['token_reduction_min']:.0f}%); "
            f"quality Δ {t['delta_pp']} pp (95% CI {t['ci95_pp']}, floor {th['quality_min_pp']} pp) → {'✓' if t['passes'] else '✗'}"
        )
    else:
        target_line = f"- target: baseline {t['baseline']} → candidate {t['candidate']}, Δ {t['delta_pp']} pp (95% CI {t['ci95_pp']}), threshold +{th['target_min_pp']} pp → {'✓' if t['passes'] else '✗'}"
    lines += [
        "",
        "## Gate",
        "",
        target_line,
        f"- reliability: {g['reliability']}",
        f"- safety complete: {g['safety']['complete']}",
        f"- **passed: {g['passed']}**" + (f" — blockers: {g['blockers']}" if g["blockers"] else ""),
        "",
        "### Non-target slices (Δ pp; < 30 items diagnostic only)",
        "",
        "| slice | n | baseline | candidate | Δ pp | diagnostic | blocks |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for s in g["non_target"]:
        lines.append(
            f"| {s['name']} | {s['n']} | {s['baseline']} | {s['candidate']} | {s['delta_pp']} | {'yes' if s['diagnostic_only'] else ''} | {'✗' if s['blocks'] else ''} |"
        )
    lines += [
        "",
        "### Safety (worst run per category)",
        "",
        "| category | n | baseline worst | candidate worst | blocks |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for s in g["safety"]["categories"]:
        lines.append(
            f"| {s['category']} | {s['n']} | {s['baseline_worst']} | {s['candidate_worst']} | {'✗' if s['blocks'] else ''} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
