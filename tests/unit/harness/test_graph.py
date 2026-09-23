"""M2-01: the compiled graph has no path to `answer` that skips retrieve, verify or safety."""

from __future__ import annotations

import pytest

from medops.harness.graph import build_graph, graph_edges, simple_paths
from medops.harness.nodes import HarnessDeps
from medops.harness.retrieval_port import RetrievalOutcome, RetrievalRequest
from medops.infrastructure.llm.fake import FakeModelGateway


class _NoRetrieval:
    def retrieve(self, request: RetrievalRequest) -> RetrievalOutcome:  # pragma: no cover - structure test only
        return RetrievalOutcome(rewritten_queries=(request.query,), candidates=(), evidence=())


def deps():
    return HarnessDeps(retrieval=_NoRetrieval(), gateway=FakeModelGateway(), answer_model_id="gpt-6-sol")


def test_every_path_to_answer_passes_retrieve_verify_safety_in_order():
    edges = graph_edges(build_graph(deps()))
    paths = simple_paths(edges, "__start__", "answer")
    assert paths, "answer must be reachable"
    for path in paths:
        idx = {n: path.index(n) for n in ("intent", "retrieve", "verify", "safety", "answer") if n in path}
        assert set(idx) == {"intent", "retrieve", "verify", "safety", "answer"}, path
        assert idx["intent"] < idx["retrieve"] < idx["verify"] < idx["safety"] < idx["answer"], path


def test_answer_has_a_single_predecessor_and_every_stage_can_escalate():
    edges = graph_edges(build_graph(deps()))
    predecessors = {b: {a for a, t in edges if t == b} for _, b in edges}
    assert predecessors["answer"] == {"safety"}
    assert predecessors["__end__"] == {"answer", "escalate"}
    for stage in ("intent", "retrieve", "verify", "safety", "answer"):
        assert "escalate" in {t for a, t in edges if a == stage}, stage
    assert not [t for a, t in edges if a == "escalate" and t != "__end__"]


def test_external_tracing_configuration_aborts_graph_construction(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    with pytest.raises(RuntimeError, match="ADR-0010"):
        build_graph(deps())
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    build_graph(deps())
