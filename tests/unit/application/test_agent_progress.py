"""Stable information fingerprints, PUBLIC synthetic material only."""

from dataclasses import asdict
from datetime import timedelta

import pytest

from medops.application.agent_contracts import admit_action
from medops.application.agent_progress import PROGRESS_VERSION, AgentProgress
from medops.application.agent_tool_results import (
    AgentToolOutcome,
    ClaimToolCheck,
    EvidenceView,
    ExtractedElement,
    ExtractionPayload,
    ReadPayload,
    SearchPayload,
    VerificationPayload,
)
from medops.core.canonical import sha256_hex
from medops.domain.agent_execution import BoundAction
from tests.support.pv_agent import NOW, handle, proposal, run, uid, wire


def action_for(current, name="search_documents", *, registry=(), **updates):
    body = proposal(name)
    body["proposal"].update(updates)
    return admit_action(wire(body), run=current, action_id=uid(900), evidence_registry=registry, now=NOW)


def view_for(record, take=None):
    e = record.evidence
    text = e.text if take is None else e.text[:take]
    return EvidenceView(
        handle=record.handle,
        citation=e.citation,
        text=text,
        char_end=len(text),
        truncated=len(text) < len(e.text),
        evidence_text_sha256=e.evidence_text_hash,
        source_sha256=record.source_sha256,
    )


def outcome_for(action, payload=None, kind="ok", **updates):
    return AgentToolOutcome(action_id=action.action_id, binding=action.binding, kind=kind, payload=payload, **updates)


def test_reissue_reorder_duplicates_and_envelope_counters_are_not_new_information():
    current = run()
    original = handle(current)
    alias = original.model_copy(update={"handle": uid(11), "expires_at": original.expires_at - timedelta(seconds=1)})
    first = action_for(current)
    second = first.model_copy(update={"action_id": uid(901), "decision_index": 2})
    tracker = AgentProgress()
    a = tracker.observe(first, outcome_for(first, SearchPayload(matches=(view_for(original),))), (original,))
    b = tracker.observe(
        second,
        outcome_for(
            second,
            SearchPayload(matches=(view_for(alias), view_for(original))),
            call_receipt_ids=("PUBLIC-new-receipt",),
            issued_handles=(alias,),
            new_handles_issued=True,
        ),
        (original, alias),
    )
    assert a.action_sha256 == b.action_sha256 and a.result_sha256 == b.result_sha256
    assert b.consecutive == 2 and b.version == PROGRESS_VERSION
    assert "PUBLIC" not in str(asdict(b)) and str(original.handle) not in str(asdict(b))


@pytest.mark.parametrize(
    "left,right",
    [
        ("PUBLIC query?", "ＰＵＢＬＩＣ  query！？"),
        ("PUBLIC query.", "PUBLIC query"),
        ("PUBLIC,query", "PUBLIC query"),
        ("PUBLIC query；", "PUBLIC query!"),
    ],
)
def test_cosmetic_search_edits_do_not_reset_streak(left, right):
    current, tracker = run(), AgentProgress()
    for query in [left, right]:
        action = action_for(current, query=query)
        state = tracker.observe(action, outcome_for(action, SearchPayload(matches=()), "empty"), ())
    assert state.consecutive == 2


@pytest.mark.parametrize(
    "left,right",
    [
        ("PUBLIC 1.5 mg", "PUBLIC 15 mg"),
        ("PUBLIC -1 mg", "PUBLIC 1 mg"),
        ("PUBLIC <=5 mg", "PUBLIC >=5 mg"),
        ("PUBLIC mM", "PUBLIC mm"),
        ("PUBLIC NOT recommended", "PUBLIC recommended"),
        ("PUBLIC HLA-B*57:01", "PUBLIC HLA-B*57:02"),
        ("PUBLIC 1,2 mg", "PUBLIC 12 mg"),
        ("PUBLIC 1,5 mg", "PUBLIC 1 5 mg"),
        ("PUBLIC x²", "PUBLIC x2"),
    ],
)
def test_numeric_negative_unit_identifier_and_real_query_changes_are_preserved(left, right):
    current, tracker = run(), AgentProgress()
    for query in [left, right]:
        action = action_for(current, query=query)
        state = tracker.observe(action, outcome_for(action, SearchPayload(matches=()), "empty"), ())
    assert state.consecutive == 1


def test_new_excerpt_or_evidence_identity_changes_stable_information():
    current, tracker = run(), AgentProgress()
    record = handle(current)
    action = action_for(current)
    for take in [6, None]:
        state = tracker.observe(
            action, outcome_for(action, SearchPayload(matches=(view_for(record, take),))), (record,)
        )
        assert state.consecutive == 1
    citation = record.evidence.citation.model_copy(update={"page": 2, "chunk_id": "PUBLIC-neighbor"})
    neighbor = record.model_copy(
        update={"handle": uid(11), "evidence": record.evidence.model_copy(update={"citation": citation})}
    )
    state = tracker.observe(
        action, outcome_for(action, SearchPayload(matches=(view_for(neighbor),))), (record, neighbor)
    )
    assert state.consecutive == 1
    state = tracker.observe(
        action, outcome_for(action, SearchPayload(matches=(view_for(neighbor),))), (record, neighbor)
    )
    assert state.consecutive == 2


