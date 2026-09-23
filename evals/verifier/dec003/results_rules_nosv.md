# DEC-003 arm `rules-nosv` (verifier-v1+support-rules-v1)

- pairs: 2076 · accuracy: 0.8776 · unsafe accept rate (non-supported judged supported): 0.0516 · cost: $0.0
- share of pairs decided by rules alone: 0.3622

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 290 | 0.9 |
| contradicted/numeric | 148 | 0.0405 |
| not_supported/other_doc | 546 | 1.0 |
| not_supported/same_doc | 546 | 0.8938 |
| supported | 546 | 0.9542 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 266 | 0.7481 |
| drug_name_zh | 360 | 0.7917 |
| long_context | 74 | 0.9459 |
| mixed_zh_en | 1924 | 0.8851 |
| negation | 1057 | 0.9007 |
| protocol_id | 527 | 0.8937 |
| time_window | 533 | 0.7523 |
| version_conflict | 184 | 0.9022 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 521 | 0 | 25 |
| not_supported | 35 | 1034 | 23 |
| contradicted | 44 | 127 | 267 |
