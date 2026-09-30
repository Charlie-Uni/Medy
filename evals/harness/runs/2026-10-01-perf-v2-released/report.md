# Performance gate run perf-v2-released-full (2026-09-30)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "withdrawn": 7, "active": 333}, chunks 36100
- API: one uvicorn process (`perf-v2-released-full`), ready after 10.1 s (model load); spans received 1584
- Cost of this run: 1.1553 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c1-cold | 1 | 30 | 0 | 11.02 | 14.53 | 17.46 | 19.71 | 19.71 | 0.09 | ✗ |
| c2 | 2 | 30 | 0 | 11.50 | 15.61 | 18.18 | 21.43 | 21.43 | 0.16 | ✗ |
| c4 | 4 | 30 | 0 | 11.32 | 14.71 | 15.59 | 16.87 | 16.87 | 0.34 | ✗ |
| c1-warm | 1 | 30 | 0 | 10.69 | 14.43 | 17.72 | 17.73 | 17.73 | 0.09 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| c1-cold | 11.13 / 17.46 / 25 | 8.12 / 14.53 / 5 |
| c2 | 11.82 / 18.18 / 26 | 7.40 / 9.05 / 4 |
| c4 | 11.78 / 15.59 / 23 | 7.71 / 14.70 / 7 |
| c1-warm | 10.90 / 17.72 / 26 | 8.29 / 13.28 / 4 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| c1-cold | 5368.20 / 12700.40 | 0.50 / 0.70 | 0.60 / 0.80 | 5351.50 / 7512.10 | 0.20 / 0.30 | 2.50 / 3.60 |
| c2 | 5303.80 / 12993.80 | 0.40 / 0.60 | 0.60 / 0.80 | 5939.90 / 7595.40 | 0.20 / 0.30 | 2.30 / 3.10 |
| c4 | 5432.40 / 9084.20 | 0.10 / 0.30 | 0.20 / 0.80 | 5693.10 / 8728.50 | 0.20 / 0.50 | 2.40 / 5.70 |
| c1-warm | 5349.90 / 10721.50 | 0.50 / 0.60 | 0.70 / 0.90 | 5462.10 / 7593.80 | 0.20 / 0.20 | 2.60 / 5.40 |

## Skill tasks (worker, one process)

- requested 8, completed 0, failed 0, worker exit None
- execution time per attempt: p50 — s, p95 — s, max — s (n=0); P95 ≤ 15 s: —
- end to end incl. queue wait behind one worker: p50 — s, p95 — s, max — s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: — (not run)
