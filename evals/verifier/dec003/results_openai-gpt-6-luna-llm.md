# DEC-003 arm `openai-llm` (gpt-6-luna)

- pairs: 297 · accuracy: 0.9596 · unsafe accept rate (non-supported judged supported): 0.0489 · cost: $0.0239
- share of pairs decided by rules alone: 0.0

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 57 | 0.8421 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 82 | 1.0 |
| not_supported/same_doc | 69 | 0.9565 |
| supported | 72 | 1.0 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.9062 |
| drug_name_zh | 52 | 0.9615 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 277 | 0.9603 |
| negation | 152 | 0.9408 |
| protocol_id | 70 | 0.9571 |
| time_window | 83 | 0.988 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 72 | 0 | 0 |
| not_supported | 3 | 148 | 0 |
| contradicted | 8 | 1 | 65 |
