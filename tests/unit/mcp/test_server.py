"""The MCP server exposes exactly the four read-only tools, takes identity only from the verified bearer token
(HTTP) or the fixed stdio identity, refuses unauthenticated HTTP calls, and reports tool failures as errors
without leaking internals. Driven in-process over memory streams with the SDK client."""

from __future__ import annotations

from starlette.testclient import TestClient

from medops.domain.common import Dept
from medops.mcp.contracts import (
    MCP_TOOLS,
)
from medops.mcp.server import build_server
from tests.mcp_client import call
from tests.support.harness_data import user
from tests.support.identity import ISSUER, TestIssuer
from tests.support.mcp_runtime import CHUNK, ISSUER_OBJ, FakeRuntime


def test_exactly_the_four_read_only_tools_and_no_identity_in_their_inputs():
    server = build_server(FakeRuntime(with_auth=False, dev_identity=user(Dept.MA)))
    tools, _ = call(server, "list_active_versions", {"input": {"family_id": "33333333-3333-4333-8333-333333333333"}})
    assert sorted(t.name for t in tools.tools) == sorted(t.name for t in MCP_TOOLS)
    for t in tools.tools:
        assert (
            t.annotations is not None
            and t.annotations.read_only_hint is True
            and t.annotations.destructive_hint is False
        )
        assert not ({"dept", "scopes", "user_id", "sub"} & set(str(t.input_schema)))


def test_tools_run_under_the_call_identity_and_errors_do_not_leak():
    rt = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(rt)
    _, ok = call(server, "get_chunk", {"input": {"chunk_id": CHUNK.citation.chunk_id}})
    assert (
        not ok.is_error
        and ok.structured_content["citation"]["chunk_id"] == CHUNK.citation.chunk_id
        and rt.served == ["MA"]
    )
    _, missing = call(server, "get_chunk", {"input": {"chunk_id": "44444444-4444-4444-8444-444444444444"}})
    assert missing.is_error and "not_found" in missing.content[0].text and "Traceback" not in missing.content[0].text
    _, verify = call(server, "verify_citation", {"input": {"citation": CHUNK.citation.model_dump(mode="json")}})
    assert verify.structured_content == {"exists": True, "status": "active", "fields_match": True}


def test_http_transport_requires_a_valid_bearer_token():
    server = build_server(FakeRuntime(with_auth=True), issuer_url=ISSUER, resource_url="http://testserver/mcp")
    app = server.streamable_http_app()
    with TestClient(app) as client:
        anonymous = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert anonymous.status_code == 401
        forged = TestIssuer(kid="k1").token()
        bad = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + forged},
        )
        assert bad.status_code == 401
        good = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + ISSUER_OBJ.token()},
        )
        assert good.status_code != 401  # authenticated; the protocol may still reject the bare request (no session)


def test_no_identity_at_all_is_refused():
    server = build_server(FakeRuntime(with_auth=False, dev_identity=None))
    _, result = call(server, "list_active_versions", {"input": {"family_id": "33333333-3333-4333-8333-333333333333"}})
    assert result.is_error and "unauthenticated" in result.content[0].text


def test_complete_input_outside_trace_summary_and_tool_output_are_separate_restricted_material():
    rt = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    query = "synthetic query 中文 " * 80
    _, result = call(build_server(rt), "search_documents", {"input": {"query": query, "k": 3}})
    assert not result.is_error
    material = rt.payloads[-1]
    assert material["input"]["input"]["query"] == query and len(rt.audited[-1].query) < len(query)
    assert material["input"]["tool"] == "search_documents"
    assert material["input"]["user"] == rt.dev_identity.model_dump(mode="json")
    assert material["model_output"]["tool_result"] == result.structured_content
    assert material["evidence_snapshot"]["observed"] == {"synthetic": True}


def test_unexpected_tool_failure_keeps_known_fees_and_never_returns_exception_message():
    rt = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    _, result = call(build_server(rt), "search_documents", {"input": {"query": "uncaught-after-model"}})
    assert result.is_error and "internal_error" in result.content[0].text
    assert "synthetic-private-error-message" not in result.content[0].text
    assert rt.audited[-1].model_calls == 1 and rt.audited[-1].cost_usd == 0.002
    assert rt.payloads[-1]["model_output"]["error_type"] == "ValueError"
    assert rt.payloads[-1]["model_output"]["tool_result"] is None


def test_tool_calls_are_traced_with_the_tool_name_and_department():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from medops.core import telemetry

    exp = InMemorySpanExporter()
    telemetry.install_exporter(exp, batch=False)
    try:
        server = build_server(FakeRuntime(with_auth=False, dev_identity=user(Dept.MA)))
        call(server, "verify_citation", {"input": {"citation": CHUNK.citation.model_dump(mode="json")}})
        tools = [s for s in exp.get_finished_spans() if s.name == "mcp.tool"]
        assert tools and tools[-1].attributes["tool"] == "verify_citation" and tools[-1].attributes["dept"] == "MA"
        call(server, "get_chunk", {"input": {"chunk_id": "44444444-4444-4444-8444-444444444444"}})
        failed = [s for s in exp.get_finished_spans() if s.name == "mcp.tool"][-1]
        assert failed.attributes["error_code"] == "not_found"
    finally:
        telemetry.set_tracer_provider(None)


def test_every_tool_call_writes_an_mcp_trace_and_audit_failure_fails_closed():
    """M3-07 follow-up (record 73): one trace per call with the tool, the principal pseudonym and the chunk ids
    handed out; an error path is audited with its code; when the audit store is down no data leaves."""
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    chunk_id = CHUNK.citation.chunk_id
    _, ok = call(server, "get_chunk", {"input": {"chunk_id": chunk_id}})
    assert not ok.is_error
    trace = runtime.audited[-1]
    assert trace.kind == "mcp" and trace.query.startswith("get_chunk ") and trace.outcome == "answered"
    assert chunk_id in trace.evidence_chunk_ids and trace.model_calls == 0 and trace.cost_usd == 0.0
    assert len(trace.principal) == 64  # a dev identity is hashed into the pseudonym shape
    _, missing = call(server, "get_chunk", {"input": {"chunk_id": "00000000-0000-4000-8000-00000000dead"}})
    assert missing.is_error and runtime.audited[-1].outcome == "escalated"
    assert runtime.audited[-1].reason_codes == ("not_found",)
    runtime.fail_audit = True
    _, closed = call(server, "get_chunk", {"input": {"chunk_id": chunk_id}})
    assert closed.is_error and "audit unavailable" in closed.content[0].text and closed.structured_content is None


def test_search_audit_includes_translation_usage_and_routed_versions():
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    _, result = call(server, "search_documents", {"input": {"query": "剂量", "k": 8}})
    assert not result.is_error
    trace = runtime.audited[-1]
    assert (trace.model_calls, trace.tokens, trace.cost_usd) == (1, 17, 0.002)
    assert trace.versions["retrieval_version"] == "retrieval-canary"
    assert trace.versions["policy_version"] == "policy-canary"


def test_failed_search_audit_keeps_model_usage_before_the_failure():
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    _, result = call(server, "search_documents", {"input": {"query": "fail-after-model", "k": 8}})
    assert result.is_error
    trace = runtime.audited[-1]
    assert trace.outcome == "escalated" and (trace.model_calls, trace.tokens, trace.cost_usd) == (1, 17, 0.002)
    assert trace.versions["policy_version"] == "policy-canary"
