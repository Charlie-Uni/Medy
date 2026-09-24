# Real end-to-end on medops_v2 (2026-09-24)

| step | ok | details |
| --- | --- | --- |
| api.ready | ✓ |  |
| ask.answered | ✓ | status=200, outcome=answered, claims=1, trace=1be42cb117ef4b6b855d354615e392ac |
| ask.high_risk_refused | ✓ | codes=['high_risk_medical'] |
| ask.unauthenticated_401 | ✓ |  |
| ask.unknown_subject_403 | ✓ |  |
| metrics | ✓ | lines=41 |
| feedback.idempotent | ✓ | receipt=f5decf23-8804-40d5-9674-ff83aabea18b |
| task.created_idempotent | ✓ | task_id=608f3211-1c4a-4445-a7b3-b8cffe56afc2 |
| replay | ✓ | status=201, changed=[], versions_match=True, replay_outcome=answered |
| api.graceful_stop | ✓ | exit_code=-15, clean_shutdown=True |
| worker.once | ✓ | exit_codes=[0], tail=s]
Loading weights: 100%|██████████| 391/391 [00:00<00:00, 3 |
| task.completed | ✓ | status=completed, attempts=1, skill_status=completed, excerpts=2 |
| audit.rows | ✓ | traces=8, trace_spans=26, escalations=2, feedback=2, tasks=2, task_attempts=2, replays=2, operation_executions=34, operation_attempts=34, kinds={'task': 2, 'ask': 4, 'replay': 2} |
| mcp.tools | ✓ |  |
| mcp.get_chunk | ✓ | status=active |
| mcp.list_active_versions | ✓ | version=pdf-meta 2016-11-22（未见版本行） |
| mcp.verify_citation | ✓ |  |
| mcp.search_documents | ✓ | hits=5, gold_in_hits=True |
