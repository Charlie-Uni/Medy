# DEC-003 arm `openai-hybrid` (gpt-6-sol)

- pairs: 300 · accuracy: 0.9567 · unsafe accept rate (non-supported judged supported): 0.0219 · cost: $0.3259
- share of pairs decided by rules alone: 0.3133

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 58 | 0.9655 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 84 | 1.0 |
| not_supported/same_doc | 69 | 0.8841 |
| supported | 72 | 0.9583 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.875 |
| drug_name_zh | 52 | 0.9423 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 280 | 0.9571 |
| negation | 152 | 0.9474 |
| protocol_id | 72 | 0.9583 |
| time_window | 83 | 0.9759 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 69 | 0 | 3 |
| not_supported | 3 | 145 | 5 |
| contradicted | 2 | 0 | 73 |
