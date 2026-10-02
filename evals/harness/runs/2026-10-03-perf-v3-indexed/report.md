# Performance gate run perf-v3-released-indexed-corpus (2026-10-02)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "withdrawn": 7, "active": 333}, chunks 36100
- API: one uvicorn process (`perf-v3-released-indexed-corpus`), ready after 11.2 s (model load); spans received 1700
- Cost of this run: 1.297 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c1-cold | 1 | 30 | 0 | 9.40 | 12.52 | 13.78 | 21.16 | 21.16 | 0.10 | ✗ |
| c2 | 2 | 30 | 0 | 9.40 | 13.64 | 14.06 | 16.96 | 16.96 | 0.19 | ✗ |
| c4 | 4 | 30 | 0 | 10.49 | 13.93 | 15.19 | 16.18 | 16.18 | 0.35 | ✗ |
| c1-warm | 1 | 30 | 0 | 9.55 | 13.28 | 14.11 | 17.51 | 17.51 | 0.10 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| c1-cold | 9.54 / 13.78 / 26 | 6.72 / 7.00 / 4 |
| c2 | 10.04 / 14.06 / 24 | 6.97 / 8.60 / 6 |
| c4 | 10.80 / 15.19 / 22 | 9.03 / 13.86 / 8 |
| c1-warm | 9.73 / 14.11 / 26 | 7.17 / 13.28 / 4 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| c1-cold | 4067.80 / 8094.70 | 0.50 / 0.50 | 0.70 / 0.90 | 5250.40 / 6231.80 | 0.20 / 0.20 | 2.50 / 4.30 |
| c2 | 4538.10 / 9894.30 | 0.50 / 0.60 | 0.60 / 0.80 | 4937.40 / 6273.40 | 0.20 / 0.20 | 2.20 / 4.10 |
| c4 | 4149.40 / 7461.30 | 0.10 / 0.30 | 0.30 / 0.70 | 6357.60 / 11180.40 | 0.20 / 0.30 | 2.30 / 3.70 |
| c1-warm | 4125.00 / 9275.20 | 0.30 / 0.50 | 0.70 / 0.90 | 5165.40 / 5840.00 | 0.20 / 0.30 | 2.50 / 5.40 |

## Skill tasks (worker, one process)

- requested 8, completed 8, failed 0, worker exit 0
- execution time per attempt: p50 9.81 s, p95 17.08 s, max 17.08 s (n=8); P95 ≤ 15 s: ✗
- end to end incl. queue wait behind one worker: p50 67.28 s, p95 113.21 s, max 113.21 s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: ✗
