"""Real AgentTools/Registry/Meter budget admission with PUBLIC fake providers."""

from medops.application.agent_contracts import admit_action
from medops.infrastructure.llm.execution_budget import request_tokens
from tests.support.pv_agent import NOW, proposal, uid, wire
from tests.support.pv_tools import parent, setup_tools


def extract_setup():
    current, tool, facts, fake = setup_tools(
        script={"skill:ae_extraction": [{"elements": [{"kind": "event", "value": "an event", "quote": "an event"}]}]}
    )
    action = admit_action(wire(proposal("extract_ae")), run=current, action_id=uid(200), evidence_registry=(), now=NOW)
    return current, tool, fake, action


def test_ae_cannot_spend_the_final_verification_reserve():
    baseline, tool, fake, action = extract_setup()
    with parent():
        assert tool.execute(action, run=baseline).kind == "ok"
    tool_request = fake.calls[0]
    current, tool, fake, action = extract_setup()
    cap = request_tokens(tool_request) + current.context.profile.final_reserve_tokens // 2
    with parent(token_limit=cap) as budget:
        result = tool.execute(action, run=current)
    assert result.kind == "budget_exceeded"
    assert not fake.calls and budget.snapshot().accounted_tokens == 0
    assert not tool.meter.receipts  # whole-tool refusal precedes any logical model call


def test_ae_fee_protection_rejects_before_provider():
    from medops.infrastructure.llm.accounting import new_call
    from medops.infrastructure.llm.execution_budget import allowance

    baseline, tool, fake, action = extract_setup()
    with parent():
        assert tool.execute(action, run=baseline).kind == "ok"
    request = fake.calls[0]
    estimated = allowance(request.model_copy(update={"call": new_call(request, "fake")}))
    current, tool, fake, action = extract_setup()
    floor = current.context.profile.final_reserve_cost_microusd / 1_000_000
    with parent(cost_limit_usd=floor + estimated.cost_usd / 2) as budget:
        result = tool.execute(action, run=current)
    assert result.kind == "budget_exceeded" and not fake.calls
    assert budget.snapshot().accounted_cost_usd == 0 and budget.protection().cost_usd == floor
    assert not tool.meter.receipts  # whole-tool refusal precedes any logical model call


def verification_setup():
    from tests.support.pv_agent import handle

    current, tool, _, fake = setup_tools(
        judge="gpt-6-sol", script={"verify": [{"verdict": "not_supported", "reason": "PUBLIC missing rule"}]}
    )
    record = handle(current)
    body = proposal("verify_citations")
    body["proposal"]["claims"] = [
        dict(
            requirement_id="guideline",
            text="PUBLIC requires preserving audit severity classifications.",
            evidence_handles=[str(record.handle)],
        )
    ]
    action = admit_action(wire(body), run=current, action_id=uid(201), evidence_registry=(record,), now=NOW)
    return current, tool, fake, action, record


def test_real_citation_skill_cannot_consume_final_verification_headroom():
    current, tool, fake, action, record = verification_setup()
    with parent():
        assert tool.execute(action, run=current, evidence_registry=(record,)).kind == "ok"
    assert len(fake.calls) == 1 and fake.calls[0].purpose == "verify"
    n = request_tokens(fake.calls[0])
    current, tool, fake, action, record = verification_setup()
    with parent(token_limit=n + 500) as budget:
        result = tool.execute(action, run=current, evidence_registry=(record,))
    assert result.kind == "budget_exceeded" and not fake.calls
    assert budget.snapshot().accounted_tokens == 0 and budget.protection().tokens == 1000
    assert not tool.meter.receipts  # whole-tool refusal precedes any logical model call


def translation_setup():
    from medops.retrieval.query_translation import QueryTranslator

    current, tool, _, fake = setup_tools(script={"query_translation": [{"translation": "PUBLIC audit rule"}]})
    retrieval = tool.skill_context.deps.retrieval
    original = retrieval.retrieve
    translator = QueryTranslator(tool.meter, "gpt-6-luna")

    def retrieve(request):
        translator.translate(request.query)
        return original(request)

    retrieval.retrieve = retrieve
    retrieval.model_requests = lambda request: (translator.request(request.query),)
    body = proposal()
    body["proposal"]["query"] = "PUBLIC 药物警戒审计的分类"
    action = admit_action(wire(body), run=current, action_id=uid(202), evidence_registry=(), now=NOW)
    return current, tool, fake, action


