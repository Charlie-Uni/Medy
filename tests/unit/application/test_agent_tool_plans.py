"""PUBLIC synthetic whole-tool plans compared with actual Registry/gateway work."""

from dataclasses import replace

import pytest

from medops.application.agent_contracts import admit_action
from medops.core.errors import ErrorCode, InfrastructureError
from medops.infrastructure.llm.execution_budget import request_tokens
from medops.infrastructure.llm.gateway import ModelPrice, PriceTable
from medops.retrieval.query_translation import QueryTranslator
from tests.support.pv_agent import NOW, handle, proposal, uid, wire
from tests.support.pv_tools import parent, setup_tools


def action(current, name="search_documents", records=(), **updates):
    raw = proposal(name)
    raw["proposal"].update(updates)
    return admit_action(wire(raw), run=current, action_id=uid(280), evidence_registry=records, now=NOW)


def shape(request):
    return request.model_dump(exclude={"call", "timeout_s"})


def plan_event(tool):
    return next(e for e in tool.audit_snapshot().events if e["kind"] == "agent_tool_budget_plan")


def test_ae_plan_is_pure_and_uses_the_actual_request_and_original_retry_bound():
    current, tool, _, fake = setup_tools(script={"skill:ae_extraction": [{"elements": []}]})
    planned = tool.registry.agent_adapter().plan_extract(current.context, tool.skill_context)
    assert not fake.calls and not tool.meter.receipts and planned.max_attempts == 3
    with parent():
        tool.execute(action(current, "extract_ae"), run=current)
    assert len(fake.calls) == 1 and shape(fake.calls[0]) == shape(planned.requests[0])
    assert planned.estimate().tokens == request_tokens(fake.calls[0]) * 3
    assert "estimated_tokens" in str(plan_event(tool))


@pytest.mark.parametrize("judge,literal,expected", [(None, False, 0), ("gpt-6-sol", True, 0), ("gpt-6-sol", False, 1)])
def test_citation_plan_matches_real_skill_shortcuts_and_judge_request(judge, literal, expected):
    current, tool, _, fake = setup_tools(
        judge=judge, script={"verify": [{"verdict": "not_supported", "reason": "PUBLIC"}]}
    )
    record = handle(current)
    claims = [
        dict(
            requirement_id="guideline",
            text=record.evidence.text if literal else "PUBLIC requires preserving audit severity classifications.",
            evidence_handles=[str(record.handle)],
        )
    ]
    bound = action(current, "verify_citations", (record,), claims=claims)
    planned = tool.registry.agent_adapter().plan_verify(
        bound.proposal, current.context, {record.handle: record}, tool.skill_context, tool.facts
    )
    assert len(planned.requests) == expected and not fake.calls and not tool.meter.receipts
    with parent():
        result = tool.execute(bound, run=current, evidence_registry=(record,))
    assert result.kind == "ok" and len(fake.calls) == expected
    assert [shape(r) for r in planned.requests] == [shape(r) for r in fake.calls]


def test_whole_multi_claim_plan_refuses_before_partially_paying_for_first_claim():
    current, tool, _, fake = setup_tools(judge="gpt-6-sol")
    record = handle(current)
    claims = [
        dict(
            requirement_id="guideline",
            text=f"PUBLIC audit classification obligation {i}.",
            evidence_handles=[str(record.handle)],
        )
        for i in range(2)
    ]
    bound = action(current, "verify_citations", (record,), claims=claims)
    planned = tool.registry.agent_adapter().plan_verify(
        bound.proposal, current.context, {record.handle: record}, tool.skill_context, tool.facts
    )
    assert len(planned.requests) == 2
    cap = request_tokens(planned.requests[0]) + 1000
    with parent(token_limit=cap) as budget:
        result = tool.execute(bound, run=current, evidence_registry=(record,))
    assert result.kind == "budget_exceeded" and not fake.calls and not tool.meter.receipts
    assert budget.snapshot().accounted_tokens == 0 and result.payload is None


def test_current_meter_price_table_controls_preflight_not_module_default():
    current, tool, _, fake = setup_tools(script={"skill:ae_extraction": [{"elements": []}]})
    fake.execution_prices = PriceTable(
        {"gpt-6-sol": ModelPrice(input_per_mtok=200, output_per_mtok=1000, cached_input_per_mtok=20)}
    )
    with parent():
        result = tool.execute(action(current, "extract_ae"), run=current)
    assert result.kind == "budget_exceeded" and not fake.calls and not tool.meter.receipts


