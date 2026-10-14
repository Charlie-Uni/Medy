"""Public synthetic checks for private query triage and historical scan receipts."""

from __future__ import annotations

from uuid import UUID

from medops.evals.isolation.canary import _refused
from medops.evals.isolation.contracts import IsolationError, PrivateCase, PrivateInventory, RuntimeInput
from medops.evals.isolation.history import (
    HistoryPlan,
    HistoryReceipt,
    HistoryRequirement,
    check_history_coverage,
    history_plan_digest,
)
from medops.evals.isolation.manifests import inventory_item
from medops.evals.isolation.screening import ScreeningPolicy, screen_queries, screening_digest


def screening_self_check() -> dict[str, object]:
    """No arbitrary input paths, real history, sealed tasks, service or model calls."""
    cases = tuple(
        PrivateCase(item_id=UUID(int=i), query=query, gold="PUBLIC SYNTHETIC GOLD")
        for i, query in enumerate(("public synthetic question A?", "public synthetic question A!"), 1)
    )
    inventories = tuple(
        PrivateInventory(
            collection_id=UUID(int=100 + i),
            split="development" if i == 0 else "holdout",
            items=(inventory_item(case, family_ids=(UUID(int=200 + i),)),),
        )
        for i, case in enumerate(cases)
    )
    policy = ScreeningPolicy(
        method_id=UUID(int=300),
        width=3,
        min_normalized_chars=12,
        threshold_numerator=4,
        threshold_denominator=5,
        max_items_per_collection=1000,
        max_comparisons=250000,
        max_total_query_chars=1000000,
    )

    def screen(method: ScreeningPolicy = policy):
        return screen_queries(
            left=inventories[0],
            left_inputs=(RuntimeInput(item_id=cases[0].item_id, query=cases[0].query),),
            right=inventories[1],
            right_inputs=(RuntimeInput(item_id=cases[1].item_id, query=cases[1].query),),
            policy=method,
            expected_method_sha256=screening_digest(policy),
        )

    result = screen()
    requirement = HistoryRequirement(
        artifact_id=UUID(int=400), artifact_sha256="a" * 64, adapter="dataset-fields-v1", required_levels=("query",)
    )
    plan = HistoryPlan(scope_id=UUID(int=500), requirements=(requirement,))
    digest = history_plan_digest(plan)
    receipt = HistoryReceipt(
        artifact_id=requirement.artifact_id,
        plan_sha256=digest,
        adapter=requirement.adapter,
        artifact_sha256=requirement.artifact_sha256,
        state="checked",
        checked_levels=("query",),
        record_count=0,
    )
    complete = check_history_coverage(plan, (receipt,), expected_plan_sha256=digest)
    missing = check_history_coverage(plan, (), expected_plan_sha256=digest)
    checks = {
        "near_query_requires_review": len(result.matches) == 1
        and result.matches[0].reason == "query_near"
        and result.matches[0].disposition == "review_required",
        "private_report_no_body": all(
            case.query not in result.model_dump_json() and case.gold not in result.model_dump_json() for case in cases
        ),
        "changed_method_denied": _refused(
            lambda: screen(policy.model_copy(update={"threshold_numerator": 3})), "binding_mismatch"
        ),
        "missing_history_remains_incomplete": missing.declared_scope_status == "incomplete"
        and missing.checked_artifacts == 0,
        "complete_declared_scope_not_unseen": complete.declared_scope_status == "complete"
        and complete.qualification == "unknown"
        and not complete.historical_scope_exhaustive_verified,
        "changed_history_artifact_denied": _refused(
            lambda: check_history_coverage(
                plan, (receipt.model_copy(update={"artifact_sha256": "f" * 64}),), expected_plan_sha256=digest
            ),
            "binding_mismatch",
        ),
    }
    if not all(checks.values()):
        raise IsolationError("invalid_payload")
    return {
        "format": "eval-screening-canary-v1",
        "checks": checks,
        "model_calls": 0,
        "qualification": "unknown",
        "deployment_isolation_verified": False,
        "independent_human_review_verified": False,
    }
