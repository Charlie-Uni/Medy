"""First live asks through the M2 harness (Intent -> Retrieve -> Verify -> Safety -> Answer | Escalate) on
samples of `main-v1-provisional`, with the production retrieval stack on medops_v2 and the OpenAI gateway.

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
import queue
import random
import sys
import threading
import time
from contextlib import contextmanager
from datetime import date
from urllib.parse import urlsplit, urlunsplit

import psycopg

from medops.core.config import Settings
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.nodes import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL
from medops.harness.retrieval_port import ProductionRetrieval
from medops.harness.runtime import initial_state, run_ask
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_lexical_retriever,
    production_lexical_versions,
    production_vector_retriever,
)
from medops.verification.verifier import VERIFIER_VERSION

REPO = pathlib.Path(__file__).resolve().parents[3]
DATASET = REPO / "evals/main_set/main-v1-provisional"  # default; --dataset selects a later frozen version
MAPPING = REPO / "evals/experiments/e2e/main-v1-provisional/chunk_mapping.chunker-v2.main-v1-provisional.json"


def mapping_for(dataset: pathlib.Path) -> pathlib.Path:
    """The gold -> chunk mapping published for a frozen main-set version (medops.evals.probe.chunk_mapping)."""
    return REPO / "evals/experiments/e2e" / dataset.name / f"chunk_mapping.chunker-v2.{dataset.name}.json"


class _Meter:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0
        self.cost = 0.0
        self.tokens = 0

    @property
    def provider(self):
        return self._inner.provider

    def complete(self, request):
        r = self._inner.complete(request)
        self.calls += 1
        self.cost += r.cost_usd
        self.tokens += r.usage.total_tokens
        return r


class GpuThread:
    """Every torch call goes through one long-lived daemon thread, with a wait timeout.

    The harness runs node bodies in short-lived worker threads (`run_node`). Driving Metal from a new thread per
    attempt wedged the MPS stream once (2026-09-23, sample 213 of the first full run: the driver blocked forever
    in resource allocation and no node timeout could unblock the process). One pinned thread removes the churn,
    and the timeout turns a wedged GPU into a `dependency_timeout` plus a process exit (75) that a supervisor can
    restart with `--resume`.
    """

    EXIT_STALLED = 75

    def __init__(self, timeout_s: float) -> None:
        self._q: queue.Queue = queue.Queue()
        self._timeout = timeout_s
        self.stalled = False
        threading.Thread(target=self._loop, name="gpu-pinned", daemon=True).start()

    def _loop(self) -> None:
        while True:
            fn, args, kwargs, box, done = self._q.get()
            try:
                box.append(("ok", fn(*args, **kwargs)))
            except BaseException as exc:  # noqa: BLE001 - re-raised in the calling thread
                box.append(("err", exc))
            done.set()

    def call(self, fn, *args, **kwargs):
        box: list = []
        done = threading.Event()
        self._q.put((fn, args, kwargs, box, done))
        if not done.wait(self._timeout):
            self.stalled = True
            raise InfrastructureError(
                ErrorCode.dependency_timeout,
                detail=f"gpu call {getattr(fn, '__name__', fn)} exceeded {self._timeout}s",
                retryable=False,
            )
        kind, value = box[0]
        if kind == "err":
            raise value
        return value


class _PinnedEmbedding:
    def __init__(self, inner, gpu: GpuThread) -> None:
        self._inner, self._gpu = inner, gpu
        self.spec = inner.spec

    def embed_documents(self, texts):
        return self._gpu.call(self._inner.embed_documents, texts)

    def embed_query(self, text):
        return self._gpu.call(self._inner.embed_query, text)


class _PinnedReranker:
    def __init__(self, inner, gpu: GpuThread) -> None:
        self._inner, self._gpu = inner, gpu
        self.spec = inner.spec
        self.framework = getattr(inner, "framework", "")

    def score(self, query, texts):
        return self._gpu.call(self._inner.score, query, texts)


def _mps_empty_cache() -> None:
    import torch

    torch.mps.empty_cache()


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


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
        "--dataset", type=pathlib.Path, default=DATASET, help="frozen main-set directory (default main-v1-provisional)"
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
        "--max-consecutive-failures",
        type=int,
        default=10,
        help="exit 76 after this many system_failure samples in a row (provider outage); the supervisor resumes later",
    )
    args = ap.parse_args()
    if args.out.exists() and not args.resume:
        raise SystemExit("refusing to overwrite an existing run directory (pass --resume to continue it)")
    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "rows.jsonl"
    done_rows: dict[str, dict] = {}
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done_rows[r["sample_id"]] = r
    redo = {sid for sid, r in done_rows.items() if "system_failure" in r["reason_codes"]}
    settings = Settings()
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    gpu = GpuThread(args.gpu_timeout)
    provider = _PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    app_dsn = _with_database(settings.database_url.get_secret_value(), args.database)
    conn = psycopg.connect(app_dsn)
    from medops.application.policy_loader import ReleasedPolicySet, load_released

    released = load_released(conn) if args.released else ReleasedPolicySet.empty()
    conn.rollback()
    rerank_output = released.rerank_output(RERANK_OUTPUT)
    reranker = _PinnedReranker(gpu.call(lambda: BgeRerankerV2M3(device=args.device, output=rerank_output)), gpu)
    if settings.database_admin_url is None:
        print("DATABASE_ADMIN_URL is needed for the index-coverage pre-flight", file=sys.stderr)
        return 2
    from medops.retrieval.production import require_index_coverage

    with psycopg.connect(_with_database(settings.database_admin_url.get_secret_value(), args.database)) as admin_conn:
        require_index_coverage(admin_conn, plane=args.database)  # record 109: never measure an unindexed corpus
    as_of = args.as_of

    @contextmanager
    def conn_for_user(user: UserContext):
        with conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
            yield conn

    gateway = _Meter(
        BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
    )
    from medops.retrieval.glossary_store import load_versioned_glossary
    from medops.retrieval.query_translation import QueryTranslator

    translation = released.query_translation()
    retrieval = ProductionRetrieval(
        conn_for_user=conn_for_user,
        lexical_factory=lambda c: production_lexical_retriever(c, as_of=as_of),
        vector_factory=lambda c: production_vector_retriever(c, provider, as_of=as_of),
        reranker=reranker,
        config=released.hybrid_config(production_hybrid_config()),
        lexical_versions=production_lexical_versions(),
        glossary=load_versioned_glossary(settings.glossary_dir or REPO / "evals/glossary", released.glossary_version()),
        multi_query=released.multi_query(),
        doc_focus=released.doc_focus(),
        translator=QueryTranslator(gateway, translation).translate if translation != "off" else None,
    )
    deps = HarnessDeps(
        retrieval=retrieval,
        gateway=gateway,
        answer_model_id=args.answer_model,
        judge_model_id=args.judge_model,
        as_of=as_of,
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
                    query_translation=translation,
                )
            )
            if args.released
            else PRODUCTION_RETRIEVAL_VERSION
        ),
        model_config_version=f"answer={args.answer_model};judge={args.judge_model};{VERIFIER_VERSION}"
        + released.model_config_suffix(),
    )
    dataset_manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
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
            s for s in pick_samples(random.Random(args.seed), 0, 0, 0, everything=True) if s["sample_id"] in wanted
        ]
        missing = wanted - {s["sample_id"] for s in samples}
        if missing:
            raise SystemExit(f"unknown sample ids: {sorted(missing)}")
    consecutive_failures = 0
    if done_rows:
        print(f"resuming: {len(done_rows) - len(redo)} rows kept, {len(redo)} system_failure rows redone", flush=True)
    for s in samples:
        if s["sample_id"] in done_rows and s["sample_id"] not in redo:
            continue
        user = UserContext(
            user_id=hashlib.sha256(f"smoke:{s['sample_id']}".encode()).hexdigest()[:16],
            dept=Dept(s["dept"]),
            roles=("analyst",),
            acl_scopes=frozenset({f"{s['dept']}:read"}),
        )
        state = initial_state(user=user, query=s["query"], versions=versions)
        before = (gateway.cost, gateway.tokens, gateway.calls)
        t0 = time.perf_counter()
        run = run_ask(state, deps)
        latency = time.perf_counter() - t0
        gold_chunks: set[str] = set()
        for g in s.get("required_gold_evidence", []):
            entry = mapping.get(g["gold_id"])
            if entry and entry["status"] == "mapped":
                gold_chunks.update(entry["chunk_ids"])
        cited = [c.chunk_id for c in run.state.answer.citations] if run.state.answer else []
        row = {
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
            "gold_cited": bool(gold_chunks & set(cited)),
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
            "cost_usd": round(gateway.cost - before[0], 6),
            "latency_s": round(latency, 2),
        }
        done_rows[row["sample_id"]] = row
        with rows_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"{s['sample_id']} [{row['kind']}] -> {run.outcome} {row['reason_codes']} gold_cited={row['gold_cited']} calls={row['model_calls']} ${row['cost_usd']:.4f} {latency:.1f}s",
            flush=True,
        )
        consecutive_failures = consecutive_failures + 1 if "system_failure" in row["reason_codes"] else 0
        if consecutive_failures >= args.max_consecutive_failures:
            print(
                f"{consecutive_failures} consecutive system failures (provider outage?): exiting 76 for the supervisor to resume later",
                flush=True,
            )
            conn.close()
            os._exit(76)
        if gpu.stalled:
            print(
                f"gpu stalled beyond {args.gpu_timeout}s: exiting {GpuThread.EXIT_STALLED} for the supervisor to resume",
                flush=True,
            )
            conn.close()
            os._exit(GpuThread.EXIT_STALLED)
        if args.device == "mps":
            gpu.call(_mps_empty_cache)
    conn.close()
    rows = [done_rows[s["sample_id"]] for s in samples if s["sample_id"] in done_rows]
    answerable = [r for r in rows if r["kind"] == "answerable"]
    summary = {
        "run": args.out.name,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "dataset": {
            "version": dataset_manifest["dataset_version"],
            "dataset_hash": dataset_manifest.get("dataset_hash"),
            "second_human_review": dataset_manifest.get("second_human_review", {}).get("status", "pending"),
        },
        "versions": versions.model_dump(),
        "n": len(rows),
        "answered": sum(r["outcome"] == "answered" for r in rows),
        "answerable_answered_rate": round(
            sum(r["outcome"] == "answered" for r in answerable) / max(1, len(answerable)), 3
        ),
        "answerable_gold_cited_rate": round(sum(r["gold_cited"] for r in answerable) / max(1, len(answerable)), 3),
        "no_answer_abstained_rate": round(
            sum(
                r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"]
                for r in rows
                if r["kind"] == "no_answer"
            )
            / max(1, sum(1 for r in rows if r["kind"] == "no_answer")),
            3,
        ),
        "answerable_false_abstention_rate": round(
            sum(r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"] for r in answerable)
            / max(1, len(answerable)),
            3,
        ),
        "conflict_answered_with_gold": [r["gold_cited"] for r in rows if r["kind"] == "conflict"],
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "total_model_calls": sum(r["model_calls"] for r in rows),
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
    sys.exit(main())
