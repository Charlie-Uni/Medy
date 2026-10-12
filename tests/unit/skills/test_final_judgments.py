"""ARCH-03: legal citations alone must not validate a business conclusion."""

import json
from dataclasses import replace

import pytest

from medops.domain.common import DocType, ReasonCode
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.catalog import default_registry
from tests.support.harness import FakeRetrieval
from tests.support.harness_data import evidence
from tests.support.risk_skills import ctx
from tests.support.skill_judgments import supported_reply


def test_original_visit_window_inversion_cannot_complete():
    clause = "访视必须在第 8 至 10 天完成。"
    reg = default_registry(sleep=lambda _s: None)
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "visit_window",
                    "rationale_statement_indices": [1],
                    "rationale": "第 9 天在第 8 至 10 天范围之外",
                }
            ],
        }
    )
    out = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "方案 A", "topic": "访视窗口", "observation": "访视在第 9 天完成。"},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, dept="CO"),
    ).output
    assert out.status is not SkillStatus.completed
    assert out.deviation == "undetermined" and out.rationale == ""
    assert out.judgment_verification.checks[0].rule_failures == ("visit_window_contradiction",)


@pytest.mark.parametrize(
    "clause,observation,rationale,failed_check",
    [
        ("每日剂量不得超过 8 mg。", "每日 12 mg", "12 mg 在最大剂量内", "conclusion"),
        ("必须在给药前取得书面同意。", "给药前没有取得书面同意", "已取得同意，未偏离", "observation_grounding"),
        (
            "仅在病情稳定时允许第 9 天访视。",
            "第 9 天访视，病情是否稳定未记录",
            "第 9 天访视，所以没有偏离",
            "rationale",
        ),
        ("书面同意必须在操作前取得。", "访视在第 9 天完成", "第 9 天在访视窗口内", "clause_relevance"),
    ],
)
def test_semantic_counterexamples_cannot_complete_through_real_registry(clause, observation, rationale, failed_check):
    reg = default_registry(sleep=lambda _s: None)
    verdict = supported_reply("deviation")
    verdict["checks"][0][failed_check] = "not_supported"
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:protocol_deviation": [
                {
                    "deviation": "no",
                    "deviation_type": "none",
                    "rationale_statement_indices": [1],
                    "rationale": rationale,
                }
            ],
            "skill:verify_judgment": [verdict],
        }
    )
    out = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "方案 A", "topic": "条款比对", "observation": observation},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, dept="CO"),
    ).output
    assert out.status is SkillStatus.insufficient_evidence and out.reason_codes == (ReasonCode.unsupported_conclusion,)
    assert out.deviation == "undetermined" and out.rationale == "" and out.rationale_clause_indices == ()
    assert out.judgment_verification is not None and not out.judgment_verification.supported
    payload = json.loads(gateway.calls[-1].messages[1].content)["judgments"][0]
    assert payload["observation"] == observation and payload["rationale"] == rationale


@pytest.mark.parametrize("indices", [[True], ["1"], [1.0]])
def test_boolean_string_or_float_indices_fail_before_final_judge(indices):
    reg = default_registry(sleep=lambda _s: None)
    clause = "必须在操作前取得书面同意。"
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "consent",
                    "rationale_statement_indices": indices,
                    "rationale": "未取得同意",
                }
            ],
        }
    )
    out = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "方案 A", "topic": "同意", "observation": "操作前未取得同意"},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, dept="CO"),
    ).output
    assert out.status is SkillStatus.escalated and out.reason_codes == (ReasonCode.system_failure,)
    assert [c.purpose for c in gateway.calls] == ["answer", "skill:protocol_deviation"]


def test_async_task_preserves_non_completion_of_the_business_judgment():
    from medops.application.contracts import TaskCreateRequest, TaskStatus
    from medops.application.tasks import InMemoryTaskStore, TaskRunner, TaskService
    from tests.support.risk_skills import user
    from tests.support.tasks import Clock, FakeEnv

    clock = Clock()
    reg = default_registry(sleep=lambda _s: None)
    u = user("CO")
    store = InMemoryTaskStore(clock=clock)
    clause = "A visit is permitted only on days 8 through 10."
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "visit_window",
                    "rationale_statement_indices": [1],
                    "rationale": "Day 9 is outside the permitted interval of days 8 through 10.",
                }
            ],
        }
    )

    class Env(FakeEnv):
        def skill_context(self, conn, selected_user, trace_id, historical):
            selected = ctx(
                reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, u=selected_user
            )
            return replace(selected, trace_id=trace_id, run_id=trace_id)

    TaskService(store=store, clock=clock).create(
        u,
        TaskCreateRequest(
            skill_name="protocol_deviation",
            skill_version="1.0.0",
            input={"governing_document": "方案 A", "topic": "访视窗口", "observation": "Visit on day 9."},
        ),
        None,
    )
    env = Env(store, reg, {u.user_id: u})
    result = TaskRunner(env=env, registry=reg, worker_id="w1", clock=clock).run_once()
    assert result.record.status is TaskStatus.completed  # job terminal state, NOT the business outcome
    assert result.record.result["status"] == "escalated"
    assert result.record.result["output"]["deviation"] == "undetermined"
    assert result.record.result["output"]["rationale"] == ""
    assert env.traces.traces[result.record.trace_id].outcome == "escalated"
    trace = env.traces.traces[result.record.trace_id]
    assert trace.evidence_chunk_ids == ("c1",)
    assert trace.cited_chunk_ids == ("c1",)  # preserved verified clauses, not the rejected comparison
    assert {s.node for s in trace.spans} >= {"retrieve", "verify", "skill:verify_judgment"}


