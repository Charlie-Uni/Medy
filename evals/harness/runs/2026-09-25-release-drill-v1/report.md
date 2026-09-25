# Release / promote / rollback drill (2026-09-25, record 85)

policy e72a6a08-bb90-45c0-a204-d7e369849fd5, reload TTL 2 s, cost 0.0655 USD, all ok: True

| check | ok | details |
| --- | --- | --- |
| phase.0-before | ✓ | versions=['policy-m3-api-1'], mismatches=[] |
| approve | ✓ | status=200 |
| release_10pct | ✓ | status=200, body={"policy_id":"e72a6a08-bb90-45c0-a204-d7e369849fd5","kind":"retrieval_params","n |
| phase.1-canary-10pct | ✓ | versions=['policy-m3-api-1', 'policy-m3-api-1+canary:e72a6a08'], mismatches=[] |
| promote_blocked_by_window | ✓ | status=409, code=observation_window_open |
| promote_100pct_with_override | ✓ | status=200, body={"policy_id":"e72a6a08-bb90-45c0-a204-d7e369849fd5","kind":"retrieval_params","n |
| phase.2-full | ✓ | versions=['policy-m3-api-1+rel:e72a6a08'], mismatches=[] |
| rollback | ✓ | status=200 |
| phase.3-after-rollback | ✓ | versions=['policy-m3-api-1'], mismatches=[] |
| release_log | ✓ | log=[('release', 10), ('promote', 100), ('rollback', None)] |
| pointer_cleared | ✓ |  |

| phase | effective within | versions seen |
| --- | ---: | --- |
| 0-before | — s | ['policy-m3-api-1'] |
| 1-canary-10pct | 3551.9 s | ['policy-m3-api-1', 'policy-m3-api-1+canary:e72a6a08'] |
| 2-full | 78.6 s | ['policy-m3-api-1+rel:e72a6a08'] |
| 3-after-rollback | 64.5 s | ['policy-m3-api-1'] |
