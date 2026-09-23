"""First live runs of the two delivered Skills through the Registry (M2-12, record 55 follow-up): `label_query` and
`citation_verification` with the production retrieval stack on medops_v2, the production lookups and the OpenAI
gateway. Cases are hand-picked from the main set (answered samples of the full run) plus deliberate failure paths
(non-label document, scope denial, unknown / cross-department chunk, altered number).

    python evals/harness/tools/skill_smoke.py --out evals/harness/runs/2026-09-23-skill-smoke-v1 [--device mps]
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
from contextlib import contextmanager
from datetime import date

import psycopg

from medops.core.config import Settings
from medops.core.errors import MedOpsError
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.nodes import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL, production_model_config_version
from medops.harness.retrieval_port import ProductionRetrieval
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
from medops.skills.catalog import default_registry
from medops.skills.production import doc_type_lookup, evidence_lookup
from medops.skills.registry import SkillContext

REPO = pathlib.Path(__file__).resolve().parents[3]
FULL_RUN = REPO / "evals/harness/runs/2026-09-23-full-ask-v1/rows.jsonl"


def _load_smoke_ask():
    spec = importlib.util.spec_from_file_location("smoke_ask", REPO / "evals/harness/tools/smoke_ask.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def user_for(dept: str, tag: str, *, scopes: frozenset[str] | None = None) -> UserContext:
    return UserContext(
        user_id=hashlib.sha256(f"skill-smoke:{tag}".encode()).hexdigest()[:16],
        dept=Dept(dept),
        roles=("analyst",),
        acl_scopes=frozenset({f"{dept}:read"}) if scopes is None else scopes,
    )


def cases(rows: dict[str, dict]) -> list[dict]:
    """Hand-picked from the full run (answered MA label samples) plus failure paths."""
    answered_ma = [r for r in rows.values() if r["dept"] == "MA" and r["outcome"] == "answered" and r["gold_cited"]]
    answered_pv = [r for r in rows.values() if r["dept"] == "PV" and r["outcome"] == "answered" and r["gold_cited"]]
    out: list[dict] = [
        {
            "case": "label_query/positive",
            "skill": "label_query",
            "user": user_for("MA", "lq1"),
            "input": {"product": "瑪爾胰", "question": "每日最高建議劑量是多少？"},
            "expect": "completed",
        },
        {
            "case": "label_query/positive-2",
            "skill": "label_query",
            "user": user_for("MA", "lq2"),
            "input": {"product": "Losacar", "question": "治療高血壓的一般起始劑量及維持劑量是多少？"},
            "expect": "completed",
        },
        {
            "case": "label_query/positive-3",
            "skill": "label_query",
            "user": user_for("MA", "lq3"),
            "input": {"product": "拔痛酸錠", "question": "6 至 12 歲兒童的口服劑量如何給予？"},
            "expect": "completed",
        },
        {
            "case": "label_query/non-label-topic",
            "skill": "label_query",
            "user": user_for("PV", "lq4"),
            "input": {"product": "GVP Module VI", "question": "嚴重不良反應 ICSR 的提交時限是幾天？"},
            "expect": "insufficient_evidence",
        },
        {
            "case": "label_query/scope-denied",
            "skill": "label_query",
            "user": user_for("MA", "lq5", scopes=frozenset({"MA:write"})),
            "input": {"product": "瑪爾胰", "question": "每日最高建議劑量是多少？"},
            "expect": "forbidden",
        },
        {
            "case": "label_query/schema-violation",
            "skill": "label_query",
            "user": user_for("MA", "lq6"),
            "input": {"product": "", "question": "x"},
            "expect": "schema_violation",
        },
    ]
    for i, r in enumerate(answered_ma[:2] + answered_pv[:1], 1):
        out.append(
            {
                "case": f"citation_verification/supported-{i}",
                "skill": "citation_verification",
                "user": user_for(r["dept"], f"cv{i}"),
                "input": {
                    "claims": [{"text": c, "citation_chunk_ids": r["cited_chunks"][:8]} for c in r["claims"][:2]]
                },
                "expect": "completed",
                "expect_verdicts": "supported",
                "sample_id": r["sample_id"],
            }
        )
    r = answered_ma[0]
    import re

    altered = re.sub(
        r"(\d+)(\s*(?:mg|毫克|公絲))", lambda m: str(int(m.group(1)) * 3) + m.group(2), r["claims"][0], count=1
    )
    out.append(
        {
            "case": "citation_verification/altered-number",
            "skill": "citation_verification",
            "user": user_for("MA", "cv-alt"),
            "input": {"claims": [{"text": altered, "citation_chunk_ids": r["cited_chunks"][:8]}]},
            "expect": "completed",
            "expect_verdicts": "not supported",
            "sample_id": r["sample_id"],
            "altered_from": r["claims"][0],
        }
    )
    out.append(
        {
            "case": "citation_verification/unknown-chunk",
            "skill": "citation_verification",
            "user": user_for("MA", "cv-unk"),
            "input": {
                "claims": [
                    {
                        "text": r["claims"][0],
                        "citation_chunk_ids": ["00000000-0000-0000-0000-000000000000", "not-a-uuid"],
                    }
                ]
            },
            "expect": "completed",
            "expect_verdicts": "not_supported",
            "sample_id": r["sample_id"],
        }
    )
    pv = answered_pv[0]
    out.append(
        {
            "case": "citation_verification/cross-dept-chunk",
            "skill": "citation_verification",
            "user": user_for("MA", "cv-xd"),
            "input": {"claims": [{"text": pv["claims"][0], "citation_chunk_ids": pv["cited_chunks"][:8]}]},
            "expect": "completed",
            "expect_verdicts": "not_supported (invisible)",
            "sample_id": pv["sample_id"],
        }
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--database", default="medops_v2")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 23))
    ap.add_argument("--only", default="", help="run only cases whose name contains this text")
    ap.add_argument(
        "--repeat", type=int, default=1, help="run each selected case this many times (nondeterminism check)"
    )
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("refusing to overwrite an existing run directory")
    sa = _load_smoke_ask()
    settings = Settings()
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    gpu = sa.GpuThread(120.0)
    provider = sa._PinnedEmbedding(gpu.call(lambda: BgeM3EmbeddingProvider(device=args.device)), gpu)
    reranker = sa._PinnedReranker(gpu.call(lambda: BgeRerankerV2M3(device=args.device, output=RERANK_OUTPUT)), gpu)
    conn = psycopg.connect(sa._with_database(settings.database_url.get_secret_value(), args.database))
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
    gateway = sa._Meter(
        BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
    )
    deps = HarnessDeps(
        retrieval=retrieval,
        gateway=gateway,
        answer_model_id=PRODUCTION_ANSWER_MODEL,
        judge_model_id=PRODUCTION_JUDGE_MODEL,
        as_of=as_of,
    )
    registry = default_registry()
    versions = VersionSet(
        policy_version="policy-m2-smoke-1",
        retrieval_version=PRODUCTION_RETRIEVAL_VERSION,
        skill_version_set=registry.version_set(),
        model_config_version=production_model_config_version(),
    )
    ev_lookup = evidence_lookup(conn_for_user, as_of=as_of)
    dt_lookup = doc_type_lookup(conn_for_user)
    rows = {
        json.loads(line)["sample_id"]: json.loads(line)
        for line in FULL_RUN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    results = []
    wanted = [w for w in args.only.split(",") if w]
    all_cases = cases(rows)
    exact = {c["case"] for c in all_cases}
    selected = [
        c for c in all_cases if not wanted or any(c["case"] == w or (w not in exact and w in c["case"]) for w in wanted)
    ]
    for case in [c for c in selected for _ in range(args.repeat)]:
        trace = hashlib.sha256(case["case"].encode()).hexdigest()[:32]
        ctx = SkillContext(
            user=case["user"],
            versions=versions,
            deps=deps,
            evidence_lookup=ev_lookup,
            doc_type_lookup=dt_lookup,
            trace_id=trace,
            run_id=trace,
            as_of=as_of,
        )
        before = (gateway.cost, gateway.calls)
        t0 = time.perf_counter()
        record: dict = {
            "case": case["case"],
            "skill": case["skill"],
            "dept": case["user"].dept.value,
            "input": case["input"],
            "expect": case["expect"],
            "expect_verdicts": case.get("expect_verdicts"),
            "sample_id": case.get("sample_id"),
        }
        try:
            run = registry.execute(case["skill"], "1.0.0", case["input"], context=ctx)
            out = run.output
            record.update(
                status=out.status.value,
                reason_codes=[c.value for c in out.reason_codes],
                detail=out.detail[:200],
                attempts=[f"{a.node}:{a.outcome}" for a in run.attempts],
                safety=run.safety.decision.value,
                output=out.model_dump(mode="json", exclude={"status", "reason_codes", "detail"}),
            )
        except MedOpsError as exc:
            record.update(
                status="error",
                error_code=exc.code.value,
                error_message=exc.message,
                error_detail=(exc.detail or "")[:200],
            )
        record["cost_usd"] = round(gateway.cost - before[0], 6)
        record["model_calls"] = gateway.calls - before[1]
        record["latency_s"] = round(time.perf_counter() - t0, 2)
        results.append(record)
        print(
            f"{case['case']}: {record['status']} {record.get('reason_codes') or record.get('error_code') or ''} calls={record['model_calls']} ${record['cost_usd']:.4f} {record['latency_s']}s",
            flush=True,
        )
    conn.close()
    args.out.mkdir(parents=True)
    summary = {
        "run": args.out.name,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "versions": versions.model_dump(),
        "n": len(results),
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "results": results,
    }
    (args.out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Skill smoke `{args.out.name}`",
        "",
        f"- {len(results)} cases · cost ${summary['total_cost_usd']} · answer {PRODUCTION_ANSWER_MODEL} · judge {PRODUCTION_JUDGE_MODEL} · skills {', '.join(versions.skill_version_set)}",
        "",
        "| case | expect | status | reason / error | verdicts | calls | cost | latency |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for r in results:
        verdicts = (
            ", ".join(
                v["verdict"] + ("" if not v.get("unknown_citations") else f" (unknown {len(v['unknown_citations'])})")
                for v in (r.get("output") or {}).get("verdicts", [])
            )
            or "—"
        )
        excerpts = len((r.get("output") or {}).get("excerpts", [])) if r["skill"] == "label_query" else None
        lines.append(
            f"| {r['case']} | {r['expect']} | {r['status']} | {', '.join(r.get('reason_codes') or []) or r.get('error_code') or '—'} | {verdicts if r['skill'] != 'label_query' else (f'{excerpts} excerpts' if excerpts is not None else '—')} | {r['model_calls']} | ${r['cost_usd']:.4f} | {r['latency_s']}s |"
        )
    (args.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "n": len(results),
                "cost": summary["total_cost_usd"],
                "statuses": {r["case"]: r["status"] for r in results},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
