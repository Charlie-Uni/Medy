"""Complete-roster aggregation. Cancelled/missing/follow-up runs never disappear."""

from __future__ import annotations

import math
from collections.abc import Sequence

from medops.evals.agent.contracts import Assessment, EvaluationPlan, ExecutionRecord, Usage, revalidate
from medops.evals.agent.scoring import ExecutionScore, conjunction, score_execution, tally


def _usage(records: Sequence[ExecutionRecord], registered: int) -> dict[str, object]:
    fields = tuple(Usage.model_fields)
    rows = [r.usage for r in records]
    elapsed = sorted(u.elapsed_ms for u in rows)
    return {
        "registered_executions": registered,
        "measured_executions": len(rows),
        "missing_executions": registered - len(rows),
        "sums": {field: sum(getattr(u, field) for u in rows) for field in fields if field != "elapsed_ms"},
        "elapsed_ms_sum": sum(elapsed),
        "elapsed_ms_p95_nearest_rank": elapsed[math.ceil(len(elapsed) * 0.95) - 1] if elapsed else None,
        "decision_steps_sum": sum(len(r.actions) for r in records),
        "p95_complete_coverage": len(rows) == registered,
        "timeout_and_failure_rows_retained": True,
    }


def aggregate(
    plan: EvaluationPlan,
    records: Sequence[ExecutionRecord],
    assessments: Sequence[Assessment],
) -> dict[str, object]:
    plan = revalidate(plan)
    records = tuple(revalidate(r) for r in records)
    assessments = tuple(revalidate(a) for a in assessments)
    observed = {r.execution_id: r for r in records}
    judged = {a.execution_id: a for a in assessments}
    attempts = [j.attempt_id for a in assessments for j in a.judge_attempts]
    receipts = [j.receipt_ref for a in assessments for j in a.judge_attempts]
    if len(attempts) != len(set(attempts)) or len(receipts) != len(set(receipts)):
        raise ValueError("duplicate_judge_attempt_or_receipt")
    registered = {t.execution_id for t in plan.tasks}
    if len(observed) != len(records) or len(judged) != len(assessments):
        raise ValueError("duplicate_execution_or_assessment")
    if not set(observed) <= registered or not set(judged) <= set(observed):
        raise ValueError("unregistered_or_orphan_record")
    scores = tuple(
        score_execution(plan, t, observed.get(t.execution_id), judged.get(t.execution_id)) for t in plan.tasks
    )
    cases: dict[str, list[ExecutionScore]] = {}
    for score in scores:
        cases.setdefault(score.business_case_id, []).append(score)
    case_rows = []
    for case_id, entries in cases.items():
        result = (
            "pass"
            if any(s.business_completed == "pass" for s in entries)
            else ("unknown" if any(s.business_completed == "unknown" for s in entries) else "fail")
        )
        own_records = [observed[s.execution_id] for s in entries if s.execution_id in observed]
        case_rows.append(
            {
                "business_case_id": case_id,
                "execution_ids": [s.execution_id for s in entries],
                "eventual_business_completion": result,
                "all_executions_handled_correctly": conjunction(s.handling_correct for s in entries),
                "usage": _usage(own_records, len(entries)),
            }
        )
    expected_completable = [s for t, s in zip(plan.tasks, scores, strict=True) if t.expected_status == "completed"]
    dimensions = {}
    for name in scores[0].dimensions:
        dimensions[name] = {
            "task_verdicts": tally(s.dimensions[name].verdict for s in scores).model_dump(),
            "item_counts": {
                key: sum(getattr(s.dimensions[name], key) for s in scores)
                for key in ("passed", "failed", "unknown", "not_applicable")
            },
        }
    return {
        "format": "pv-agent-rubric-report-v1",
        "rubric_version": plan.rubric_version,
        "usage": plan.usage,
        "unseen_holdout": False,
        "medical_gold": False,
        "engineering_scripts_only": True,
        "formal_gate": False,
        "registered_executions": len(plan.tasks),
        "unique_business_cases": len(cases),
        "unseen_tasks": 0,
        "missing_executions": len(plan.tasks) - len(observed),
        "business_completion": tally(s.business_completed for s in scores).model_dump(),
        "handling_correctness": tally(s.handling_correct for s in scores).model_dump(),
        "expected_completable": tally(s.business_completed for s in expected_completable).model_dump(),
        "dimensions": dimensions,
        "cases": case_rows,
        "semantic_assessment_coverage": {
            "expected": sum(s.semantic_checks_expected for s in scores),
            "effective": sum(s.semantic_checks_effective for s in scores),
            "missing_records": len(plan.tasks) - len(observed),
        },
        "efficiency_all": _usage(records, len(plan.tasks)),
        "judge_attempts": {
            "count": sum(len(a.judge_attempts) for a in assessments),
            "failed": sum(j.status != "completed" for a in assessments for j in a.judge_attempts),
            "known_cost_microusd": sum(j.usage.known_cost_microusd for a in assessments for j in a.judge_attempts),
            "conservative_cost_microusd": sum(
                j.usage.conservative_cost_microusd for a in assessments for j in a.judge_attempts
            ),
            "input_tokens": sum(j.usage.input_tokens for a in assessments for j in a.judge_attempts),
            "output_tokens": sum(j.usage.output_tokens for a in assessments for j in a.judge_attempts),
            "receipt_refs": [j.receipt_ref for a in assessments for j in a.judge_attempts],
        },
        "efficiency_by_terminal": {
            status: _usage(
                [r for r in records if r.status == status],
                sum(
                    observed.get(t.execution_id) is not None and observed[t.execution_id].status == status
                    for t in plan.tasks
                ),
            )
            for status in ("running", "completed", "awaiting_clarification", "escalated", "failed", "cancelled")
        },
        "rows": [s.model_dump(mode="json") for s in scores],
    }
