# DEC-003 arm `openai-hybrid` (gpt-6-luna)

- pairs: 300 · accuracy: 0.9367 · unsafe accept rate (non-supported judged supported): 0.0439 · cost: $0.0175
- share of pairs decided by rules alone: 0.3133

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 58 | 0.8621 |
| contradicted/numeric | 17 | 0.9412 |
| not_supported/other_doc | 84 | 1.0 |
| not_supported/same_doc | 69 | 0.8986 |
| supported | 72 | 0.9583 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.8438 |
| drug_name_zh | 52 | 0.9231 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 280 | 0.9357 |
| negation | 152 | 0.9079 |
| protocol_id | 72 | 0.9444 |
| time_window | 83 | 0.9759 |
| version_conflict | 28 | 0.9643 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 69 | 0 | 3 |
| not_supported | 3 | 146 | 4 |
| contradicted | 7 | 2 | 66 |
