# DEC-003 arm comparison on 299 shared pairs

| arm | accuracy | unsafe accept | contradicted/negation | contradicted/numeric | not_supported/other_doc | not_supported/same_doc | supported | cost (USD, API-equivalent) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules:verifier-v1+support-rules-v1 | 0.923 | 0.040 | 0.930 | 0.765 | 0.976 | 0.841 | 0.972 | 0.00 |
| cli:claude-haiku-4-5 | 0.946 | 0.053 | 0.877 | 1.000 | 1.000 | 0.870 | 1.000 | 0.57 |
| cli:claude-sonnet-5 | 0.957 | 0.048 | 0.842 | 1.000 | 1.000 | 0.942 | 1.000 | 1.12 |

## By slice (accuracy; n in the first arm)

| slice | n | rules:verifier-v1+support-rules-v1 | cli:claude-haiku-4-5 | cli:claude-sonnet-5 |
| --- | ---: | ---: | ---: | ---: |
| dose_unit | 32 | 0.781 | 0.906 | 0.969 |
| drug_name_zh | 52 | 0.827 | 0.981 | 0.962 |
| long_context | 13 | 1.000 | 0.846 | 1.000 |
| mixed_zh_en | 279 | 0.939 | 0.946 | 0.957 |
| negation | 151 | 0.927 | 0.921 | 0.940 |
| protocol_id | 72 | 0.944 | 0.972 | 0.972 |
| time_window | 83 | 0.904 | 0.976 | 0.964 |
| version_conflict | 28 | 0.964 | 1.000 | 1.000 |
