# DEC-002 vector channel run `2026-10-10-main-v5-custom-plan-v1`

Protocol: docs/adr/ADR-0007-embedding-and-reranker-selection.md · dataset main-v5-provisional `23bf8530d63f…` · k=20 · as_of=2026-10-09 · device=mps

Provider: `BAAI/bge-m3` @ `5617a9f61b02` (emb-bge-m3-dense-v1), index chunks 35830

## Strict macro Recall@20 by gate scope

| scope | queries | Recall@20 |
| --- | ---: | ---: |
| language_matched | 341 | 0.855 |
| cross_lingual | 213 | 0.787 |
| selected frozen | 554 | 0.829 |

Diagnostic threshold (ADR-0007): cross_lingual Recall@20 >= 0.50 → **meets** (0.787).

## language_matched by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 91 | 0.855 |
| MA | 110 | 0.836 |
| PV | 140 | 0.870 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 59 | 0.847 |
| drug_name_zh | 93 | 0.849 |
| mixed_zh_en | 302 | 0.870 |
| negation | 170 | 0.872 |
| protocol_id | 78 | 0.786 |
| time_window | 79 | 0.937 |

## cross_lingual by department / slice

| department | n | strict macro Recall@20 |
| --- | ---: | ---: |
| CO | 95 | 0.751 |
| MA | 0 |  |
| PV | 118 | 0.816 |

| slice | n | strict macro Recall@20 |
| --- | ---: | ---: |
| dose_unit | 6 | 0.500 (diagnostic: n < 8) |
| drug_name_zh | 0 |  |
| mixed_zh_en | 213 | 0.787 |
| negation | 105 | 0.834 |
| protocol_id | 69 | 0.748 |
| time_window | 49 | 0.939 |

## Integrity

- leak violations: 0
- non-reproducible queries: 0
- candidate_exhausted queries: 0 · zero-result queries: 0
- latency ms (measured passes, embedding + database): p95 195.0 · mean 145.5 · max 863.8
- run_manifest sha256: `5a095f848b88805000f5ee796967e3187bd403121ae3d05a4621b13eac5381b6`

## Query selection

- scope: gold_only · source queries: 615 · selected: 554 · excluded without gold: 61
- unmappable gold: keep in the recall denominator as misses
- Only one pass: repeatability was not assessed.
