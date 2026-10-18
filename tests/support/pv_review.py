"""PUBLIC final-review fake replies. No hidden gold or production defaults."""

from medops.application.agent_final_gate import FinalGateConfig
from tests.support.pv_agent import draft, run


def final_config(**changes):
    values = dict(
        model_id="gpt-6-sol",
        max_output_tokens=128,
        timeout_s=20,
        max_review_user_bytes=2000,
        max_citation_user_bytes=500,
        max_citation_judges=1,
    )
    return FinalGateConfig(**(values | changes))


def material_verdict(current=None, draft_value=None, **changes):
    current = current or run()
    value = draft_value if draft_value is not None else draft()
    result = {
        "narrative_supported": True,
        "complete": True,
        "scope_safe": True,
        "requirements": [{"requirement_id": r.requirement_id, "complete": True} for r in current.context.requirements],
        "guideline_support": [
            {"claim_index": i, "verdict": "supported", "support_groups": [list(c["evidence_handles"])]}
            for i, c in enumerate(value["guideline_claims"])
        ],
    }
    return result | changes
