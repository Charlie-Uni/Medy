# DEC-003 division-of-labour policies (offline, recorded model verdicts)

| model | policy | pairs | model calls | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-haiku-4-5 | model_only | 299 | 299 (100%) | 0.946 | 0.053 | 0.877 | 1.000 | 0.870 | 1.000 | 1.000 |
| claude-haiku-4-5 | rules_decisive | 299 | 178 (60%) | 0.913 | 0.066 | 0.877 | 1.000 | 0.754 | 1.000 | 0.972 |
| claude-haiku-4-5 | polarity+contain | 299 | 215 (72%) | 0.920 | 0.044 | 0.912 | 1.000 | 0.783 | 0.976 | 0.972 |
| claude-haiku-4-5 | polarity_only | 299 | 231 (77%) | 0.936 | 0.044 | 0.912 | 1.000 | 0.826 | 1.000 | 0.972 |
| claude-sonnet-5 | model_only | 300 | 300 (100%) | 0.957 | 0.048 | 0.845 | 1.000 | 0.942 | 1.000 | 1.000 |
| claude-sonnet-5 | rules_decisive | 300 | 179 (60%) | 0.927 | 0.061 | 0.845 | 1.000 | 0.841 | 1.000 | 0.972 |
| claude-sonnet-5 | polarity+contain | 300 | 216 (72%) | 0.933 | 0.039 | 0.879 | 1.000 | 0.870 | 0.976 | 0.972 |
| claude-sonnet-5 | polarity_only | 300 | 232 (77%) | 0.947 | 0.039 | 0.879 | 1.000 | 0.899 | 1.000 | 0.972 |
