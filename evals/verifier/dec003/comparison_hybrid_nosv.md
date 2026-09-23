# DEC-003 simulated hybrid (rules first, model where rules are undetermined)

| arm | shared pairs | model calls needed | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules→claude-haiku-4-5 | 299 | 193 (65%) | 0.923 | 0.070 | 0.877 | 1.000 | 0.797 | 1.000 | 0.972 |
| rules→claude-sonnet-5 | 300 | 194 (65%) | 0.933 | 0.066 | 0.845 | 1.000 | 0.870 | 1.000 | 0.972 |
| rules→gpt-6-luna | 297 | 193 (65%) | 0.933 | 0.071 | 0.825 | 1.000 | 0.884 | 1.000 | 0.972 |
| rules→gpt-5.4-mini | 300 | 194 (65%) | 0.897 | 0.105 | 0.776 | 1.000 | 0.783 | 0.988 | 0.972 |
| rules→gpt-6-sol | 300 | 194 (65%) | 0.937 | 0.053 | 0.914 | 1.000 | 0.826 | 1.000 | 0.972 |