def test_agent_search_without_preview_fails_before_retrieval_or_model():
    current, tool, _, fake = setup_tools()
    retrieval = tool.skill_context.deps.retrieval
    tool.skill_context = replace(tool.skill_context, deps=replace(tool.skill_context.deps, retrieval=object()))
    with parent():
        result = tool.execute(action(current), run=current)
    assert result.kind == "dependency_error" and not retrieval.requests and not fake.calls


def test_preview_dependency_failure_cannot_start_search():
    current, tool, _, fake = setup_tools()
    retrieval = tool.skill_context.deps.retrieval

    def broken(_request):
        raise InfrastructureError(ErrorCode.dependency_unavailable, "PUBLIC unavailable")

    retrieval.model_requests = broken
    with parent():
        result = tool.execute(action(current), run=current)
    assert result.kind == "dependency_error" and not retrieval.requests and not fake.calls


def test_no_model_read_still_works_with_only_final_headroom():
    current, tool, _, fake = setup_tools()
    record = handle(current)
    with parent(token_limit=1000, cost_limit_usd=0.05):
        result = tool.execute(action(current, "read_evidence", (record,)), run=current, evidence_registry=(record,))
    assert result.kind == "ok" and not fake.calls and not tool.meter.receipts


def test_translation_preview_uses_original_query_and_actual_bound_request():
    current, tool, _, fake = setup_tools(script={"query_translation": [{"translation": "PUBLIC audit rule"}]})
    translator = QueryTranslator(tool.meter, "gpt-6-luna")
    query = "PUBLIC 药物警戒审计"
    planned = translator.request(query)
    assert planned is not None and not fake.calls and translator.request("PUBLIC audit") is None
    with parent():
        assert translator.translate(query) == "PUBLIC audit rule"
    assert shape(fake.calls[0]) == shape(planned)


@pytest.mark.parametrize("mode", ["off", "missing", "preview"])
def test_production_retrieval_preview_does_no_database_cache_or_translation_work(mode):
    from medops.harness.retrieval_port import ProductionRetrieval, RetrievalRequest
    from medops.retrieval.hybrid import HybridConfig
    from medops.retrieval.query_translation import QueryTranslator

    current, tool, _, fake = setup_tools()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preview must not perform retrieval")

    translator = QueryTranslator(tool.meter, "gpt-6-luna")
    retrieval = ProductionRetrieval(
        conn_for_user=forbidden,
        lexical_factory=forbidden,
        vector_factory=forbidden,
        reranker=None,
        config=HybridConfig(),
        translator=forbidden if mode != "off" else None,
        translation_request=translator.request if mode == "preview" else None,
    )
    request = RetrievalRequest(query="PUBLIC 药物警戒", user=current.context.principal)
    if mode == "missing":
        with pytest.raises(InfrastructureError):
            retrieval.model_requests(request)
    else:
        planned = retrieval.model_requests(request)
        assert len(planned) == int(mode == "preview")
        if planned:
            assert shape(planned[0]) == shape(translator.request(request.query))
    assert not fake.calls and not tool.meter.receipts


def test_judge_preview_refuses_unknown_multi_call_policy(monkeypatch):
    from medops.domain.answer import Claim
    from medops.verification import verifier

    current, _, _, _ = setup_tools()
    evidence = handle(current).evidence
    monkeypatch.setattr(verifier, "DEFAULT_POLICY", "rules_first")
    with pytest.raises(ValueError):
        verifier.plan_claim_judges(
            [Claim(text="PUBLIC claim", citation_chunk_ids=(evidence.citation.chunk_id,))],
            [evidence],
            judge_model_id="gpt-6-sol",
            timeout_s=30,
        )


def test_judge_preview_preserves_polarity_rule_without_a_model_request():
    from medops.domain.answer import Claim
    from medops.verification.verifier import plan_claim_judges
    from tests.support.harness_data import evidence

    fact = evidence("PUBLIC", "禁止使用本品。")
    requests = plan_claim_judges(
        [Claim(text="使用本品。", citation_chunk_ids=("PUBLIC",))], [fact], judge_model_id="gpt-6-sol", timeout_s=30
    )
    assert requests == ()
