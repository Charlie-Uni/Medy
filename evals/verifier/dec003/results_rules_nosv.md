# DEC-003 arm `rules-nosv` (verifier-v2+support-rules-v2+polarity_only)

- pairs: 2076 · accuracy: 0.881 · unsafe accept rate (non-supported judged supported): 0.0412 · cost: $0.0
- share of pairs decided by rules alone: 0.354

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 290 | 0.9241 |
| contradicted/numeric | 148 | 0.0608 |
| not_supported/other_doc | 546 | 1.0 |
| not_supported/same_doc | 546 | 0.9084 |
| supported | 546 | 0.9341 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 266 | 0.7744 |
| drug_name_zh | 360 | 0.8111 |
| long_context | 74 | 0.9459 |
| mixed_zh_en | 1924 | 0.8888 |
| negation | 1057 | 0.9092 |
| protocol_id | 527 | 0.8956 |
| time_window | 533 | 0.7561 |
| version_conflict | 184 | 0.9022 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 510 | 8 | 28 |
| not_supported | 30 | 1042 | 20 |
| contradicted | 33 | 128 | 277 |
