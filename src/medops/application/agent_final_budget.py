"""Private citation-check handoff for the trusted final owner, not a completed task.

The result covers the final draft's citation requests and their budget only.
The terminal owner establishes completeness, narrative/business/safety validity
and persists the business result under its final fact fence. This DTO alone cannot complete a run.
"""

from dataclasses import dataclass
from uuid import UUID

from medops.application.agent_final_gate import FinalMaterialCheck
from medops.application.agent_tool_results import VerificationPayload
from medops.domain.agent_execution import AgentBinding
from medops.infrastructure.llm.execution_budget import BudgetSnapshot, FinalizationProfile

FINAL_CITATION_BUDGET_VERSION = "pv-final-citation-budget-v1"


@dataclass(frozen=True)
class FinalCitationBudgetResult:
    action_id: UUID
    binding: AgentBinding
    draft_sha256: str
    payload: VerificationPayload | None
    profile: FinalizationProfile
    budget: BudgetSnapshot
    call_receipt_ids: tuple[str, ...]
    material_check: FinalMaterialCheck | None = None
