# Skill smoke `2026-09-23-skill-smoke-v1`

- 12 cases · cost $0.06 · answer gpt-6-sol · judge gpt-6-sol · skills citation_verification@1.0.0, label_query@1.0.0

| case | expect | status | reason / error | verdicts | calls | cost | latency |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| label_query/positive | completed | insufficient_evidence | insufficient_evidence | 0 excerpts | 2 | $0.0115 | 9.33s |
| label_query/positive-2 | completed | completed | — | 2 excerpts | 2 | $0.0110 | 5.83s |
| label_query/positive-3 | completed | completed | — | 3 excerpts | 3 | $0.0194 | 10.04s |
| label_query/non-label-topic | insufficient_evidence | insufficient_evidence | insufficient_evidence | 0 excerpts | 2 | $0.0063 | 6.3s |
| label_query/scope-denied | forbidden | error | forbidden | 0 excerpts | 0 | $0.0000 | 0.0s |
| label_query/schema-violation | schema_violation | error | schema_violation | 0 excerpts | 0 | $0.0000 | 0.0s |
| citation_verification/supported-1 | completed | completed | — | supported | 1 | $0.0015 | 1.69s |
| citation_verification/supported-2 | completed | completed | — | supported, supported | 2 | $0.0063 | 3.66s |
| citation_verification/supported-3 | completed | completed | — | supported, supported | 2 | $0.0025 | 3.2s |
| citation_verification/altered-number | completed | completed | — | contradicted | 1 | $0.0015 | 1.42s |
| citation_verification/unknown-chunk | completed | completed | — | not_supported (unknown 2) | 0 | $0.0000 | 0.02s |
| citation_verification/cross-dept-chunk | completed | completed | — | not_supported (unknown 1) | 0 | $0.0000 | 0.01s |
