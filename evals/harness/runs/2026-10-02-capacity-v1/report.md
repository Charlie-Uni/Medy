# Performance gate run capacity-v1-c8-c16-backlog (2026-10-01)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "withdrawn": 7, "active": 333}, chunks 36100
- API: one uvicorn process (`capacity-v1-c8-c16-backlog`), ready after 11.2 s (model load); spans received 1178
- Cost of this run: 0.4756 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c8 | 8 | 30 | 0 | 19.01 | 39.22 | 41.27 | 41.75 | 41.75 | 0.32 | ✗ |
| c16 | 16 | 30 | 23 | 60.69 | 60.98 | 61.00 | 61.02 | 61.02 | 0.25 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| c8 | 19.87 / 39.92 / 25 | 17.85 / 41.27 / 5 |
| c16 | 16.95 / 28.99 / 7 | 60.77 / 61.00 / 23 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| c8 | 4833.60 / 8798.10 | 0.10 / 0.10 | 0.20 / 1.20 | 14311.90 / 37265.30 | 0.20 / 0.50 | 2.30 / 5.20 |
| c16 | 5238.80 / 10161.70 | 0.20 / 0.70 | 1.30 / 43.10 | 60040.10 / 60139.50 | 0.20 / 0.50 | 2.40 / 4.50 |

## Skill tasks (worker, one process)

- requested 8, completed 8, failed 0, worker exit 0
- execution time per attempt: p50 9.99 s, p95 16.88 s, max 16.88 s (n=8); P95 ≤ 15 s: ✗
- end to end incl. queue wait behind one worker: p50 160.96 s, p95 200.90 s, max 200.90 s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: ✗
