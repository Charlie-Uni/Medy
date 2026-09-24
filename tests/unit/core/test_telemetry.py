"""OTel spans (M3-09): one ask yields http.request -> harness.node x5 -> llm.call with the MedOps trace id and
versions as attributes; a failing node span is ERROR with its error code; no attribute carries evidence text;
without an endpoint the tracer is a no-op."""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from medops.core import telemetry
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelUnavailable
from tests.unit.api.test_ask_route import ANSWER, QUERY, FakeRuntime, auth, client
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval


def exporter() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    telemetry.install_exporter(exp, batch=False)
    return exp


def teardown_module() -> None:
    telemetry.set_tracer_provider(None)


def test_ask_produces_the_span_tree_with_trace_id_and_versions():
    exp = exporter()
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    body = client(rt).post("/v1/ask", json={"query": QUERY}, headers=auth()).json()
    spans = exp.get_finished_spans()
    names = [s.name for s in spans]
    assert names.count("harness.node") == 5 and names.count("llm.call") == 1 and names.count("http.request") == 1
    http = next(s for s in spans if s.name == "http.request")
    assert http.attributes["http.status_code"] == 200 and http.attributes["medops.policy_version"] == "policy-test-1"
    nodes = [s for s in spans if s.name == "harness.node"]
    assert [s.attributes["node"] for s in nodes] == ["intent", "retrieve", "verify", "safety", "answer"]
    assert all(s.attributes["medops.trace_id"] == body["trace_id"] and s.attributes["outcome"] == "ok" for s in nodes)
    llm = next(s for s in spans if s.name == "llm.call")
    assert llm.attributes["purpose"] == "answer" and llm.attributes["output_tokens"] > 0 and llm.parent is not None
    blob = " ".join(str(v) for s in spans for v in s.attributes.values())
    assert LABEL not in blob and "claims" not in blob  # no evidence or model text in attributes


def test_failed_node_span_is_error_with_the_code_and_no_endpoint_means_no_spans():
    exp = exporter()
    rt = FakeRuntime(
        FakeRetrieval(evidence("c1", LABEL)),
        FakeModelGateway({"answer": [ModelUnavailable("down", retryable=True)] * 3}),
    )
    client(rt).post("/v1/ask", json={"query": QUERY}, headers=auth())
    answers = [s for s in exp.get_finished_spans() if s.name == "harness.node" and s.attributes["node"] == "answer"]
    assert [s.attributes["outcome"] for s in answers] == ["retry", "retry", "failed"]
    assert all(s.attributes["error_code"] == "dependency_unavailable" for s in answers)
    assert telemetry.configure_telemetry(endpoint=None) is None
    exp2 = InMemorySpanExporter()  # provider cleared: nothing is recorded
    client(rt).post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert exp2.get_finished_spans() == ()
    provider = telemetry.configure_telemetry(endpoint="http://collector:4318", service_name="medops-test")
    assert provider is not None
    telemetry.set_tracer_provider(None)
