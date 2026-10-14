"""Already exposed synthetic method examples; not a formal holdout protocol."""

from medops.evals.isolation.contracts import PrivateInventory, RuntimeInput
from medops.evals.isolation.history import HistoryPlan, HistoryReceipt, HistoryRequirement, history_plan_digest
from medops.evals.isolation.manifests import inventory_item
from medops.evals.isolation.screening import ScreeningPolicy, screening_digest
from tests.support.eval_isolation import case, uid


def collection(value, *queries):
    cases = tuple(case(value * 100 + i, query=query) for i, query in enumerate(queries, 1))
    return PrivateInventory(
        collection_id=uid(value),
        split="development" if value == 1 else "holdout",
        items=tuple(inventory_item(item, family_ids=(uid(1000 + item.item_id.int),)) for item in cases),
    ), tuple(RuntimeInput(item_id=item.item_id, query=item.query) for item in cases)


def policy(**changes):
    return ScreeningPolicy(
        method_id=uid(500),
        width=3,
        min_normalized_chars=12,
        threshold_numerator=4,
        threshold_denominator=5,
        max_items_per_collection=1000,
        max_comparisons=250000,
        max_total_query_chars=1000000,
    ).model_copy(update=changes)


def inputs(left_queries=("public synthetic question A?",), right_queries=("public synthetic question A!",), **changes):
    left, lhs = collection(1, *left_queries)
    right, rhs = collection(2, *right_queries)
    method = policy(**changes)
    return dict(
        left=left,
        left_inputs=lhs,
        right=right,
        right_inputs=rhs,
        policy=method,
        expected_method_sha256=screening_digest(method),
    )


def history():
    plan = HistoryPlan(
        scope_id=uid(900),
        requirements=(
            HistoryRequirement(
                artifact_id=uid(1), artifact_sha256="a" * 64, adapter="dataset-fields-v1", required_levels=("query",)
            ),
            HistoryRequirement(
                artifact_id=uid(2),
                artifact_sha256="b" * 64,
                adapter="retrieval-fields-v1",
                required_levels=("query", "source"),
            ),
        ),
    )
    digest = history_plan_digest(plan)
    receipts = tuple(
        HistoryReceipt(
            artifact_id=item.artifact_id,
            plan_sha256=digest,
            adapter=item.adapter,
            artifact_sha256=item.artifact_sha256,
            state="checked",
            checked_levels=item.required_levels,
            record_count=1,
        )
        for item in plan.requirements
    )
    return plan, receipts, digest
