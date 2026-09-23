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
import pathlib
import random
import sys
import time
from contextlib import contextmanager
from datetime import date
from urllib.parse import urlsplit, urlunsplit

import psycopg

from medops.core.config import Settings
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
DATASET = REPO / "evals/main_set/main-v1-provisional"
MAPPING = REPO / "evals/experiments/e2e/main-v1-provisional/chunk_mapping.chunker-v2.main-v1-provisional.json"


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


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def pick_samples(rng: random.Random, per_dept: int, no_answer: int, conflict: int, *, everything: bool = False) -> list[dict]:
    samples = [json.loads(l) for l in (DATASET / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if everything:
        return samples
    new = [s for s in samples if s["sample_id"].startswith("ms-")]
    chosen: list[dict] = []
    for dept in ("MA", "PV", "CO"):
        pool = [s for s in new if s["dept"] == dept and s.get("answerable", True) and not s.get("conflict") and not s.get("derived_from")]
        chosen += rng.sample(pool, min(per_dept, len(pool)))
    na_pool = [s for s in new if s.get("answerable", True) is False]
    chosen += na_pool if no_answer < 0 else rng.sample(na_pool, min(no_answer, len(na_pool)))
    chosen += rng.sample([s for s in new if s.get("conflict") and not s.get("derived_from")], conflict)
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
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
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("refusing to overwrite an existing run directory")
    settings = Settings()
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    provider = BgeM3EmbeddingProvider(device=args.device)
    reranker = BgeRerankerV2M3(device=args.device, output=RERANK_OUTPUT)
    app_dsn = _with_database(settings.database_url.get_secret_value(), args.database)
    conn = psycopg.connect(app_dsn)
    as_of = args.as_of

    @contextmanager
    def conn_for_user(user: UserContext):
        with conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
            yield conn

    retrieval = ProductionRetrieval(
        conn_for_user=conn_for_user,
        lexical_factory=lambda c: production_lexical_retriever(c, as_of=as_of),
        vector_factory=lambda c: production_vector_retriever(c, provider, as_of=as_of),
        reranker=reranker,
        config=production_hybrid_config(),
        lexical_versions=production_lexical_versions(),
    )
    gateway = _Meter(
        BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
    )
    deps = HarnessDeps(
        retrieval=retrieval, gateway=gateway, answer_model_id=args.answer_model, judge_model_id=args.judge_model, as_of=as_of
    )
    versions = VersionSet(
        policy_version="policy-m2-smoke-1",
        retrieval_version=PRODUCTION_RETRIEVAL_VERSION,
        model_config_version=f"answer={args.answer_model};judge={args.judge_model};{VERIFIER_VERSION}",
    )
    mapping = {e["gold_id"]: e for e in json.loads(MAPPING.read_text(encoding="utf-8"))["entries"]}
    samples = pick_samples(random.Random(args.seed), args.per_dept, args.no_answer, args.conflict, everything=args.all)
    rows = []
    for s in samples:
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
        rows.append(
            {
                "sample_id": s["sample_id"],
                "dept": s["dept"],
                "kind": "no_answer" if s.get("answerable", True) is False else ("conflict" if s.get("conflict") else "answerable"),
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
                "flagged_evidence": list(run.flagged_evidence),
                "verify_elements": [
                    {"kind": e.kind.value, "verdict": e.verdict.value, "reason": e.reason[:120]}
                    for e in (run.state.verify_result.elements if run.state.verify_result else ())
                ],
                "attempts": [f"{a.node}:{a.outcome}" for a in run.attempts],
                "tokens_used": run.state.budget.used,
                "model_calls": gateway.calls - before[2],
                "model_tokens": gateway.tokens - before[1],
                "cost_usd": round(gateway.cost - before[0], 6),
                "latency_s": round(latency, 2),
            }
        )
        print(f"{s['sample_id']} [{rows[-1]['kind']}] -> {run.outcome} {rows[-1]['reason_codes']} gold_cited={rows[-1]['gold_cited']} calls={rows[-1]['model_calls']} ${rows[-1]['cost_usd']:.4f} {latency:.1f}s")
    conn.close()
    answerable = [r for r in rows if r["kind"] == "answerable"]
    summary = {
        "run": args.out.name,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "dataset": {"version": "main-v1-provisional", "second_human_review": "pending"},
        "versions": versions.model_dump(),
        "n": len(rows),
        "answered": sum(r["outcome"] == "answered" for r in rows),
        "answerable_answered_rate": round(sum(r["outcome"] == "answered" for r in answerable) / max(1, len(answerable)), 3),
        "answerable_gold_cited_rate": round(sum(r["gold_cited"] for r in answerable) / max(1, len(answerable)), 3),
        "no_answer_abstained_rate": round(
            sum(r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"] for r in rows if r["kind"] == "no_answer")
            / max(1, sum(1 for r in rows if r["kind"] == "no_answer")),
            3,
        ),
        "answerable_false_abstention_rate": round(
            sum(r["outcome"] == "escalated" and "insufficient_evidence" in r["reason_codes"] for r in answerable) / max(1, len(answerable)), 3
        ),
        "conflict_answered_with_gold": [r["gold_cited"] for r in rows if r["kind"] == "conflict"],
        "total_cost_usd": round(gateway.cost, 4),
        "total_model_calls": gateway.calls,
        "mean_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 2),
        "p95_latency_s": sorted(r["latency_s"] for r in rows)[int(0.95 * (len(rows) - 1))],
        "reason_code_counts": {},
        "rows": rows,
    }
    for r in rows:
        for c in r["reason_codes"]:
            summary["reason_code_counts"][c] = summary["reason_code_counts"].get(c, 0) + 1
    args.out.mkdir(parents=True)
    (args.out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Harness smoke `{args.out.name}` (main-v1-provisional, second human review pending)",
        "",
        f"- samples {summary['n']} · answered {summary['answered']} · answerable answered {summary['answerable_answered_rate']} · gold cited among answerable {summary['answerable_gold_cited_rate']} · no-answer abstained {summary['no_answer_abstained_rate']} · false abstention on answerable {summary['answerable_false_abstention_rate']} · cost ${summary['total_cost_usd']} · calls {summary['total_model_calls']} · mean latency {summary['mean_latency_s']}s · p95 {summary['p95_latency_s']}s",
        f"- answer model {args.answer_model} · judge {args.judge_model} · {VERIFIER_VERSION} · retrieval {PRODUCTION_RETRIEVAL_VERSION[:12]}…",
        "",
        "| sample | kind | dept | outcome | reason codes | gold cited | claims | calls | cost | latency |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(f"| {r['sample_id']} | {r['kind']} | {r['dept']} | {r['outcome']} | {', '.join(r['reason_codes']) or '—'} | {'yes' if r['gold_cited'] else ('—' if r['kind'] == 'no_answer' else 'no')} | {len(r['claims'])} | {r['model_calls']} | ${r['cost_usd']:.4f} | {r['latency_s']}s |")
    lines.append("")
    (args.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n", "answered", "answerable_answered_rate", "answerable_gold_cited_rate", "no_answer_abstained_rate", "answerable_false_abstention_rate", "total_cost_usd", "mean_latency_s")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
