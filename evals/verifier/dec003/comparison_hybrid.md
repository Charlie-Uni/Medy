# DEC-003 simulated hybrid (rules first, model where rules are undetermined)

| arm | shared pairs | model calls needed | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules→claude-haiku-4-5 | 299 | 193 (65%) | 0.913 | 0.075 | 0.860 | 1.000 | 0.768 | 1.000 | 0.972 |
| rules→claude-sonnet-5 | 300 | 194 (65%) | 0.927 | 0.070 | 0.828 | 1.000 | 0.855 | 1.000 | 0.972 |
| rules→gpt-6-luna | 297 | 192 (65%) | 0.926 | 0.071 | 0.825 | 1.000 | 0.855 | 1.000 | 0.972 |
| rules→gpt-5.4-mini | 300 | 194 (65%) | 0.893 | 0.105 | 0.776 | 1.000 | 0.768 | 0.988 | 0.972 |
| rules→gpt-6-sol | 300 | 194 (65%) | 0.933 | 0.053 | 0.914 | 1.000 | 0.812 | 1.000 | 0.972 |
