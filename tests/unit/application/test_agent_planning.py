"""Planner projection keeps exact context and explicit omissions, never private gold."""

import json

import pytest

from medops.application.agent_contracts import admit_action
from medops.application.agent_planning import PlannerConfig, PlanningBoard
from medops.application.agent_tool_results import AgentToolOutcome, EvidenceView, ReadPayload, SearchPayload
from medops.core.canonical import canonical_hash
from medops.domain.agent_execution import EvidenceHandle
from tests.support.harness_data import evidence
from tests.support.pv_agent import DIGEST, NOW, handle, proposal, run, uid, wire


def view_and_outcome(current, number, text, *, take=None):
    original = handle(current, number)
    actual = evidence(f"PUBLIC-{number}", text, doc_id="PUBLIC-doc", version="PUBLIC v1")
    original = EvidenceHandle.model_validate({**original.model_dump(), "evidence": actual})
    excerpt = text if take is None else text[:take]
    view = EvidenceView(
        handle=original.handle,
        citation=actual.citation,
        text=excerpt,
        char_end=len(excerpt),
        truncated=len(excerpt) < len(text),
        evidence_text_sha256=actual.evidence_text_hash,
        source_sha256=DIGEST,
    )
    action = admit_action(wire(proposal()), run=current, action_id=uid(900), evidence_registry=(), now=NOW)
    outcome = AgentToolOutcome(
        action_id=action.action_id, binding=action.binding, kind="ok", payload=SearchPayload(matches=(view,))
    )
    return action, outcome, view


def state(board, current=None):
    current = current or run()
    request = board.request(current, PlannerConfig(model_id="gpt-6-sol", max_output_tokens=512, timeout_s=20))
    return request, json.loads(request.messages[1].content)


def test_projection_uses_exact_original_narrative_conditions_and_no_private_identity():
    current = run()
    request, data = state(PlanningBoard(), current)
    assert data["narrative"] == current.context.narrative
    assert data["requirements"] == [r.model_dump(mode="json") for r in current.context.requirements]
    assert data["query_context"] == current.context.query_context.model_dump(mode="json")
    assert "principal" not in data and "case_id" not in data and "audit" not in data
    assert "expected" not in data and request.json_schema is None
    assert canonical_hash(data) == canonical_hash(json.loads(request.messages[1].content))


def test_long_original_read_retains_negation_numbers_and_conditions_without_silent_clipping():
    current, board = run(), PlanningBoard()
    text = "PUBLIC " * 500 + "DO NOT infer causality; only if 2026-10-01 and dose 100 mg."
    action, outcome, view = view_and_outcome(current, 10, text)
    outcome = outcome.model_copy(update={"payload": ReadPayload(evidence=view)})
    board.observe(action, outcome)
    _, data = state(board, current)
    assert data["evidence"][0]["text"] == text and data["evidence"][0]["truncated"] is False


def test_previous_long_read_is_not_replaced_by_short_search_excerpt():
    current, board = run(), PlanningBoard()
    text = "PUBLIC first sentence. Condition: never infer causality at 100 mg."
    action, full, _ = view_and_outcome(current, 10, text)
    _, short, _ = view_and_outcome(current, 10, text, take=22)
    board.observe(action, full)
    board.observe(action, short)
    assert state(board, current)[1]["evidence"][0]["text"] == text


def test_only_eight_recent_bodies_but_all_old_handle_metadata_remain_explicit():
    current, board = run(), PlanningBoard()
    for number in range(10, 20):
        action, outcome, _ = view_and_outcome(current, number, f"PUBLIC rule {number}.")
        board.observe(action, outcome)
    data = state(board, current)[1]
    assert len(data["evidence"]) == 10
    assert sum("text" in row for row in data["evidence"]) == 8
    assert data["evidence"][0]["text_omitted_from_planning"] is True
    assert "handle" in data["evidence"][0] and "citation" in data["evidence"][0]


def test_unsupported_payload_does_not_become_knowledge_in_later_planning():
    current, board = run(), PlanningBoard()
    action, outcome, _ = view_and_outcome(current, 10, "PUBLIC unsafe or unconfirmed result.")
    outcome = outcome.model_copy(update={"kind": "unsupported"})
    board.observe(action, outcome)
    _, data = state(board, current)
    assert data["evidence"] == [] and data["last_observation"]["kind"] == "unsupported"


def test_history_metadata_capacity_does_not_drop_required_conditions_silently():
    current, board = run(), PlanningBoard()
    for number in range(10, 74):
        action, outcome, _ = view_and_outcome(current, number, f"PUBLIC rule {number}.")
        board.observe(action, outcome)
    action, outcome, _ = view_and_outcome(current, 74, "PUBLIC final rule.")
    with pytest.raises(ValueError, match="state_limit"):
        board.observe(action, outcome)