def test_final_judge_timeout_is_bounded_and_keeps_no_candidate_payload():
    from medops.infrastructure.llm.gateway import ModelTimeout

    reg = default_registry(sleep=lambda _s: None)
    clause = "必须在操作前取得书面同意。"
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}] * 3,
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "consent",
                    "rationale_statement_indices": [1],
                    "rationale": "操作前未取得同意",
                }
            ]
            * 3,
            "skill:verify_judgment": [ModelTimeout()] * 3,
        }
    )
    out = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "方案 A", "topic": "同意", "observation": "操作前未取得同意"},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, dept="CO"),
    ).output
    assert out.status is SkillStatus.escalated and out.rendered_texts() == ()
    assert out.reason_codes[0] in (ReasonCode.system_failure, ReasonCode.budget_exceeded)
    assert 1 <= sum(c.purpose == "skill:verify_judgment" for c in gateway.calls) <= 3


@pytest.mark.parametrize("reply_dimensions", [("dose", "dose"), ("dose",), ("dose", "population")])
def test_off_label_missing_duplicate_or_unrequested_dimensions_fail_closed(reply_dimensions):
    reg = default_registry(sleep=lambda _s: None)
    clause = "每日最高剂量为 8 mg。"
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:off_label_check": [
                {
                    "findings": [
                        {
                            "dimension": d,
                            "finding": "outside_label",
                            "statement_indices": [1],
                            "note": "超出每日最高剂量",
                        }
                        for d in reply_dimensions
                    ]
                }
            ],
        }
    )
    out = reg.execute(
        "off_label_check",
        "1.0.0",
        {"product": "药 A", "proposed_use": {"dose": "每日 12 mg", "route": "口服"}},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.label}, dept="MA"),
    ).output
    assert out.status is SkillStatus.escalated and out.reason_codes == (ReasonCode.system_failure,)
    assert out.rendered_texts() == ()


def test_off_label_false_within_scope_does_not_return_the_wrong_finding_or_note():
    reg = default_registry(sleep=lambda _s: None)
    clause = "每日最高剂量为 8 mg。"
    gateway = FakeModelGateway(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:off_label_check": [
                {
                    "findings": [
                        {
                            "dimension": "dose",
                            "finding": "within_label",
                            "statement_indices": [1],
                            "note": "每日 0.012 g 在范围内",
                        }
                    ]
                }
            ],
        }
    )
    out = reg.execute(
        "off_label_check",
        "1.0.0",
        {"product": "药 A", "proposed_use": {"dose": "每日 0.012 g"}},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.label}, dept="MA"),
    ).output
    assert out.status is SkillStatus.escalated and out.reason_codes == (ReasonCode.unsupported_conclusion,)
    assert (
        out.findings[0].finding == "not_addressed"
        and out.findings[0].note == ""
        and out.findings[0].clause_indices == ()
    )
    assert out.judgment_verification.checks[0].rule_failures == ("daily_maximum_contradiction",)


def test_final_judge_cannot_reopen_the_shared_execution_budget():
    from medops.infrastructure.llm.gateway import ModelUsage

    class ExpensiveStage2(FakeModelGateway):
        def complete(self, request):
            response = super().complete(request)
            if request.purpose == "skill:protocol_deviation":
                return response.model_copy(update={"usage": ModelUsage(input_tokens=10000, output_tokens=100)})
            return response

    reg = default_registry(sleep=lambda _s: None)
    clause = "必须在操作前取得书面同意。"
    gateway = ExpensiveStage2(
        {
            "answer": [{"claims": [{"text": clause, "citation_chunk_ids": ["c1"]}]}],
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "consent",
                    "rationale_statement_indices": [1],
                    "rationale": "操作前未取得同意",
                }
            ],
        }
    )
    out = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {"governing_document": "方案 A", "topic": "同意", "observation": "操作前未取得同意"},
        context=ctx(reg, gateway, FakeRetrieval(evidence("c1", clause)), {"doc-1": DocType.protocol}, dept="CO"),
    ).output
    assert out.status is SkillStatus.escalated and out.reason_codes == (ReasonCode.budget_exceeded,)
    assert [c.purpose for c in gateway.calls] == ["answer", "skill:protocol_deviation"]