@pytest.mark.parametrize("change", ["text", "source_hash", "status", "version", "content_hash"])
def test_evidence_conditions_and_text_changes_are_not_ignored(change):
    current, tracker = run(), AgentProgress()
    original = handle(current)
    revised = original
    if change == "text":
        text = "PUBLIC revised evidence: do NOT use 1.5 mg."
        revised = original.model_copy(
            update={
                "evidence": original.evidence.model_copy(update={"text": text, "evidence_text_hash": sha256_hex(text)})
            }
        )
    elif change == "source_hash":
        revised = original.model_copy(update={"source_sha256": "b" * 64})
    elif change == "status":
        revised = original.model_copy(
            update={"evidence": original.evidence.model_copy(update={"status": "archived", "historical": True})}
        )
    elif change == "version":
        revised = original.model_copy(
            update={
                "evidence": original.evidence.model_copy(
                    update={"citation": original.evidence.citation.model_copy(update={"version": "PUBLIC v2"})}
                )
            }
        )
    else:
        revised = original.model_copy(
            update={"evidence": original.evidence.model_copy(update={"chunk_content_hash": "b" * 64})}
        )
    action = action_for(current)
    for record in [original, revised]:
        state = tracker.observe(action, outcome_for(action, SearchPayload(matches=(view_for(record),))), (record,))
    assert state.consecutive == 1  # live validation still rejects illegal fact/version changes


def test_read_aliases_are_same_parameters_but_regions_are_distinct():
    current, tracker = run(), AgentProgress()
    first = handle(current)
    alias = first.model_copy(update={"handle": uid(11)})
    registry = (first, alias)
    for h in [first, alias]:
        action = action_for(current, "read_evidence", registry=registry, handle=str(h.handle))
        state = tracker.observe(action, outcome_for(action, ReadPayload(evidence=view_for(h))), registry)
    assert state.consecutive == 2
    action = action_for(current, "read_evidence", registry=registry, handle=str(alias.handle), region="next")
    assert tracker.observe(action, outcome_for(action, None, "empty"), registry).consecutive == 1


def test_verification_handle_aliases_are_same_but_changed_support_resets_streak():
    current, tracker = run(), AgentProgress()
    first = handle(current)
    alias = first.model_copy(update={"handle": uid(11)})
    registry = (first, alias)
    for h in [first, alias]:
        claims = [dict(requirement_id="guideline", text="PUBLIC rule", evidence_handles=[str(h.handle)])]
        action = action_for(current, "verify_citations", registry=registry, claims=claims)
        check = ClaimToolCheck(
            requirement_id="guideline",
            text="PUBLIC rule",
            verdict="not_supported",
            requested_handles=(h.handle,),
            supporting_handles=(),
            unconfirmed_handles=(h.handle,),
        )
        state = tracker.observe(
            action, outcome_for(action, VerificationPayload(checks=(check,), verifier_version="PUBLIC-v1")), registry
        )
    assert state.consecutive == 2
    supported = check.model_copy(
        update={"verdict": "supported", "supporting_handles": (alias.handle,), "unconfirmed_handles": ()}
    )
    state = tracker.observe(
        action, outcome_for(action, VerificationPayload(checks=(supported,), verifier_version="PUBLIC-v1")), registry
    )
    assert state.consecutive == 1


def test_extraction_uses_grounded_elements_and_missing_fields_not_drop_counters():
    current, tracker = run(), AgentProgress()
    action = action_for(current, "extract_ae")
    element = ExtractedElement(kind="event", value="PUBLIC", quote="PUBLIC", char_start=0, char_end=6)
    payload = ExtractionPayload(
        skill_status="completed",
        elements=(element,),
        missing_kinds=("patient",),
        unaligned_elements=0,
        dropped_ungrounded=0,
        dropped_causality=0,
    )
    tracker.observe(action, outcome_for(action, payload), ())
    payload = payload.model_copy(update={"dropped_ungrounded": 1, "dropped_causality": 2})
    assert tracker.observe(action, outcome_for(action, payload), ()).consecutive == 2
    payload = payload.model_copy(update={"missing_kinds": ("reporter",)})
    assert tracker.observe(action, outcome_for(action, payload), ()).consecutive == 1


def test_non_ok_payload_cannot_claim_new_information_and_kind_changes_remain_visible():
    current, tracker = run(), AgentProgress()
    record = handle(current)
    action = action_for(current)
    tracker.observe(action, outcome_for(action, None, "unsupported"), ())
    state = tracker.observe(action, outcome_for(action, SearchPayload(matches=(view_for(record),)), "unsupported"), ())
    assert state.consecutive == 2
    assert tracker.observe(action, outcome_for(action, None, "denied_or_unavailable"), ()).consecutive == 1


def test_invalid_proposal_interrupts_the_consecutive_streak():
    current, tracker = run(), AgentProgress()
    action = action_for(current)
    outcome = outcome_for(action, SearchPayload(matches=()), "empty")
    tracker.observe(action, outcome, ())
    tracker.reset()
    assert tracker.snapshot().consecutive == 0
    assert tracker.observe(action, outcome, ()).consecutive == 1


def test_unknown_handle_and_terminal_action_fail_closed_without_mutating_checkpoint():
    current, tracker = run(), AgentProgress()
    record = handle(current)
    action = action_for(current)
    with pytest.raises(ValueError, match="unknown_handle"):
        tracker.observe(action, outcome_for(action, SearchPayload(matches=(view_for(record),))), ())
    assert tracker.snapshot().consecutive == 0
    action = BoundAction(
        action_id=uid(901), binding=action.binding, decision_index=1, proposal=proposal("clarify")["proposal"]
    )
    with pytest.raises(ValueError, match="requires_tool_action"):
        tracker.observe(action, outcome_for(action, None, "unsupported"), ())
    assert tracker.snapshot().consecutive == 0
