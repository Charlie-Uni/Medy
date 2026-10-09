"""State transitions shared by node execution and answer verification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from medops.domain.answer import Escalation
from medops.domain.common import ReasonCode
from medops.domain.state import AgentState


def escalate(state: AgentState, codes: Sequence[ReasonCode], detail: str, **extra: Any) -> AgentState:
    escalation = Escalation(
        reason_codes=tuple(codes),
        query=state.query,
        evidence_chunk_ids=tuple(e.citation.chunk_id for e in state.evidence),
        verify_result=extra.get("verify_result", state.verify_result),
        safety_result=extra.get("safety_result", state.safety_result),
        policy_version=state.versions.policy_version,
        detail=detail[:500],
    )
    return state.advance(escalation=escalation, **extra)
