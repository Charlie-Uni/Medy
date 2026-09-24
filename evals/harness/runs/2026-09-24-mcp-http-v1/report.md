# Read-only MCP over Streamable HTTP with bearer auth (2026-09-24)

| step | ok | details |
| --- | --- | --- |
| server.up | ✓ | first_status=401 |
| tools | ✓ | tools=['get_chunk', 'list_active_versions', 'search_documents', 'verify_cita |
| get_chunk | ✓ | status=active |
| list_active_versions | ✓ |  |
| verify_citation | ✓ |  |
| search_documents | ✓ | hits=5, gold_in_hits=True |
| cross_dept_chunk_not_found | ✓ | text=Error executing tool get_chunk: not_found: chunk not found |
| refusal.no_token | ✓ | status=401, www_authenticate=Bearer error="invalid_token", error_description="Authenticat, sdk_session_refused=True |
| refusal.wrong_audience | ✓ | status=401, www_authenticate=Bearer error="invalid_token", error_description="Authenticat, sdk_session_refused=True |
| refusal.unknown_subject | ✓ | status=401, www_authenticate=Bearer error="invalid_token", error_description="Authenticat, sdk_session_refused=True |
| raw_http_no_token_401 | ✓ | status=401, www_authenticate=Bearer error="invalid_token", error_description="Authentication requir |
| server.graceful_stop | ✓ | exit_code=-15 |
