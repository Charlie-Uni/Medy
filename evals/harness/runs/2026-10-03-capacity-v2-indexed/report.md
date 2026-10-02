# Performance gate run capacity-v2-c8-c16-backlog-indexed-corpus (2026-10-02)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "withdrawn": 7, "active": 333}, chunks 36100
- API: one uvicorn process (`capacity-v2-c8-c16-backlog-indexed-corpus`), ready after 10.2 s (model load); spans received 1047
- Cost of this run: 0.2818 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c8 | 8 | 30 | 0 | 17.54 | 23.54 | 24.38 | 24.95 | 24.95 | 0.39 | ✗ |
| c16 | 16 | 30 | 24 | 60.72 | 60.90 | 60.98 | 61.01 | 61.01 | 0.25 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| c8 | 17.54 / 24.38 / 25 | 17.55 / 21.56 / 5 |
| c16 | 17.89 / 23.67 / 5 | 60.77 / 60.98 / 25 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| c8 | 4468.90 / 9310.90 | 0.10 / 0.10 | 0.30 / 2.60 | 13743.30 / 19507.20 | 0.20 / 0.50 | 2.30 / 5.40 |
| c16 | 4741.60 / 7522.50 | 0.20 / 2.00 | 3.40 / 54.30 | 60044.80 / 60087.80 | 0.20 / 0.40 | 3.00 / 6.20 |

## Skill tasks (worker, one process)

- requested 8, completed 8, failed 0, worker exit 0
- execution time per attempt: p50 10.86 s, p95 18.29 s, max 18.29 s (n=8); P95 ≤ 15 s: ✗
- end to end incl. queue wait behind one worker: p50 72.79 s, p95 113.34 s, max 113.34 s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: ✗
