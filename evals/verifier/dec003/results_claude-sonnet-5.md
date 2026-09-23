# DEC-003 arm `cli` (claude-sonnet-5)

- pairs: 300 · accuracy: 0.9567 · unsafe accept rate (non-supported judged supported): 0.0482 · cost: $1.1193
- share of pairs decided by rules alone: 0.0

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 58 | 0.8448 |
| contradicted/numeric | 17 | 1.0 |
| not_supported/other_doc | 84 | 1.0 |
| not_supported/same_doc | 69 | 0.942 |
| supported | 72 | 1.0 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 32 | 0.9688 |
| drug_name_zh | 52 | 0.9615 |
| long_context | 13 | 1.0 |
| mixed_zh_en | 280 | 0.9571 |
| negation | 152 | 0.9408 |
| protocol_id | 72 | 0.9722 |
| time_window | 83 | 0.9639 |
| version_conflict | 28 | 1.0 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 72 | 0 | 0 |
| not_supported | 2 | 149 | 2 |
| contradicted | 9 | 0 | 66 |
