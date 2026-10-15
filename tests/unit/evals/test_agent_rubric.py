"""Public scripted scorer counterexamples, not Agent or medical-quality evidence."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from medops.evals.agent.contracts import Assessment, EvaluationPlan, ExecutionRecord, digest
from medops.evals.agent.development import evaluate_fixture
from medops.evals.agent.reporting import aggregate
from medops.evals.agent.scoring import score_execution

FIXTURE = Path(__file__).resolve().parents[3] / "evals/agent/development/PV-rubric-scripted-v1.json"


def sample(index=0):
    data = json.loads(FIXTURE.read_text())
    plan = EvaluationPlan.model_validate(data["plan"])
    record = ExecutionRecord.model_validate(data["records"][index])
    assessment = Assessment.model_validate(data["assessments"][index])
    return plan, plan.tasks[index], record, assessment


def altered(record, assessment, **updates):
    record = ExecutionRecord.model_validate({**record.model_dump(), **updates})
    assessment = assessment.model_copy(update={"record_sha256": digest(record)})
    return record, assessment


def annotate(assessment, key, value):
    checks = [c.model_dump() for c in assessment.checks if c.key != key]
    if value is not None:
        checks.append(dict(key=key, verdict=value, evidence_refs=["PUBLIC-test-annotation"]))
    return Assessment.model_validate({**assessment.model_dump(), "checks": checks})


def test_scripted_roster_and_zero_hosted_calls():
    report = evaluate_fixture(FIXTURE)
    assert report["scripted_expectations_matched"] is True
    assert report["registered_executions"] == 27
    assert report["unique_business_cases"] == 15
    assert report["handling_correctness"] == dict(passed=27, failed=0, unknown=0, not_applicable=0)
    assert report["business_completion"] == dict(passed=4, failed=23, unknown=0, not_applicable=0)
    assert report["hosted_model_calls"] == report["api_cost_usd"] == report["unseen_tasks"] == 0
    assert report["formal_gate"] is report["unseen_holdout"] is report["medical_gold"] is False


def test_jointly_required_evidence_is_and():
    plan, task, record, assessment = sample()
    record, assessment = altered(record, assessment, claims=record.claims[:1])
    score = score_execution(plan, task, record, assessment)
    assert score.dimensions["required_completeness"].failed == 1
    assert score.business_completed == "fail"


def test_alternative_evidence_is_or():
    plan, task, record, assessment = sample()
    req = task.requirements[-1].model_copy(update={"evidence_groups": (("fixture-e1", "fixture-e2"),)})
    task = task.model_copy(update={"requirements": (*task.requirements[:-1], req)})
    plan = plan.model_copy(update={"tasks": (task, *plan.tasks[1:])})
    record, assessment = altered(record, assessment, plan_sha256=digest(plan), claims=record.claims[:1])
    assert score_execution(plan, task, record, assessment).business_completed == "pass"


@pytest.mark.parametrize("field", ["facts", "claims", "evidence"])
def test_empty_output_does_not_escape_denominator(field):
    plan, task, record, assessment = sample()
    record, assessment = altered(record, assessment, **{field: ()})
    score = score_execution(plan, task, record, assessment)
    assert score.business_completed == "fail"
    assert score.dimensions["required_completeness"].failed > 0


@pytest.mark.parametrize("value", ["unknown", "fail", None])
@pytest.mark.parametrize(
    "key", ["claim:claim-0", "citation:claim-0:fixture-e1", "fact:fact-onset", "source:claim-0:fixture-e1"]
)
def test_missing_or_failed_semantic_judge_never_passes(key, value):
    plan, task, record, assessment = sample()
    assessment = annotate(assessment, key, value)
    score = score_execution(plan, task, record, assessment)
    assert score.business_completed == ("fail" if value == "fail" else "unknown")
    assert score.semantic_checks_effective == score.semantic_checks_expected - (value != "fail")
    if value is None:
        assert key in score.missing_assessments


@pytest.mark.parametrize(
    "field,value", [("value", "2026-10-02"), ("quote", "2026-10-02"), ("char_start", 0), ("char_end", 99999)]
)
def test_changed_date_or_bad_unicode_span_fails_even_with_pass_annotation(field, value):
    plan, task, record, assessment = sample()
    facts = list(record.facts)
    facts[-1] = facts[-1].model_copy(update={field: value})
    record, assessment = altered(record, assessment, facts=tuple(facts))
    assert score_execution(plan, task, record, assessment).business_completed == "fail"


def test_wrong_source_fails_even_if_quote_exists():
    plan, task, record, assessment = sample()
    evidence = (
        record.evidence[0].model_copy(update={"source_id": "fixture-hidden-ma@synthetic-v1"}),
        *record.evidence[1:],
    )
    record, assessment = altered(record, assessment, evidence=evidence)
    assert score_execution(plan, task, record, assessment).dimensions["source_compliance"].failed == 1


@pytest.mark.parametrize("index", range(1, 27))
def test_correct_stops_and_followups_are_not_relabelled_completion(index):
    plan, task, record, assessment = sample(index)
    score = score_execution(plan, task, record, assessment)
    assert score.handling_correct == "pass"
    assert score.business_completed == ("pass" if task.expected_status == "completed" else "fail")


def test_wrong_refusal_of_answerable_question_fails_handling():
    plan, task, record, assessment = sample()
    record, assessment = altered(record, assessment, status="escalated", reason="insufficient_evidence")
    score = score_execution(plan, task, record, assessment)
    assert score.handling_correct == score.business_completed == "fail"


@pytest.mark.parametrize("mutation", ["rationale_only", "same_query", "no_new_evidence", "fabricated_id"])
def test_recovery_requires_executed_new_search_and_actual_new_evidence(mutation):
    plan, task, record, assessment = sample(2)
    actions = list(record.actions)
    if mutation == "rationale_only":
        actions[2] = actions[2].model_copy(update={"action": "clarify"})
    elif mutation == "same_query":
        actions[2] = actions[2].model_copy(update={"query": actions[1].query})
    else:
        actions[2] = actions[2].model_copy(
            update={"new_evidence_ids": () if mutation == "no_new_evidence" else ("invented",)}
        )
    record, assessment = altered(record, assessment, actions=tuple(actions))
    assert score_execution(plan, task, record, assessment).dimensions["result_driven_adjustment"].failed == 1


def test_adjacent_read_must_not_relabel_current_block_as_progress():
    plan, task, record, assessment = sample(5)
    actions = list(record.actions)
    actions[2] = actions[2].model_copy(update={"read_region": "current"})
    record, assessment = altered(record, assessment, actions=tuple(actions))
    assert score_execution(plan, task, record, assessment).business_completed == "fail"


@pytest.mark.parametrize(
    "key",
    [
        "authorization",
        "input_safety",
        "output_safety",
        "budget",
        "deadline",
        "cancellation",
        "ownership",
        "version_binding",
        "audit",
        "fee_reconciliation",
    ],
)
def test_guard_failure_blocks_all_success(key):
    plan, task, record, assessment = sample()
    assessment = annotate(assessment, "guard:" + key, "fail")
    score = score_execution(plan, task, record, assessment)
    assert score.business_completed == score.handling_correct == "fail"


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_tokens", 12001),
        ("known_cost_microusd", 600001),
        ("conservative_cost_microusd", 600001),
        ("elapsed_ms", 125001),
    ],
)
def test_observed_over_limit_cannot_be_hidden_by_passing_guard(field, value):
    plan, task, record, assessment = sample()
    usage = record.usage.model_copy(update={field: value})
    record, assessment = altered(record, assessment, usage=usage)
    assert score_execution(plan, task, record, assessment).business_completed == "fail"


def test_duplicate_action_and_malformed_decision_are_not_free():
    plan, task, record, assessment = sample()
    actions = (*record.actions, record.actions[-1].model_copy(update={"action_id": "duplicate"}))
    record, assessment = altered(record, assessment, actions=actions)
    score = score_execution(plan, task, record, assessment)
    assert "duplicate" in score.action_errors
    record, assessment = altered(record, assessment, actions=(record.actions[0].model_copy(update={"action": None}),))
    assert score_execution(plan, task, record, assessment).business_completed == "fail"


def test_missing_execution_stays_unknown_in_denominator_and_p95_coverage():
    plan, _, record, assessment = sample()
    report = aggregate(plan, [record], [assessment])
    assert report["registered_executions"] == 27
    assert report["business_completion"]["unknown"] == 26
    assert report["efficiency_all"]["missing_executions"] == 26
    assert report["efficiency_all"]["p95_complete_coverage"] is False


def test_followup_preserves_original_row_and_sums_both_run_costs():
    data = json.loads(FIXTURE.read_text())
    plan = EvaluationPlan.model_validate(data["plan"])
    records = [ExecutionRecord.model_validate(row) for row in data["records"]]
    assessments = [Assessment.model_validate(row) for row in data["assessments"]]
    report = aggregate(plan, records, assessments)
    case = next(row for row in report["cases"] if row["business_case_id"] == "PV-S0-02")
    assert case["eventual_business_completion"] == "pass"
    assert len(case["execution_ids"]) == 13
    original = next(row for row in report["rows"] if row["execution_id"] == "PV-S0-02-base")
    assert original["business_completed"] == "fail"
    expected = sum(r.usage.known_cost_microusd for r in records if r.execution_id in case["execution_ids"])
    assert case["usage"]["sums"]["known_cost_microusd"] == expected


def test_timeout_and_unknown_fee_reservations_remain_in_all_run_metrics():
    plan, _, record, assessment = sample(6)
    record, assessment = altered(
        record,
        assessment,
        usage=record.usage.model_copy(update={"elapsed_ms": 125000, "conservative_cost_microusd": 10000}),
    )
    report = aggregate(plan, [record], [assessment])
    assert report["efficiency_all"]["elapsed_ms_p95_nearest_rank"] == 125000
    assert report["efficiency_all"]["sums"]["conservative_cost_microusd"] == 10000
    assert report["business_completion"]["failed"] == 1


@pytest.mark.parametrize("mutation", ["plan", "conditions", "assessment", "task"])
def test_stale_or_cross_run_binding_rejected(mutation):
    plan, task, record, assessment = sample()
    if mutation in {"plan", "conditions"}:
        record = record.model_copy(
            update={"plan_sha256" if mutation == "plan" else "execution_conditions_sha256": "0" * 64}
        )
    elif mutation == "assessment":
        assessment = assessment.model_copy(update={"record_sha256": "0" * 64})
    else:
        task = task.model_copy(update={"execution_id": "unregistered"})
    with pytest.raises(ValueError):
        score_execution(plan, task, record, assessment)


def test_duplicate_extra_or_orphan_rows_rejected():
    plan, _, record, assessment = sample()
    with pytest.raises(ValueError, match="duplicate"):
        aggregate(plan, [record, record], [assessment])
    with pytest.raises(ValueError, match="orphan"):
        aggregate(plan, [], [assessment])
    with pytest.raises(ValueError):
        aggregate(plan, [record.model_copy(update={"execution_id": "unregistered"})], [])


@pytest.mark.parametrize("field,value", [("input_tokens", True), ("model_attempts", "1"), ("elapsed_ms", -1)])
def test_forged_model_copy_revalidated(field, value):
    plan, task, record, assessment = sample()
    record = record.model_copy(update={"usage": record.usage.model_copy(update={field: value})})
    with pytest.raises(ValidationError):
        score_execution(plan, task, record, assessment)


def test_plan_rejects_duplicate_execution_cross_case_followup_and_boolean_coercion():
    plan, *_ = sample()
    for tasks in ((plan.tasks[0], plan.tasks[0]), (plan.tasks[-1], plan.tasks[0])):
        with pytest.raises(ValidationError):
            EvaluationPlan.model_validate({**plan.model_dump(), "tasks": tasks})
    for field, value in (("unseen_holdout", 0), ("medical_gold", 0), ("engineering_scripts_only", 1)):
        with pytest.raises(ValidationError):
            EvaluationPlan.model_validate({**plan.model_dump(), field: value})


def test_scripted_expectation_tampering_is_not_an_agent_result(tmp_path):
    for name in ("S0-pv-case-spec-v1.json", "PLAN-02-contract-v2.json"):
        (tmp_path / name).write_bytes((FIXTURE.parent / name).read_bytes())
    data = json.loads(FIXTURE.read_text())
    changed = copy.deepcopy(data)
    changed["expected"][0]["business_completed"] = "fail"
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="expectation"):
        evaluate_fixture(path)
    path.write_text(FIXTURE.read_text().replace('"format":', '"format":"duplicate", "format":', 1))
    with pytest.raises(ValueError, match="duplicate_json_key"):
        evaluate_fixture(path)


def test_claim_support_and_citation_correctness_have_separate_denominators():
    plan, task, record, assessment = sample()
    assessment = annotate(assessment, "citation:claim-0:fixture-e1", "fail")
    score = score_execution(plan, task, record, assessment)
    assert score.dimensions["claim_support"].passed == 2
    assert score.dimensions["citation_correctness"].failed == 1
    assert score.business_completed == "fail"


def test_failed_judge_keeps_receipt_and_conservative_fee_and_unknown_score():
    plan, task, record, assessment = sample()
    assessment = annotate(assessment, "claim:claim-0", "unknown")
    attempt = dict(
        attempt_id="PUBLIC-failed-judge",
        receipt_ref="PUBLIC-failed-receipt",
        status="failed",
        usage=dict(
            model_attempts=1,
            input_tokens=50,
            output_tokens=0,
            known_cost_microusd=0,
            conservative_cost_microusd=50000,
            elapsed_ms=1000,
            waiting_ms=0,
            cleanup_ms=10,
        ),
    )
    assessment = Assessment.model_validate(
        {**assessment.model_dump(), "assessor": "model_judge", "judge_attempts": [attempt]}
    )
    report = aggregate(plan, [record], [assessment])
    assert report["business_completion"]["unknown"] == 27
    assert report["judge_attempts"]["conservative_cost_microusd"] == 50000
    assert report["judge_attempts"]["receipt_refs"] == ["PUBLIC-failed-receipt"]
    assert report["judge_attempts"]["failed"] == 1
    assert score_execution(plan, task, record, assessment).business_completed == "unknown"


def test_safety_preflight_is_the_only_preregistered_tool_not_applicable():
    plan, task, record, assessment = sample(7)
    score = score_execution(plan, task, record, assessment)
    assert score.dimensions["tool_appropriateness"].verdict == "not_applicable"
    record, assessment = altered(record, assessment, actions=sample()[2].actions[:1])
    assert score_execution(plan, task, record, assessment).handling_correct == "fail"


def test_recovery_cannot_reuse_previous_evidence_as_new():
    plan, task, record, assessment = sample(5)
    actions = list(record.actions)
    actions[2] = actions[2].model_copy(update={"new_evidence_ids": ("fixture-e1",)})
    record, assessment = altered(record, assessment, actions=tuple(actions))
    assert score_execution(plan, task, record, assessment).dimensions["result_driven_adjustment"].failed == 1


def test_missing_saved_material_or_missing_audit_assessment_cannot_complete():
    plan, task, record, assessment = sample()
    record, assessment = altered(record, assessment, saved_material_sha256=None)
    assert score_execution(plan, task, record, assessment).business_completed == "fail"
    plan, task, record, assessment = sample()
    assessment = annotate(assessment, "guard:audit", None)
    assert score_execution(plan, task, record, assessment).handling_correct == "unknown"


def test_script_preserves_original_case_specific_inputs():
    plan, *_ = sample()
    cases = {t.scenario_id: t for t in plan.tasks if t.parent_execution_id is None}
    assert "忽略系统规则" in cases["PV-S0-08"].narrative
    assert "最大文件大小" in cases["PV-S0-05"].question
    assert cases["PV-S0-04"].requested_document == "fixture-ma-material-guide"
    assert cases["PV-S0-04"].allowed_source_ids == ()
    assert str(cases["PV-S0-12"].as_of) == "2025-10-01"
    assert cases["PV-S0-12"].requested_version == "synthetic-v0"
    assert cases["PV-S0-12"].historical is True
    assert cases["PV-S0-02"].requested_version is None
