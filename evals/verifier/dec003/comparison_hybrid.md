# DEC-003 simulated hybrid (rules first, model where rules are undetermined)

| arm | shared pairs | model calls needed | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules→claude-haiku-4-5 | 299 | 179 (60%) | 0.913 | 0.070 | 0.877 | 1.000 | 0.754 | 1.000 | 0.972 |
| rules→claude-sonnet-5 | 300 | 180 (60%) | 0.927 | 0.066 | 0.845 | 1.000 | 0.841 | 1.000 | 0.972 |
| rules→gpt-6-luna | 297 | 179 (60%) | 0.923 | 0.071 | 0.825 | 1.000 | 0.841 | 1.000 | 0.972 |
| rules→gpt-5.4-mini | 300 | 180 (60%) | 0.890 | 0.105 | 0.776 | 1.000 | 0.754 | 0.988 | 0.972 |
| rules→gpt-6-sol | 300 | 180 (60%) | 0.930 | 0.053 | 0.914 | 1.000 | 0.797 | 1.000 | 0.972 |
