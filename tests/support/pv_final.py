"""Shared PUBLIC final-gate fixtures; no collected tests or hosted calls."""

from medops.application.agent_contracts import admit_action
from medops.domain.agent_execution import AgentProfile
from tests.support.pv_agent import NOW, handle, proposal, uid, wire
from tests.support.pv_tools import setup_tools


def setup_final(*, script=None, judge="gpt-6-sol", literal=False, reserve=6000, prior_steps=0, empty=False):
    profile = AgentProfile(final_reserve_tokens=reserve, final_reserve_cost_microusd=50000)
    current, tool, facts, fake = setup_tools(
        judge=judge,
        profile=profile,
        script=script or {"verify": [{"verdict": "supported", "reason": "PUBLIC grounded"}]},
    )
    record = handle(current)
    body = proposal("finish")
    if literal:
        body["proposal"]["draft"]["guideline_claims"][0]["text"] = record.evidence.text
    if empty:
        body["proposal"]["draft"]["guideline_claims"] = []
    prior = current.model_copy(update={"decisions_consumed": prior_steps})
    bound = admit_action(wire(body), run=prior, action_id=uid(300), evidence_registry=(record,), now=NOW)
    current = prior.model_copy(update={"decisions_consumed": prior_steps + 1})
    return current, tool, facts, fake, bound, record
