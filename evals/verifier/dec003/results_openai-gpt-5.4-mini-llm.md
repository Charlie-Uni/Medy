# DEC-003 arm `openai-llm` (gpt-5.4-mini)

- pairs: 300 · accuracy: 0.8967 · unsafe accept rate (non-supported judged supported): 0.1096 · cost: $0.1699
- share of pairs decided by rules alone: 0.0

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 58 | 0.6897 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 84 | 0.9881 |
| not_supported/same_doc | 69 | 0.8261 |
| supported | 72 | 1.0 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.9062 |
| drug_name_zh | 52 | 0.9038 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 280 | 0.8964 |
| negation | 152 | 0.8684 |
| protocol_id | 72 | 0.875 |
| time_window | 83 | 0.9157 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 72 | 0 | 0 |
| not_supported | 7 | 140 | 6 |
| contradicted | 18 | 0 | 57 |
