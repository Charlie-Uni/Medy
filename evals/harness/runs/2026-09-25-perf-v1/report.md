# Performance gate run perf-v1 (2026-09-25)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "active": 76}, chunks 11231
- API: one uvicorn process (`perf-v1`), ready after 20.4 s (model load); spans received 1496
- Cost of this run: 1.1576 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c1-cold | 1 | 30 | 14 | 9.21 | 23.19 | 72.49 | 84.25 | 84.25 | 0.07 | ✗ |
| c2 | 2 | 30 | 0 | 9.53 | 13.37 | 15.92 | 16.27 | 16.27 | 0.21 | ✗ |
| c4 | 4 | 30 | 0 | 17.84 | 22.52 | 23.43 | 25.97 | 25.97 | 0.21 | ✗ |
| c1-warm | 1 | 30 | 0 | 7.53 | 12.25 | 12.76 | 13.16 | 13.16 | 0.12 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| c1-cold | 11.67 / 84.25 / 12 | 5.83 / 72.49 / 18 |
| c2 | 10.00 / 15.92 / 23 | 6.01 / 13.72 / 7 |
| c4 | 18.59 / 23.43 / 24 | 13.65 / 20.92 / 6 |
| c1-warm | 7.53 / 12.58 / 24 | 5.12 / 12.76 / 6 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| c1-cold | 3038.20 / 199805.50 | 0.50 / 1.40 | 0.50 / 2.40 | 3598.90 / 750933.00 | 0.50 / 1.80 | 4.70 / 13.10 |
| c2 | 5360.20 / 8915.70 | 0.30 / 0.70 | 0.50 / 1.70 | 3407.00 / 8399.40 | 0.70 / 1.40 | 6.20 / 12.30 |
| c4 | 4957.20 / 7313.40 | 0.20 / 0.40 | 0.50 / 0.80 | 12543.40 / 18905.00 | 0.50 / 2.20 | 4.90 / 9.90 |
| c1-warm | 4830.10 / 10039.90 | 0.50 / 0.60 | 0.50 / 0.80 | 2562.00 / 3324.70 | 0.20 / 1.30 | 2.60 / 6.20 |

## Skill tasks (worker, one process)

- requested 8, completed 8, failed 0, worker exit 0
- execution time per attempt: p50 8.43 s, p95 13.53 s, max 13.53 s (n=8); P95 ≤ 15 s: ✓
- end to end incl. queue wait behind one worker: p50 61.51 s, p95 96.23 s, max 96.23 s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: ✓
