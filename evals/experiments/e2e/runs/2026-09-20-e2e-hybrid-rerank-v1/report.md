# End-to-end retrieval run `2026-09-20-e2e-hybrid-rerank-v1`

Dataset v2 `1fc5089f6fa7…` · as_of 2026-09-20 · RRF k=60.0 · channel k=20/20 · fused limit 20 · recheck then rerank (BAAI/bge-reranker-v2-m3, top 8) then top 5

## Strict macro Recall@5 after fact re-check

| system | all (n) | language_matched | cross_lingual | Hit@5 all | fused Recall@20 all | lexical-only R@5 | vector-only R@5 | P95 ms | gate (probe scale) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A2+V | 0.757 (107) | 0.813 | 0.625 | 0.757 | 0.794 | 0.383 | 0.701 | 7567.1 | fail |
| B2+V | 0.757 (107) | 0.827 | 0.594 | 0.757 | 0.794 | 0.411 | 0.701 | 8877.2 | fail |

## By department and slice (Recall@5, all frozen samples)

### A2+V

| group | n | Recall@5 |
| --- | ---: | ---: |
| CO | 32 | 0.562 |
| MA | 30 | 0.933 |
| PV | 45 | 0.778 |
| dose_unit | 19 | 0.947 |
| drug_name_zh | 18 | 0.889 |
| mixed_zh_en | 85 | 0.718 |
| negation | 56 | 0.821 |
| protocol_id | 29 | 0.517 |
| time_window | 28 | 1.000 |
| en | 64 | 0.625 |
| zh-Hans | 10 | 1.000 |
| zh-Hant | 33 | 0.939 |

- invalid-version citations in top 5: 0.0000 of 535 · dropped by re-check: {} · leaks: 0 · non-reproducible: 0

### B2+V

| group | n | Recall@5 |
| --- | ---: | ---: |
| CO | 32 | 0.531 |
| MA | 30 | 0.967 |
| PV | 45 | 0.778 |
| dose_unit | 19 | 0.947 |
| drug_name_zh | 18 | 0.944 |
| mixed_zh_en | 85 | 0.706 |
| negation | 56 | 0.839 |
| protocol_id | 29 | 0.483 |
| time_window | 28 | 1.000 |
| en | 64 | 0.609 |
| zh-Hans | 10 | 1.000 |
| zh-Hant | 33 | 0.970 |

- invalid-version citations in top 5: 0.0000 of 535 · dropped by re-check: {} · leaks: 0 · non-reproducible: 0

## Paired bootstrap on Recall@5 (all frozen samples)

- B2+V minus A2+V: +0.00 pp, 95% CI [-2.80, +2.80] (10000 resamples)

run_manifest sha256: `7b656625ef9c2e3538309433707abbef9487b6a0683934d721ecc395f4e497f1`
