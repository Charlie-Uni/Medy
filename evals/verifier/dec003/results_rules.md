# DEC-003 arm `rules` (verifier-v2+support-rules-v2+polarity_only)

- pairs: 2076 · accuracy: 0.8839 · unsafe accept rate (non-supported judged supported): 0.0379 · cost: $0.0
- share of pairs decided by rules alone: 0.3613

| kind | n | accuracy |
| --- | ---: | ---: |
| contradicted/negation | 290 | 0.8483 |
| contradicted/numeric | 148 | 0.6959 |
| not_supported/other_doc | 546 | 0.9853 |
| not_supported/same_doc | 546 | 0.8883 |
| supported | 546 | 0.848 |

| slice | n | accuracy |
| --- | ---: | ---: |
| dose_unit | 266 | 0.7669 |
| drug_name_zh | 360 | 0.8389 |
| long_context | 74 | 0.9054 |
| mixed_zh_en | 1924 | 0.8909 |
| negation | 1057 | 0.895 |
| protocol_id | 527 | 0.8653 |
| time_window | 533 | 0.8668 |
| version_conflict | 184 | 0.8913 |

| label \ pred | supported | not_supported | contradicted |
| --- | ---: | ---: | ---: |
| supported | 463 | 31 | 52 |
| not_supported | 28 | 1023 | 41 |
| contradicted | 30 | 59 | 349 |
