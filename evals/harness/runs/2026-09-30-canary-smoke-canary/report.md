# Performance gate run canary-observation-canary (2026-09-30)

## Environment

- Host: Apple M3 / 24.0 GB / 8 CPUs / macOS-26.5.2-arm64-arm-64bit
- Python 3.11.16; torch 2.14.0, sentence-transformers 5.7.0, uvicorn 0.53.0, fastapi 0.141.1, psycopg 3.3.5, openai 2.54.0, httpx 0.28.1
- Device for embedding + reranker: mps (one pinned model thread per process)
- Models: {"answer": "gpt-6-sol", "judge": "gpt-6-sol", "verifier": "verifier-v2+support-rules-v3+polarity_only"}; retrieval {"k_lexical": 20, "k_vector": 20, "rrf_k": 60.0, "fused_limit": 20, "rerank_output": 8}
- PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) (shared_buffers 128MB, max_connections 100); database medops_v2: documents {"draft": 3, "archived": 7, "withdrawn": 7, "active": 333}, chunks 36100
- API: one uvicorn process (`canary-observation-canary`), ready after 10.2 s (model load); spans received 393
- Cost of this run: 0.2938 USD

## Ask levels (client wall time, seconds; nearest-rank percentiles)

| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| canary-smoke | 1 | 30 | 0 | 11.11 | 12.95 | 14.70 | 16.46 | 16.46 | 0.09 | ✗ |

### By outcome (p50 / p95 / n)

| level | answered | escalated |
| --- | --- | --- |
| canary-smoke | 11.12 / 14.70 / 26 | 8.32 / 12.54 / 4 |

### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)

| level | answer | escalate | intent | retrieve | safety | verify |
| --- | --- | --- | --- | --- | --- | --- |
| canary-smoke | 5279.80 / 8710.90 | 0.50 / 0.60 | 0.70 / 0.80 | 5861.50 / 6535.10 | 0.20 / 0.20 | 2.50 / 3.70 |

## Skill tasks (worker, one process)

- requested 0, completed 0, failed 0, worker exit None
- execution time per attempt: p50 — s, p95 — s, max — s (n=0); P95 ≤ 15 s: —
- end to end incl. queue wait behind one worker: p50 — s, p95 — s, max — s

## Gate

- 普通问答 P95 ≤ 8 s at every level: ✗
- 复杂 Skill P95 ≤ 15 s: — (not run)
