# End-to-end retrieval run `2026-09-20-e2e-hybrid-v1`

Dataset v2 `1fc5089f6fa7…` · as_of 2026-09-20 · RRF k=60.0 · channel k=20/20 · fused limit 20 · recheck then top 5

## Strict macro Recall@5 after fact re-check

| system | all (n) | language_matched | cross_lingual | Hit@5 all | fused Recall@20 all | lexical-only R@5 | vector-only R@5 | P95 ms | gate (probe scale) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A2+V | 0.542 (107) | 0.640 | 0.312 | 0.542 | 0.794 | 0.383 | 0.701 | 164.9 | fail |
| B2+V | 0.589 (107) | 0.693 | 0.344 | 0.589 | 0.794 | 0.411 | 0.701 | 186.1 | fail |

## By department and slice (Recall@5, all frozen samples)

### A2+V

| group | n | Recall@5 |
| --- | ---: | ---: |
| CO | 32 | 0.281 |
| MA | 30 | 0.800 |
| PV | 45 | 0.556 |
| dose_unit | 19 | 0.842 |
| drug_name_zh | 18 | 0.722 |
| mixed_zh_en | 85 | 0.518 |
| negation | 56 | 0.554 |
| protocol_id | 29 | 0.310 |
| time_window | 28 | 0.857 |
| en | 64 | 0.391 |
| zh-Hans | 10 | 0.800 |
| zh-Hant | 33 | 0.758 |

- invalid-version citations in top 5: 0.0000 of 535 · dropped by re-check: {} · leaks: 0 · non-reproducible: 0

### B2+V

| group | n | Recall@5 |
| --- | ---: | ---: |
| CO | 32 | 0.344 |
| MA | 30 | 0.900 |
| PV | 45 | 0.556 |
| dose_unit | 19 | 0.895 |
| drug_name_zh | 18 | 0.944 |
| mixed_zh_en | 85 | 0.518 |
| negation | 56 | 0.625 |
| protocol_id | 29 | 0.310 |
| time_window | 28 | 0.857 |
| en | 64 | 0.391 |
| zh-Hans | 10 | 0.800 |
| zh-Hant | 33 | 0.909 |

- invalid-version citations in top 5: 0.0000 of 535 · dropped by re-check: {} · leaks: 0 · non-reproducible: 0

## Paired bootstrap on Recall@5 (all frozen samples)

- B2+V minus A2+V: +4.67 pp, 95% CI [-1.87, +11.21] (10000 resamples)

run_manifest sha256: `cdd7aca21ebd63ec0a19ada9fa6f839953663415eb4afbfacf42fdf5fc9f3a4c`
