"""Compare sequential lexical/vector search with an optimistic two-connection overlap.

This benchmark uses the production BM25 and local embedding implementations against the configured database.
It never calls the hosted LLM gateway. The parallel arm keeps both database connections open for the whole run,
so its timing is an upper bound on the benefit available to the request path, which currently opens connections
per request.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
from typing import Any, TypedDict

import psycopg

from medops.core.config import Settings
from medops.domain.common import Dept
from medops.retrieval.lexical.boundary import run_lexical_search
from medops.retrieval.pinned import PinnedEmbedding, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    production_lexical_retriever,
    production_lexical_versions,
    production_vector_retriever,
)
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

QUERIES = (
    "根据 GVP Module IV，药物警戒审计发现应如何分级？",
    "什么情况下需要提交 SUSAR，时限是多少？",
    "Risperdal 的常见不良反应有哪些？",
    "ICH E2B(R3) 中发送方标识符如何填写？",
    "临床试验中发生危及生命的非预期严重不良反应后应如何报告？",
    "定期安全性更新报告的国际诞生日如何确定？",
    "上市许可持有人发现新的安全信号后需要采取什么措施？",
    "妊娠期间暴露的个例安全性报告应记录哪些信息？",
)


class _Row(TypedDict):
    mode: str
    total_ms: float
    lexical_ms: float
    vector_ms: float


def _nearest_rank(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    rank = max(1, (len(ordered) * percentile + 99) // 100)
    return ordered[min(len(ordered), rank) - 1]


def _summary(rows: list[_Row], mode: str) -> dict[str, float]:
    values = [row["total_ms"] for row in rows if row["mode"] == mode]
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_nearest_rank(values, 95), 2),
        "mean_ms": round(statistics.mean(values), 2),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def run(*, device: str, dept: Dept, rounds: int) -> dict[str, Any]:
    settings = Settings()
    dsn = settings.database_url.get_secret_value()
    pinned = PinnedThread(timeout_s=120)
    provider = PinnedEmbedding(pinned.call(lambda: BgeM3EmbeddingProvider(device=device)), pinned)
    rows: list[_Row] = []
    expected_orders: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    variation = {
        mode: {
            channel: {"comparisons": 0, "order_changes": 0, "set_changes": 0, "min_overlap_at_20": 20}
            for channel in ("lexical", "vector")
        }
        for mode in ("sequential", "parallel")
    }

    with (
        psycopg.connect(dsn) as lexical_conn,
        psycopg.connect(dsn) as vector_conn,
        lexical_conn.transaction(),
        vector_conn.transaction(),
    ):
        for conn in (lexical_conn, vector_conn):
            conn.execute("select set_config('medops.dept', %s, true)", (dept.value,))
        lexical = production_lexical_retriever(lexical_conn)
        vector = production_vector_retriever(vector_conn, provider)
        lexical_expected = production_lexical_versions()
        vector_expected = vector.versions

        def lexical_call(query: str) -> tuple[float, tuple[str, ...]]:
            started = time.perf_counter()
            result = run_lexical_search(lexical, query, 20, expected=lexical_expected)
            return (time.perf_counter() - started) * 1000, tuple(c.chunk_id for c in result.candidates)

        def vector_call(query: str) -> tuple[float, tuple[str, ...]]:
            started = time.perf_counter()
            result = run_vector_search(vector, query, 20, expected=vector_expected)
            return (time.perf_counter() - started) * 1000, tuple(c.chunk_id for c in result.candidates)

        lexical_call(QUERIES[0])
        vector_call(QUERIES[0])
        with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="benchmark-lexical") as pool:
            for round_no in range(rounds):
                for query_no, query in enumerate(QUERIES):
                    modes = (
                        ("parallel", "sequential")
                        if (round_no + query_no) % 2 == 0
                        else (
                            "sequential",
                            "parallel",
                        )
                    )
                    for mode in modes:
                        started = time.perf_counter()
                        if mode == "sequential":
                            lexical_ms, lexical_ids = lexical_call(query)
                            vector_ms, vector_ids = vector_call(query)
                        else:
                            lexical_future = pool.submit(lexical_call, query)
                            vector_ms, vector_ids = vector_call(query)
                            lexical_ms, lexical_ids = lexical_future.result()
                        orders = (lexical_ids, vector_ids)
                        if query in expected_orders:
                            expected_lexical, expected_vector = expected_orders[query]
                            for channel, expected, actual in (
                                ("lexical", expected_lexical, lexical_ids),
                                ("vector", expected_vector, vector_ids),
                            ):
                                stats = variation[mode][channel]
                                stats["comparisons"] += 1
                                if expected != actual:
                                    stats["order_changes"] += 1
                                overlap = len(set(expected) & set(actual))
                                if set(expected) != set(actual):
                                    stats["set_changes"] += 1
                                stats["min_overlap_at_20"] = min(stats["min_overlap_at_20"], overlap)
                        expected_orders.setdefault(query, orders)
                        rows.append(
                            {
                                "mode": mode,
                                "total_ms": (time.perf_counter() - started) * 1000,
                                "lexical_ms": lexical_ms,
                                "vector_ms": vector_ms,
                            }
                        )

    sequential = [row for row in rows if row["mode"] == "sequential"]
    parallel = [row for row in rows if row["mode"] == "parallel"]
    sequential_summary = _summary(rows, "sequential")
    parallel_summary = _summary(rows, "parallel")
    delta = parallel_summary["p50_ms"] - sequential_summary["p50_ms"]
    return {
        "device": device,
        "dept": dept.value,
        "queries": len(QUERIES),
        "rounds": rounds,
        "n_per_mode": len(sequential),
        "method": "alternating adjacent arms; two pre-opened identity-bound connections; hosted LLM calls disabled",
        "production_retrieval_version": PRODUCTION_RETRIEVAL_VERSION,
        "lexical_versions": lexical_expected.model_dump(mode="json"),
        "vector_versions": vector_expected.model_dump(mode="json"),
        "channel_variation_against_first_run": variation,
        "sequential": sequential_summary,
        "parallel": parallel_summary,
        "channels": {
            "sequential_lexical_p50_ms": round(statistics.median(row["lexical_ms"] for row in sequential), 2),
            "sequential_vector_p50_ms": round(statistics.median(row["vector_ms"] for row in sequential), 2),
            "parallel_lexical_p50_ms": round(statistics.median(row["lexical_ms"] for row in parallel), 2),
            "parallel_vector_p50_ms": round(statistics.median(row["vector_ms"] for row in parallel), 2),
        },
        "parallel_minus_sequential_p50_ms": round(delta, 2),
        "parallel_minus_sequential_p50_pct": round(100 * delta / sequential_summary["p50_ms"], 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dept", choices=[dept.value for dept in Dept], default=Dept.MA.value)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    print(json.dumps(run(device=args.device, dept=Dept(args.dept), rounds=args.rounds), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
