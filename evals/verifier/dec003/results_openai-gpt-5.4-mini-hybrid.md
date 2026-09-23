# DEC-003 arm `openai-hybrid` (gpt-5.4-mini)

- pairs: 300 · accuracy: 0.9 · unsafe accept rate (non-supported judged supported): 0.0789 · cost: $0.1198
- share of pairs decided by rules alone: 0.3133

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 58 | 0.8103 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 84 | 0.9881 |
| not_supported/same_doc | 69 | 0.7826 |
| supported | 72 | 0.9583 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.875 |
| drug_name_zh | 52 | 0.8846 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 280 | 0.9 |
| negation | 152 | 0.875 |
| protocol_id | 72 | 0.8611 |
| time_window | 83 | 0.9398 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 69 | 0 | 3 |
| not_supported | 7 | 137 | 9 |
| contradicted | 11 | 0 | 64 |
