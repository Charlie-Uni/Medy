# DEC-002 vector channel run `2026-09-20-dec002-bge-m3-v1`

Protocol: docs/adr/ADR-0007-embedding-and-reranker-selection.md · dataset v2 `1fc5089f6fa7…` · k=20 · as_of=2026-09-20 · device=cpu

Provider: `BAAI/bge-m3` @ `5617a9f61b02` (emb-bge-m3-dense-v1), index chunks 2662

## Strict macro Recall@20 by gate scope

| scope | queries | Recall@20 |
| --- | ---: | ---: |
| language_matched | 75 | 0.827 |
| cross_lingual | 32 | 0.656 |
| all frozen | 107 | 0.776 |

Diagnostic threshold (ADR-0007): cross_lingual Recall@20 >= 0.50 → **meets** (0.656).

## language_matched by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 16 | 0.562 |
| MA | 30 | 1.000 |
| PV | 29 | 0.793 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 19 | 1.000 |
| drug_name_zh | 18 | 1.000 |
| mixed_zh_en | 53 | 0.755 |
| negation | 38 | 0.895 |
| protocol_id | 17 | 0.588 |
| time_window | 19 | 1.000 |

## cross_lingual by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 16 | 0.562 |
| MA | 0 |  |
| PV | 16 | 0.750 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 0 |  |
| drug_name_zh | 0 |  |
| mixed_zh_en | 32 | 0.656 |
| negation | 18 | 0.833 |
| protocol_id | 12 | 0.417 |
| time_window | 9 | 1.000 |

## Integrity

- leak violations: 0
- non-reproducible queries: 0
- candidate_exhausted queries: 0 · zero-result queries: 0
- latency ms (measured passes, embedding + database): p95 138.4 · mean 100.1 · max 898.8
- run_manifest sha256: `90f435810d731f6f2579528891181add7ce853383e8d71b18effde4980098b8a`
