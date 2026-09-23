# DEC-003 arm `rules` (verifier-v1+support-rules-v1)

- pairs: 2076 · accuracy: 0.9104 · unsafe accept rate (non-supported judged supported): 0.0516 · cost: $0.0
- share of pairs decided by rules alone: 0.4215

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 290 | 0.9 |
| contradicted/numeric | 148 | 0.7095 |
| not_supported/other_doc | 546 | 0.9853 |
| not_supported/same_doc | 546 | 0.8516 |
| supported | 546 | 0.9542 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 266 | 0.7556 |
| drug_name_zh | 360 | 0.8222 |
| long_context | 74 | 0.9459 |
| mixed_zh_en | 1924 | 0.9184 |
| negation | 1057 | 0.9196 |
| protocol_id | 527 | 0.9317 |
| time_window | 533 | 0.8743 |
| version_conflict | 184 | 0.9457 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 521 | 0 | 25 |
| not_supported | 35 | 1003 | 54 |
| contradicted | 44 | 28 | 366 |
