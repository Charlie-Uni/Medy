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


def test_app_shutdown_flushes_spans_still_held_by_the_batch_processor():
    """uvicorn re-raises SIGTERM after a graceful stop, so atexit never runs; the lifespan flush is what gets the
    last spans out (record 77)."""
    from fastapi.testclient import TestClient

    from medops.api.app import create_app

    exp = InMemorySpanExporter()
    telemetry.install_exporter(exp, batch=True)  # BatchSpanProcessor: exports every 5 s or on flush
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    with TestClient(create_app(rt)) as c:
        assert c.post("/v1/ask", json={"query": QUERY}, headers=auth()).status_code == 200
        held = len(exp.get_finished_spans())
    flushed = [s.name for s in exp.get_finished_spans()]
    assert held == 0 and flushed.count("harness.node") == 5 and "http.request" in flushed


def test_model_call_spans_carry_genai_attributes_but_never_prompt_or_reply():
    """Record 123: trace viewers read the OpenTelemetry GenAI names; the content stays out (INV-OBS-03)."""
    exp = exporter()
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    client(rt).post("/v1/ask", json={"query": QUERY}, headers=auth())
    llm = next(s for s in exp.get_finished_spans() if s.name == "llm.call")
    attrs = dict(llm.attributes)
    assert attrs["gen_ai.operation.name"] == "chat" and attrs["gen_ai.request.model"] == attrs["model_id"]
    assert attrs["gen_ai.usage.input_tokens"] == attrs["input_tokens"] > 0
    assert attrs["gen_ai.usage.output_tokens"] == attrs["output_tokens"] > 0
    everything = " ".join(str(v) for s in exp.get_finished_spans() for v in s.attributes.values())
    assert LABEL not in everything and QUERY not in everything  # neither evidence nor the question
    assert not any(k.startswith(("gen_ai.prompt", "gen_ai.completion", "gen_ai.input", "gen_ai.output")) for k in attrs)


def test_otlp_headers_are_parsed_strictly_and_passed_to_the_exporter(monkeypatch):
    import pytest

    assert telemetry.parse_headers(None) == {} and telemetry.parse_headers("") == {}
    assert telemetry.parse_headers("Authorization=Basic cGs6c2s=, x-tenant = a ") == {
        "Authorization": "Basic cGs6c2s=",  # a base64 value keeps its own `=`
        "x-tenant": "a",
    }
    with pytest.raises(ValueError, match="Key=Value"):
        telemetry.parse_headers("Authorization")
    seen = {}

    class FakeExporter:
        def __init__(self, endpoint, headers=None):
            seen.update(endpoint=endpoint, headers=headers)

        def export(self, spans):  # pragma: no cover - not reached
            return None

        def shutdown(self):
            return None

        def force_flush(self, timeout_millis=30000):
            return True

    import opentelemetry.exporter.otlp.proto.http.trace_exporter as mod

    monkeypatch.setattr(mod, "OTLPSpanExporter", FakeExporter)
    telemetry.configure_telemetry(endpoint="http://127.0.0.1:3000/api/public/otel/", headers="Authorization=Basic x=")
    assert seen == {
        "endpoint": "http://127.0.0.1:3000/api/public/otel/v1/traces",
        "headers": {"Authorization": "Basic x="},
    }
    telemetry.configure_telemetry(endpoint="http://127.0.0.1:4318")
    assert seen == {"endpoint": "http://127.0.0.1:4318/v1/traces", "headers": None}
    telemetry.set_tracer_provider(None)
