"""Business trace linkage, routed versions, privacy and thread-context regression checks."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from medops.core import telemetry
from medops.core.tracing import bind_trace_id, current_trace_id
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api.test_ask_route import ANSWER, QUERY, FakeRuntime, auth, client
from tests.unit.harness._fixtures import evidence, user, versions
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval, make_deps


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    provider = telemetry.install_exporter(exporter, batch=False)
    yield exporter
    provider.shutdown()
    telemetry.set_tracer_provider(None)


def test_api_and_model_spans_share_the_business_id_and_cost(spans):
    runtime = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    body = client(runtime).post("/v1/ask", json={"query": QUERY}, headers=auth()).json()
    actual = spans.get_finished_spans()
    assert {s.context.trace_id for s in actual} == {int(body["trace_id"], 16)}
    assert {s.attributes["medops.trace_id"] for s in actual} == {body["trace_id"]}
    llm = next(s for s in actual if s.name == "llm.call")
    assert llm.attributes["langfuse.observation.type"] == "generation"
    assert llm.attributes["gen_ai.usage.cost"] == llm.attributes["cost_usd"]
    assert all(s.attributes["langfuse.trace.metadata.policy_version"] == "policy-test-1" for s in actual)


def test_versions_follow_actual_canary_routing_including_http_parent(spans):
    from medops.api.ports import RequestPolicies
    from medops.application.policy_loader import ReleasedPolicySet

    class Routed(FakeRuntime):
        def route_policies(self, conn, user):
            return RequestPolicies(
                ReleasedPolicySet.empty(),
                self.versions.model_copy(update={"policy_version": "canary-policy", "retrieval_version": "canary-r"}),
            )

    rt = Routed(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    assert client(rt).post("/v1/ask", json={"query": QUERY}, headers=auth()).status_code == 200
    for s in spans.get_finished_spans():
        assert s.attributes["medops.policy_version"] == "canary-policy"
        assert s.attributes["langfuse.trace.metadata.retrieval_version"] == "canary-r"


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt])
def test_exception_message_and_stack_never_leave_span(spans, error):
    secret = "SECRET_MEDICAL_QUERY patient example and source body"
    with pytest.raises(error), telemetry.span("outer"), telemetry.span("inner"):
        raise error(secret)
    for s in spans.get_finished_spans():
        assert s.status.status_code is StatusCode.ERROR
        assert s.status.description == error.__name__
        assert s.events == ()
        assert secret not in s.to_json()


def test_replay_is_separate_trace_with_parent_link_and_scoped_versions(spans):
    first, replay = "a" * 32, "b" * 32
    with telemetry.run_metadata(first, {"policy_version": "original"}, kind="ask"), telemetry.span("http.request"):
        with telemetry.run_metadata(replay, {"policy_version": "replay"}, kind="ask"):
            with telemetry.span("harness.run"), telemetry.span("llm.call"):
                assert current_trace_id() == replay
        with telemetry.span("after"):
            assert current_trace_id() == first
    all_spans = {s.name: s for s in spans.get_finished_spans()}
    http, run, llm = (all_spans[n] for n in ("http.request", "harness.run", "llm.call"))
    assert run.parent is None and len(run.links) == 1 and run.links[0].context == http.context
    assert run.context.trace_id == llm.context.trace_id == int(replay, 16)
    assert llm.parent == run.context
    assert all_spans["after"].attributes["medops.policy_version"] == "original"
    assert http.attributes["medops.policy_version"] == "original"
    assert current_trace_id() is None


def test_offline_harness_has_one_root_and_one_trace(spans):
    from medops.harness.runtime import initial_state, run_ask

    state = initial_state(user=user(), query=QUERY, versions=versions())
    run_ask(state, make_deps(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]})))
    actual = spans.get_finished_spans()
    assert [s.name for s in actual if s.parent is None] == ["harness.run"]
    assert {s.context.trace_id for s in actual} == {int(state.trace_id, 16)}
    assert current_trace_id() is None


def test_parallel_skills_keep_parent_and_distinct_span_ids(spans):
    from medops.skills.registry import SkillRequest
    from tests.unit.skills.test_registry import context, entry, registry

    reg = registry(entry(parallel_safe=True))
    ctx = context(reg)
    with bind_trace_id(ctx.trace_id), telemetry.span("worker.task"):
        results = reg.execute_many(
            [SkillRequest("echo_skill", "1.0.0", {"text": str(i)}) for i in range(3)], context=ctx
        )
    assert len(results) == 3
    actual = spans.get_finished_spans()
    parent = next(s for s in actual if s.name == "worker.task")
    skill_spans = [s for s in actual if s.name == "skill.run"]
    assert len(skill_spans) == 3
    assert all(s.parent == parent.context for s in skill_spans)
    assert len({s.context.span_id for s in actual}) == len(actual)
    assert {s.context.trace_id for s in actual} == {int(ctx.trace_id, 16)}


def test_unknown_url_and_client_trace_header_do_not_enter_telemetry(spans):
    secret = "PRIVATE_UNKNOWN_PATH"
    rt = FakeRuntime(FakeRetrieval(), FakeModelGateway())
    response = client(rt).get(f"/{secret}?sensitive=query", headers={"X-Trace-Id": "c" * 32})
    assert response.status_code == 404
    http = spans.get_finished_spans()[0]
    assert http.attributes["http.route"] == "/<unmatched>"
    assert http.context.trace_id == int(response.headers["X-Trace-Id"], 16) != int("c" * 32, 16)
    assert secret not in http.to_json() and "sensitive=query" not in http.to_json()


def test_caught_node_failure_is_marked_error(spans):
    from medops.harness.contracts import NodeFailure, NodeSpec, run_node

    def fail():
        raise ValueError("private error text")

    with pytest.raises(NodeFailure):
        run_node(NodeSpec(name="test", timeout_s=1), "key", fail)
    s = spans.get_finished_spans()[0]
    assert s.status.status_code is StatusCode.ERROR
    assert s.attributes["langfuse.observation.level"] == "ERROR"
    assert "private error text" not in s.to_json()


def test_mcp_audit_and_telemetry_use_same_id(spans):
    from medops.mcp.server import build_server
    from tests.unit.mcp.test_server import FakeRuntime as McpRuntime
    from tests.unit.mcp.test_server import call

    rt = McpRuntime(with_auth=False, dev_identity=user())
    server = build_server(rt)
    _, result = call(server, "search_documents", {"input": {"query": "query", "k": 2}})
    assert not result.is_error
    s = next(s for s in spans.get_finished_spans() if s.name == "mcp.tool")
    assert s.attributes["medops.trace_id"] == rt.audited[0].trace_id
    assert s.context.trace_id == int(rt.audited[0].trace_id, 16)


def test_http_exporter_sends_sanitized_protobuf_and_auth_to_local_receiver():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    captured = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append((self.path, dict(self.headers), self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = None
    try:
        provider = telemetry.configure_telemetry(
            endpoint=f"http://127.0.0.1:{server.server_port}/api/public/otel",
            headers="Authorization=Basic TEST_ONLY,x-langfuse-ingestion-version=4",
        )
        with bind_trace_id("d" * 32), telemetry.span("llm.call", **{"gen_ai.usage.cost": 0.01}):
            pass
        telemetry.flush()
        assert len(captured) == 1
        path, headers, payload = captured[0]
        assert path == "/api/public/otel/v1/traces"
        assert headers["Authorization"] == "Basic TEST_ONLY"
        assert headers["x-langfuse-ingestion-version"] == "4"
        assert headers["Content-Type"] == "application/x-protobuf"
        request = ExportTraceServiceRequest.FromString(payload)
        sent = request.resource_spans[0].scope_spans[0].spans[0]
        assert sent.trace_id.hex() == "d" * 32
        assert sent.name == "llm.call" and len(sent.events) == 0
    finally:
        if provider is not None:
            provider.shutdown()
        telemetry.set_tracer_provider(None)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
