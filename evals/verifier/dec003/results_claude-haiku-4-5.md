# DEC-003 arm `cli` (claude-haiku-4-5)

- pairs: 299 · accuracy: 0.9465 · unsafe accept rate (non-supported judged supported): 0.0529 · cost: $0.5713
- share of pairs decided by rules alone: 0.0

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 57 | 0.8772 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 84 | 1.0 |
| not_supported/same_doc | 69 | 0.8696 |
| supported | 72 | 1.0 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.9062 |
| drug_name_zh | 52 | 0.9808 |
| long_context | 13 | 0.8462 |
| mixed_zh_en | 279 | 0.9462 |
| negation | 151 | 0.9205 |
| protocol_id | 72 | 0.9722 |
| time_window | 83 | 0.9759 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 72 | 0 | 0 |
| not_supported | 6 | 144 | 3 |
| contradicted | 6 | 1 | 67 |
