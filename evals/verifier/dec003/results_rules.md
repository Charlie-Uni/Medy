# DEC-003 arm `rules` (verifier-v2+support-rules-v2+polarity_only)

- pairs: 2076 · accuracy: 0.9128 · unsafe accept rate (non-supported judged supported): 0.0412 · cost: $0.0
- share of pairs decided by rules alone: 0.4133

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 290 | 0.9241 |
| contradicted/numeric | 148 | 0.7162 |
| not_supported/other_doc | 546 | 0.9853 |
| not_supported/same_doc | 546 | 0.8663 |
| supported | 546 | 0.9341 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 266 | 0.782 |
| drug_name_zh | 360 | 0.8417 |
| long_context | 74 | 0.9459 |
| mixed_zh_en | 1924 | 0.921 |
| negation | 1057 | 0.9281 |
| protocol_id | 527 | 0.9298 |
| time_window | 533 | 0.8743 |
| version_conflict | 184 | 0.9457 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 510 | 8 | 28 |
| not_supported | 30 | 1011 | 51 |
| contradicted | 33 | 31 | 374 |
