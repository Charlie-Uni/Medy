"""The fixed graph (M2-01). Structure, not behaviour: every edge is declared here and nowhere else, so a test
can enumerate the compiled graph and prove that no path reaches `answer` without `retrieve`, `verify` and
`safety`, and that `answer`'s only predecessor is `safety`.

Third-party tracing is refused: LangGraph's optional LangSmith upload would send prompts (evidence text)
to an external service outside the DEC-009 boundary, so a configured tracer aborts graph construction.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from medops.harness.dependencies import HarnessDeps
from medops.harness.nodes import NODE_ORDER, HarnessState, build_nodes

_TRACING_VARS = ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY")


def _refuse_external_tracing() -> None:
    enabled = [v for v in _TRACING_VARS if os.environ.get(v, "").strip() not in ("", "false", "0")]
    if enabled:
        raise RuntimeError(f"external LLM tracing is not allowed (ADR-0010 data boundary): unset {', '.join(enabled)}")


def _route(next_node: str) -> Callable[[HarnessState], str]:
    def router(hs: HarnessState) -> str:
        return "escalate" if hs["state"].escalation is not None else next_node

    return router


def build_graph(deps: HarnessDeps) -> Any:
    _refuse_external_tracing()
    graph: Any = StateGraph(HarnessState)  # node callables are plain functions of HarnessState
    nodes = build_nodes(deps)
    for name in NODE_ORDER:
        graph.add_node(name, nodes[name])
    graph.add_edge(START, "intent")
    graph.add_conditional_edges("intent", _route("retrieve"), {"retrieve": "retrieve", "escalate": "escalate"})
    graph.add_conditional_edges("retrieve", _route("verify"), {"verify": "verify", "escalate": "escalate"})
    graph.add_conditional_edges("verify", _route("safety"), {"safety": "safety", "escalate": "escalate"})
    graph.add_conditional_edges("safety", _route("answer"), {"answer": "answer", "escalate": "escalate"})
    graph.add_conditional_edges("answer", _route("end"), {"end": END, "escalate": "escalate"})
    graph.add_edge("escalate", END)
    return graph.compile()


def graph_edges(compiled: Any) -> list[tuple[str, str]]:
    return [(edge.source, edge.target) for edge in compiled.get_graph().edges]


def simple_paths(edges: list[tuple[str, str]], source: str, target: str) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
    paths: list[list[str]] = []

    def walk(node: str, path: list[str]) -> None:
        if node == target:
            paths.append(path)
            return
        for nxt in adjacency.get(node, []):
            if nxt not in path:
                walk(nxt, [*path, nxt])

    walk(source, [source])
    return paths
