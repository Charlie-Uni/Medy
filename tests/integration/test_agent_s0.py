"""AGENT-07: original PUBLIC S0 scenarios through actual durable PG execution."""

import json

import pytest

from tests.support.agent_integration import s0_case


def execute(case):
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
        with case["connection"]() as conn:
            conn.execute("select set_config('medops.dept','PV',true)")
            store = execution.driver._store(conn)
            events, calls = store.events(), store.calls()
            control = execution.driver._control(conn).get()
            assert control.terminal_status == result.run.status
            assert control.terminal_ref is not None
            assert len([e for e in events if e.body.get("kind") == "business_terminal"]) == 1
        assert len(calls) == len(case["gateway"].calls)
        assert len([e for e in events if e.kind == "call_admitted"]) == len(calls)
    assert case["runtime"].result(case["context"], user=case["context"].principal) == result
    assert not result.material.same_run_resumable
    assert result.run.decisions_consumed <= 8
    assert result.run.budget.accounted_tokens + result.run.budget.reserved_tokens <= 12000
    return result


@pytest.mark.parametrize("path", ["complete", "empty_then_rewrite", "adjacent_read"])
def test_s0_01_03_06_actual_observations_change_paths_and_commit_joint_evidence(db, path):
    case = s0_case(db, empty_first=path == "empty_then_rewrite", partial=path == "adjacent_read")
    result = execute(case)
    assert result.run.status == "completed", (
        result.run.terminal.reason,
        [a.model_dump(mode="json") for a in result.material.committed_actions],
        [r.purpose for r in case["gateway"].calls],
    )
    review = result.material.review
    assert len(review.narrative_facts) == 4 and len(review.evidence) == 2
    for fact in review.narrative_facts:
        assert case["context"].narrative[fact.char_start : fact.char_end] == fact.quote == fact.value
    assert {f.value for f in review.narrative_facts} == {"一名成年人", "合成药品A", "皮疹", "2026-10-01"}
    assert len(review.guideline_claims) == 2
    assert {g for c in review.guideline_claims for g in c.support_groups} == {(e.handle,) for e in review.evidence}
    assert {e.citation.doc_id for e in review.evidence} == {case["doc"]}
    assert {e.citation.version for e in review.evidence} == {"PUBLIC v1"}
    actions = [a.action for a in result.material.committed_actions]
    expected = ["search_documents"]
    if path == "empty_then_rewrite":
        expected.append("search_documents")
        requests = case["retrieval"].requests
        assert len(requests) == 2 and requests[0].query != requests[1].query
        assert case["gateway"].boards[1]["last_observation"] == {"action": "search_documents", "kind": "empty"}
    elif path == "adjacent_read":
        expected.append("read_evidence")
        assert len(case["retrieval"].requests) == 1
        assert len(case["gateway"].boards[1]["evidence"]) == 1
        assert len(case["gateway"].boards[2]["evidence"]) == 2
    assert actions == expected
    projections = json.dumps(case["gateway"].boards, ensure_ascii=False)
    for private_key in ('"private_environment"', '"expected"', '"observations"', "HIDDEN-MA-CANARY-S0"):
        assert private_key not in projections


def test_s0_05_missing_attachment_limit_is_not_invented_or_completed(db):
    case = s0_case(db, missing=True)
    result = execute(case)
    assert result.run.status == "escalated" and result.run.terminal.reason == "insufficient_evidence", (
        result.run.terminal.reason,
        [r.purpose for r in case["gateway"].calls],
        [a.model_dump(mode="json") for a in result.material.committed_actions],
    )
    assert result.material.missing_requirement_ids == ("event", "guideline")
    assert result.material.review is None and not result.material.extracted_elements
    assert "99 MB" not in result.material.model_dump_json()
    assert [r.purpose for r in case["gateway"].calls][-1] == "agent_final_stop"


def test_s0_07_retrieval_timeout_is_system_failure_not_correct_abstention(db):
    case = s0_case(db, timeout=True)
    result = execute(case)
    assert result.run.status == "failed" and result.run.terminal.reason == "timeout"
    assert result.material.review is None
    assert [r.purpose for r in case["gateway"].calls] == ["agent_plan"]
    assert result.run.budget.accounted_tokens > 0


@pytest.mark.parametrize("defect", ["changed_date", "omitted_condition"])
def test_s0_11_final_gate_rejects_credible_but_incorrect_material(db, defect):
    case = s0_case(db, defect=defect)
    result = execute(case)
    assert result.run.status == "escalated" and result.run.terminal.reason != "completed"
    assert any(r.purpose == "agent_final_material" for r in case["gateway"].calls)
    if defect == "changed_date":
        assert not result.material.review.narrative_facts
    else:
        assert "guideline" in result.material.missing_requirement_ids


def test_s0_11_existing_citation_does_not_support_an_invented_attachment_limit(db):
    from medops.infrastructure.llm.fake import FakeModelGateway
    from tests.support.agent_runtime import runtime_case
    from tests.support.agent_terminal import PublicRetrievalAgent
    from tests.support.pv_review import final_config

    class UnsupportedGateway(PublicRetrievalAgent):
        def complete(self, request):
            response = super().complete(request)
            raw = json.loads(response.text)
            if request.purpose == "agent_plan" and raw["proposal"]["action"] == "finish":
                raw["proposal"]["draft"]["guideline_claims"][0]["text"] = "PUBLIC attachment limit is 99 MB."
            elif request.purpose == "verify":
                raw = {"verdict": "not_supported", "reason": "PUBLIC cited source has no attachment limit"}
            return FakeModelGateway(default=[raw]).complete(request)

    gateway = UnsupportedGateway()
    case = runtime_case(
        db,
        gateway,
        final_config=final_config(max_review_user_bytes=2000, max_citation_judges=1, citation_attempts=1),
    )
    case["gateway"] = gateway
    result = execute(case)
    assert result.run.status == "escalated" and not result.material.review.guideline_claims
    assert len(case["gateway"].calls) == 4
    assert [r.purpose for r in gateway.calls][-2:] == ["verify", "agent_final_material"]


def test_s0_12_unavailable_history_is_clarified_without_silent_current_source_fallback(db):
    case = s0_case(db, history=True)
    result = execute(case)
    assert result.run.status == "awaiting_clarification"
    assert result.material.questions[0].field == "source_version"
    assert not result.material.review and not result.material.extracted_elements
    assert [r.purpose for r in case["gateway"].calls] == ["agent_plan", "agent_final_stop"]
    assert case["gateway"].boards[0]["source"]["requested_version"] == "PUBLIC unavailable v0"
    assert case["gateway"].boards[0]["query_context"] == {"as_of": "2020-01-01", "historical_requested": True}


def test_s0_09_whole_extraction_envelope_preserves_final_reserve_and_stops_before_skill_provider(db):
    case = s0_case(db, extract=True)
    result = execute(case)
    assert result.run.status == "failed" and result.run.terminal.reason == "budget_exceeded"
    assert result.material.committed_actions[0].outcome == "budget_exceeded"
    assert [r.purpose for r in case["gateway"].calls] == ["agent_plan"]
    assert result.run.budget.accounted_tokens > 0
