# DEC-002 vector channel run `2026-10-10-pgvector-auto-plan-v1`

Protocol: docs/adr/ADR-0007-embedding-and-reranker-selection.md · dataset v4 `1427274ecd04…` · k=20 · as_of=2026-10-09 · device=mps

Provider: `BAAI/bge-m3` @ `5617a9f61b02` (emb-bge-m3-dense-v1), index chunks 35830

## Strict macro Recall@20 by gate scope

| scope | queries | Recall@20 |
| --- | ---: | ---: |
| language_matched | 75 | 0.680 |
| cross_lingual | 32 | 0.594 |
| all frozen | 107 | 0.654 |

Diagnostic threshold (ADR-0007): cross_lingual Recall@20 >= 0.50 → **meets** (0.594).

## language_matched by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 16 | 0.562 |
| MA | 30 | 0.667 |
| PV | 29 | 0.759 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 19 | 0.789 |
| drug_name_zh | 21 | 0.714 |
| mixed_zh_en | 53 | 0.717 |
| negation | 38 | 0.763 |
| protocol_id | 17 | 0.353 |
| time_window | 19 | 0.895 |

## cross_lingual by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 16 | 0.500 |
| MA | 0 |  |
| PV | 16 | 0.688 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 0 |  |
| drug_name_zh | 0 |  |
| mixed_zh_en | 32 | 0.594 |
| negation | 18 | 0.778 |
| protocol_id | 12 | 0.333 |
| time_window | 9 | 1.000 |

## Integrity

- leak violations: 0
- non-reproducible queries: 1
- candidate_exhausted queries: 0 · zero-result queries: 0
- latency ms (measured passes, embedding + database): p95 342.4 · mean 240.4 · max 421.7
- run_manifest sha256: `09230ebe57bfd2e1cbde4af7860d0f6e408dcf7280594a0378f0b5c34dbe6ecc`
