"""Business entry points share translation, answer/judge, retries and structured Skill allowances."""

from dataclasses import replace

from medops.domain.common import DocType, ReasonCode
from medops.domain.skill import SkillStatus
from medops.harness.executions import InMemoryExecutionStore
from medops.harness.runtime import run_ask
from medops.infrastructure.llm.execution_budget import ExecutionLimits, execution_scope, request_tokens
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout, ModelUsage
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.query_translation import QueryTranslator, TranslationPool
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillRequest
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval, make_deps, state
from tests.unit.infrastructure.test_llm_gateway import _FixedCost, req
from tests.unit.skills.test_registry import EchoOut, context, entry, registry
from tests.unit.skills.test_risk_skills import ANSWER_CLAUSE, CLAUSE, ctx

ANSWER = {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}


def limits(tokens=12_000, cost=0.6):
    return ExecutionLimits(token_limit=tokens, cost_limit_usd=cost, timeout_s=10)


class TranslatingRetrieval(FakeRetrieval):
    def __init__(self, meter):
        super().__init__(evidence("c1", LABEL))
        self.translator = QueryTranslator(meter, "gpt-6-luna")
        self.pool = TranslationPool(workers=1, capacity=1)

    def retrieve(self, request):
        self.pool.submit(self.translator.translate, request.query).result(timeout=5)
        return super().retrieve(request)


def test_threaded_translation_counts_in_answer_state_and_reused_result_keeps_historical_usage():
    provider = FakeModelGateway({"query_translation": [{"translation": "What is the child dose?"}], "answer": [ANSWER]})
    meter = MeteredGateway(provider)
    retrieval = TranslatingRetrieval(meter)
    deps = make_deps(retrieval, meter, executions=InMemoryExecutionStore())
    try:
        first = run_ask(state(), deps)
        second = run_ask(state(), deps)
    finally:
        retrieval.pool.shutdown()
    assert first.outcome == second.outcome == "answered" and first.state == second.state
    assert [c.purpose for c in provider.calls] == ["query_translation", "answer"]
    assert first.state.budget.used == meter.tokens and len(meter.receipts) == 2
    assert not second.attempts


def test_translation_fallback_cannot_hide_execution_fee_exhaustion():
    provider = FakeModelGateway()
    meter = MeteredGateway(provider)
    retrieval = TranslatingRetrieval(meter)
    try:
        run = run_ask(state(), make_deps(retrieval, meter, execution_limits=limits(cost=0)))
    finally:
        retrieval.pool.shutdown()
    assert run.outcome == "escalated" and run.state.escalation.reason_codes == (ReasonCode.budget_exceeded,)
    assert provider.calls == [] and meter.receipts[0].outcome == "denied"


def test_unknown_billable_timeout_leaves_no_capacity_for_a_second_provider_attempt():
    probe = FakeModelGateway({"answer": [ANSWER]})
    run_ask(state(), make_deps(FakeRetrieval(evidence("c1", LABEL)), probe))
    cap = request_tokens(probe.calls[0])
    provider = FakeModelGateway({"answer": [ModelTimeout(), ANSWER]})
    meter = MeteredGateway(provider)
    run = run_ask(state(), make_deps(FakeRetrieval(evidence("c1", LABEL)), meter, execution_limits=limits(tokens=cap)))
    assert run.state.escalation.reason_codes == (ReasonCode.budget_exceeded,)
    assert [a.outcome for a in run.attempts if a.node == "answer"] == ["retry", "failed"]
    assert len(provider.calls) == 1 and run.state.budget.used == cap
    assert meter.receipts[0].usage is None and meter.receipts[0].accounted_cost_usd > 0


def test_claim_judge_cannot_ignore_the_answers_accounted_fee():
    class HighFeeAnswer(FakeModelGateway):
        def complete(self, request):
            return super().complete(request).model_copy(update={"cost_usd": 0.59999})

    provider = HighFeeAnswer(
        {
            "answer": [
                {"claims": [{"text": "6 至 12 歲幼兒每天分三次口服，每次 100 mg。", "citation_chunk_ids": ["c1"]}]}
            ]
        }
    )
    meter = MeteredGateway(provider)
    run = run_ask(state(), make_deps(FakeRetrieval(evidence("c1", LABEL)), meter, judge_model_id="gpt-6-sol"))
    assert run.state.escalation.reason_codes == (ReasonCode.budget_exceeded,)
    assert [c.purpose for c in provider.calls] == ["answer"]
    assert meter.cost_usd == 0.59999 and meter.receipts[-1].call.purpose == "verify"


def test_second_stage_of_real_protocol_skill_cannot_reopen_the_grounded_answers_budget():
    class ExpensiveAnswer(FakeModelGateway):
        def complete(self, request):
            response = super().complete(request)
            if request.purpose == "answer":
                return response.model_copy(update={"usage": ModelUsage(input_tokens=11_000, output_tokens=200)})
            return response

    reg = default_registry(sleep=lambda _: None)
    provider = ExpensiveAnswer({"answer": [ANSWER_CLAUSE]})
    meter = MeteredGateway(provider)
    context = ctx(
        reg, meter, FakeRetrieval(evidence("c1", CLAUSE, doc_id="doc-cfr")), {"doc-cfr": DocType.guideline}, dept="CO"
    )
    run = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "21 CFR 812.110", "topic": "器械交付", "observation": "x"},
        context=context,
    )
    assert run.output.status is SkillStatus.escalated and run.output.reason_codes == (ReasonCode.budget_exceeded,)
    assert [c.purpose for c in provider.calls] == ["answer"]
    assert meter.tokens == 11_200 and meter.receipts[-1].outcome == "denied"


def test_multiple_skills_in_one_execution_cannot_obtain_fresh_child_budgets():
    def complete(ctx, inp):
        ctx.deps.gateway.complete(req())
        return EchoOut(status=SkillStatus.completed, text=inp.text)

    reg = registry(entry(handler=complete))
    provider = _FixedCost(0.00001)
    c = context(reg)
    c = replace(c, deps=replace(c.deps, gateway=provider))
    cap = request_tokens(req())
    # The first call uses 15 actual tokens. Its next call still needs a full admission allowance.
    with execution_scope(limits(tokens=cap)):
        runs = reg.execute_many(
            [SkillRequest("echo_skill", "1.0.0", {"text": "a"}), SkillRequest("echo_skill", "1.0.0", {"text": "b"})],
            context=c,
        )
    assert provider.calls == 1 and runs[0].output.status is SkillStatus.completed
    assert runs[1].output.reason_codes == (ReasonCode.budget_exceeded,)
