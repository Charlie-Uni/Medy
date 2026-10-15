"""Fact-plane port of one action-scoped, caller-owned Agent transaction."""

from __future__ import annotations

from typing import Literal, Protocol

from medops.application.agent_tool_results import AgentFact
from medops.domain.agent_execution import AgentContext
from medops.domain.evidence import Evidence


class AgentToolFault(ValueError):
    def __init__(self, kind: Literal["denied_or_unavailable", "dependency_error", "unsupported", "ambiguous"]):
        self.kind = kind
        super().__init__(kind)


class AgentFacts(Protocol):
    def check(self, context: AgentContext) -> None: ...
    def sources(self, context: AgentContext) -> None: ...
    def lookup(self, context: AgentContext, chunk_ids: tuple[str, ...]) -> tuple[AgentFact, ...]: ...
    def read(
        self, context: AgentContext, evidence: Evidence, region: Literal["current", "previous", "next"]
    ) -> AgentFact | None: ...
    def final_check(self, context: AgentContext, facts: tuple[AgentFact, ...], *, check_sources: bool = True) -> None:
        """Hold fact/identity fence until the caller persists audit/result and commits."""
        ...
