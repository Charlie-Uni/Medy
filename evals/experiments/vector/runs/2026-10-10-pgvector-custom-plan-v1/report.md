# DEC-002 vector channel run `2026-10-10-pgvector-custom-plan-v1`

Protocol: docs/adr/ADR-0007-embedding-and-reranker-selection.md · dataset v4 `1427274ecd04…` · k=20 · as_of=2026-10-09 · device=mps

Provider: `BAAI/bge-m3` @ `5617a9f61b02` (emb-bge-m3-dense-v1), index chunks 35830

## Strict macro Recall@20 by gate scope

| scope | queries | Recall@20 |
| --- | ---: | ---: |
| language_matched | 75 | 0.680 |
| cross_lingual | 32 | 0.562 |
| selected frozen | 107 | 0.645 |

Diagnostic threshold (ADR-0007): cross_lingual Recall@20 >= 0.50 → **meets** (0.562).

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
| PV | 16 | 0.625 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 0 |  |
| drug_name_zh | 0 |  |
| mixed_zh_en | 32 | 0.562 |
| negation | 18 | 0.722 |
| protocol_id | 12 | 0.333 |
| time_window | 9 | 1.000 |

## Integrity

- leak violations: 0
- non-reproducible queries: 0
- candidate_exhausted queries: 0 · zero-result queries: 0
- latency ms (measured passes, embedding + database): p95 193.7 · mean 133.4 · max 296.3
- run_manifest sha256: `e20daf8613b24c96f62bcceedee2ad434a426af345e0a8355deda986139588ff`

## Query selection

- scope: all · source queries: 107 · selected: 107 · excluded without gold: 0
- unmappable gold: keep in the recall denominator as misses
- Repeatability compares every saved ranking, including warmup passes.
