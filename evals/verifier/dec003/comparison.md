# DEC-003 arm comparison on 296 shared pairs

| arm | accuracy | unsafe accept | contradicted/negation | contradicted/numeric | not_supported/other_doc | not_supported/same_doc | supported | cost (USD, API-equivalent) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules:verifier-v2+support-rules-v2+polarity_only | 0.892 | 0.040 | 0.857 | 0.706 | 0.976 | 0.884 | 0.875 | 0.00 |
| cli:claude-haiku-4-5 | 0.946 | 0.054 | 0.875 | 1.000 | 1.000 | 0.870 | 1.000 | 0.57 |
| cli:claude-sonnet-5 | 0.956 | 0.049 | 0.839 | 1.000 | 1.000 | 0.942 | 1.000 | 1.12 |
| openai-llm:gpt-6-luna | 0.959 | 0.049 | 0.839 | 1.000 | 1.000 | 0.957 | 1.000 | 0.02 |
| openai-llm:gpt-5.4-mini | 0.895 | 0.112 | 0.679 | 1.000 | 0.988 | 0.826 | 1.000 | 0.17 |
| openai-llm:gpt-6-sol | 0.970 | 0.022 | 0.964 | 1.000 | 1.000 | 0.899 | 1.000 | 0.45 |
| openai-hybrid:gpt-6-luna | 0.936 | 0.045 | 0.857 | 0.941 | 1.000 | 0.899 | 0.958 | 0.02 |
| openai-hybrid:gpt-5.4-mini | 0.899 | 0.080 | 0.804 | 1.000 | 0.988 | 0.783 | 0.958 | 0.12 |
| openai-hybrid:gpt-6-sol | 0.956 | 0.022 | 0.964 | 1.000 | 1.000 | 0.884 | 0.958 | 0.33 |

## By slice (accuracy; n in the first arm)

| slice | n | rules:verifier-v2+support-rules-v2+polarity_only | cli:claude-haiku-4-5 | cli:claude-sonnet-5 | openai-llm:gpt-6-luna | openai-llm:gpt-5.4-mini | openai-llm:gpt-6-sol | openai-hybrid:gpt-6-luna | openai-hybrid:gpt-5.4-mini | openai-hybrid:gpt-6-sol |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dose_unit | 32 | 0.781 | 0.906 | 0.969 | 0.906 | 0.906 | 0.906 | 0.844 | 0.875 | 0.875 |
| drug_name_zh | 52 | 0.827 | 0.981 | 0.962 | 0.962 | 0.904 | 0.981 | 0.923 | 0.885 | 0.942 |
| long_context | 13 | 0.923 | 0.846 | 1.000 | 0.846 | 0.846 | 0.846 | 0.846 | 0.846 | 0.846 |
| mixed_zh_en | 276 | 0.906 | 0.946 | 0.957 | 0.960 | 0.895 | 0.971 | 0.935 | 0.899 | 0.957 |
| negation | 151 | 0.907 | 0.921 | 0.940 | 0.940 | 0.868 | 0.980 | 0.907 | 0.874 | 0.947 |
| protocol_id | 70 | 0.886 | 0.971 | 0.971 | 0.957 | 0.871 | 0.971 | 0.943 | 0.857 | 0.957 |
| time_window | 83 | 0.867 | 0.976 | 0.964 | 0.988 | 0.916 | 0.976 | 0.976 | 0.940 | 0.976 |
| version_conflict | 28 | 0.893 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.964 | 1.000 | 1.000 |
