# End-to-end retrieval run `2026-09-22-e2e-main-v1-provisional-rerank-v1`

Dataset main-v1-provisional `269be665c288…` · as_of 2026-09-22 · RRF k=60.0 · channel k=20/20 · fused limit 20 · recheck then rerank (BAAI/bge-reranker-v2-m3, top 8) then top 5

## Strict macro Recall@5 after fact re-check

| system | all (n) | language_matched | cross_lingual | Hit@5 all | fused Recall@20 all | lexical-only R@5 | vector-only R@5 | P95 ms | gate (probe scale) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A2+V | 0.850 (553) | 0.877 | 0.807 | 0.850 | 0.866 | 0.322 | 0.763 | 5191.0 | fail |

## By department and slice (Recall@5, all frozen samples)

### A2+V

| group | n | Recall@5 |
| --- | ---: | ---: |
| CO | 186 | 0.817 |
| MA | 110 | 0.873 |
| PV | 257 | 0.864 |
| dose_unit | 65 | 0.877 |
| drug_name_zh | 90 | 0.867 |
| long_context | 23 | 0.696 |
| mixed_zh_en | 514 | 0.856 |
| negation | 275 | 0.865 |
| protocol_id | 146 | 0.808 |
| time_window | 128 | 0.945 |
| version_conflict | 52 | 0.885 |
| en | 412 | 0.835 |
| zh-Hans | 26 | 0.962 |
| zh-Hant | 115 | 0.878 |

- invalid-version citations in top 5: 0.0000 of 3070 · dropped by re-check: {} · leaks: 0 · non-reproducible: 0

## Subsets (A2+V)

| subset | n | Recall@5 | Hit@5 |
| --- | ---: | ---: | ---: |
| probe_imported | 107 | 0.682 | 0.682 |
| main_new | 446 | 0.890 | 0.890 |
| conflict | 52 | 0.885 | 0.885 |

## Version-conflict samples (A2+V)

- n = 52 · current version cited (Hit@5): 0.885 · historical version absent from top 5: 1.000 · both: 0.885 (gate 1.0)

## No-answer samples (A2+V)

- n = 61 · abstention rule: empty re-checked top list or reranker top score < threshold (provisional; M2 Verifier decides) · chosen threshold 0.3: accuracy 0.213 (gate 0.9), false abstention on answerable 0.011

| threshold | no-answer accuracy | false abstention (answerable) |
| ---: | ---: | ---: |
| 0.0 | 0.000 | 0.000 |
| 0.1 | 0.049 | 0.004 |
| 0.2 | 0.131 | 0.009 |
| 0.3 | 0.213 | 0.011 |
| 0.4 | 0.246 | 0.016 |
| 0.5 | 0.377 | 0.033 |

> **第二人工复核未完成**：数据集为 provisional 版本（spec-m1 §4 第 4 条），本报告的门禁结论为临时结论。

run_manifest sha256: `66ad531db59214ac1fdba6926175e9ce019cf609c35eea2138e37d606014234d`