def test_translation_budget_denial_cannot_be_hidden_by_ordinary_search_fallback():
    current, tool, fake, action = translation_setup()
    with parent():
        assert tool.execute(action, run=current).kind == "ok"
    assert len(fake.calls) == 1 and fake.calls[0].purpose == "query_translation"
    n = request_tokens(fake.calls[0])
    current, tool, fake, action = translation_setup()
    with parent(token_limit=n + 500) as budget:
        result = tool.execute(action, run=current)
    assert result.kind == "budget_exceeded" and not fake.calls
    assert budget.snapshot().blocked_reason is None and budget.protection().tokens == 1000
    assert not tool.meter.receipts  # whole-tool refusal precedes any logical model call


def test_loop_checkpoints_keep_actual_protection_separate_from_usage_and_pending_calls():
    from tests.support.pv_loop import setup_loop, terminal

    current, loop, driver, fake, meter = setup_loop({"agent_plan": [terminal()]})
    with parent() as budget:
        result = loop.run(current)
    assert result.reason == "completed" and result.run.status == "running" and len(fake.calls) == 1
    assert all(e.budget_protection == budget.protection() for e in driver.events)
    assert budget.snapshot().protected_tokens == current.context.profile.final_reserve_tokens
    assert result.run.budget.reserved_tokens == result.run.budget.reserved_cost_microusd == 0
    assert result.run.budget.accounted_tokens == meter.tokens and meter.calls == 1


def test_fresh_loop_refuses_foreign_protection_without_overwriting_it():
    from medops.infrastructure.llm.execution_budget import BudgetProtection
    from tests.support.pv_loop import setup_loop

    current, loop, driver, fake, _ = setup_loop()
    protected = BudgetProtection(tokens=500, cost_usd=0.02)
    with parent() as budget:
        budget.protect_remaining(protected)
        result = loop.run(current)
    assert result.reason == "unsupported_recovery" and not fake.calls and result.run.decisions_consumed == 0
    assert budget.protection() == protected and driver.events[-1].budget_protection is None
    assert driver.events[-1].progress is None


def test_loop_tool_timeout_retains_unknown_usage_and_final_protection():
    from medops.infrastructure.llm.gateway import ModelTimeout
    from tests.support.pv_loop import setup_loop, terminal

    current, loop, driver, fake, meter = setup_loop(
        {
            "agent_plan": [proposal("extract_ae"), terminal()],
            "skill:ae_extraction": [ModelTimeout(), ModelTimeout(), ModelTimeout()],
        }
    )
    with parent() as budget:
        result = loop.run(current)
    assert result.reason == "timeout" and len(fake.calls) == len(meter.receipts) == 4
    assert result.run.decisions_consumed == 1 and result.terminal_request is None
    assert budget.snapshot().accounted_tokens > budget.snapshot().known_tokens
    assert budget.protection().tokens == 1000 and budget.protection().cost_usd == 0.05
    assert driver.events[-1].budget_protection == budget.protection()
    assert any(r.cost_basis == "conservative_reservation" for r in meter.receipts)


def test_whole_skill_retry_bound_is_checked_before_any_model_call():
    from medops.infrastructure.llm.gateway import ModelTimeout

    current, tool, fake, action = extract_setup()
    with parent():
        assert tool.execute(action, run=current).kind == "ok"
    n = request_tokens(fake.calls[0])
    current, tool, _, fake = setup_tools(
        script={"skill:ae_extraction": [ModelTimeout(), ModelTimeout(), ModelTimeout()]}
    )
    action = admit_action(wire(proposal("extract_ae")), run=current, action_id=uid(203), evidence_registry=(), now=NOW)
    with parent(token_limit=2 * n + 999) as budget:
        result = tool.execute(action, run=current)
    assert result.kind == "budget_exceeded" and not fake.calls
    assert not tool.meter.receipts
    assert budget.snapshot().accounted_tokens == budget.snapshot().known_tokens == 0
    assert budget.protection().tokens == 1000
