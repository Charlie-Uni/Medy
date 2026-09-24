# Run 1 (14:28–14:33, before the two fixes): 18/19 steps

```
OK   api.ready {}
OK   ask.answered {'status': '200', 'outcome': 'answered', 'claims': '1', 'trace': 'd4c493c144c8423c89297dd3e9d00cc8'}
OK   ask.high_risk_refused {'codes': "['high_risk_medical']"}
OK   ask.unauthenticated_401 {}
OK   ask.unknown_subject_403 {}
OK   metrics {'lines': '34'}
OK   feedback.idempotent {'receipt': '805da97a-b439-478f-9fef-fe99023a4e85'}
OK   task.created_idempotent {'task_id': 'c80a8fca-1b8c-494d-8ce8-e3b7dc4dc552'}
OK   replay {'status': '201', 'changed': '[]', 'versions_match': 'True', 'replay_outcome': 'answered'}
FAIL api.graceful_stop {'exit_code': '-15'}
OK   worker.once {'exit_codes': '[0]', 'tail': 's]\nLoading weights: 100%|██████████| 391/391 [00:00<00:00, 30797.03it/s]\n\nLoadin'}
OK   task.completed {'status': 'completed', 'attempts': '1', 'skill_status': 'completed', 'excerpts': '2'}
OK   audit.rows {'traces': '4', 'trace_spans': '13', 'escalations': '1', 'feedback': '1', 'tasks': '1', 'task_attempts': '1', 'replays': '1', 'operation_executions': '17', 'operation_attempts': '17', 
OK   mcp.tools {}
OK   mcp.get_chunk {'status': 'active'}
OK   mcp.list_active_versions {'version': 'pdf-meta 2016-11-22（未见版本行）'}
OK   mcp.verify_citation {}
OK   mcp.search_documents {'hits': '5', 'gold_in_hits': 'True'}
SOME STEPS FAILED
```

- api.graceful_stop: exit status -15 after a clean shutdown (uvicorn re-raises the captured SIGTERM by design; log shows Application shutdown complete., no traceback) -> criterion corrected, DEPLOY.md notes exit 143.
- MCP stdio: 8 JSON-RPC validation warnings on the client because structured logs were written to stdout -> medops.mcp.serve now logs to stderr for stdio; run 2 shows 0 warnings.
