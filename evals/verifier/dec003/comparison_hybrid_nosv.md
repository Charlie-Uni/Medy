# DEC-003 simulated hybrid (rules first, model where rules are undetermined)

| arm | shared pairs | model calls needed | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rules→claude-haiku-4-5 | 299 | 206 (69%) | 0.923 | 0.075 | 0.860 | 1.000 | 0.812 | 1.000 | 0.972 |
| rules→claude-sonnet-5 | 300 | 207 (69%) | 0.933 | 0.070 | 0.828 | 1.000 | 0.884 | 1.000 | 0.972 |
| rules→gpt-6-luna | 297 | 205 (69%) | 0.936 | 0.071 | 0.825 | 1.000 | 0.899 | 1.000 | 0.972 |
| rules→gpt-5.4-mini | 300 | 207 (69%) | 0.900 | 0.105 | 0.776 | 1.000 | 0.797 | 0.988 | 0.972 |
| rules→gpt-6-sol | 300 | 207 (69%) | 0.940 | 0.053 | 0.914 | 1.000 | 0.841 | 1.000 | 0.972 |
