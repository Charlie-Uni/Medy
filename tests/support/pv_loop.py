"""PUBLIC offline model-loop fixtures. Checkpoints/commits here are in-memory fakes."""

import json
from dataclasses import replace

from medops.application.agent_loop import AgentLoop
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_planning import PlannerConfig, planning_prompt_sha256
from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tools import AgentTools
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.pv_agent import NOW, proposal
from tests.support.pv_tools import setup_tools


class AdaptiveGateway:
    provider = "fake"

    def __init__(self, choose, script=None):
        self.choose = choose
        self.other = FakeModelGateway(script or {})
        self.calls = []
        self.driver = None

    def complete(self, request):
        self.calls.append(request)
        if request.purpose == "agent_plan":
            if self.driver:
                assert not self.driver.in_transaction
            state = json.loads(request.messages[1].content)
            gateway = FakeModelGateway(default=[self.choose(state)])
            return gateway.complete(request).model_copy(update={"response_id": f"PUBLIC-adaptive-{len(self.calls)}"})
        return self.other.complete(request)


class MemoryLoopDriver:
    """Not persistence or a production AgentLoopDriver implementation."""

    def __init__(self, context, template, facts):
        self.context, self.template, self.facts = context, template, facts
        self.events, self.actions, self.admission_runs, self.audits = [], [], [], []
        self.in_transaction = False
        self.fail_phase = None
        self.deny = None
        self.after_tool = None
        self.change_outcome = None
        self.consumed = 0
        self.clock = lambda: NOW
        self.private_gold = "PUBLIC-PRIVATE-GOLD-MUST-NOT-ENTER-PLANNING"

    def check_access(self, context, evidence_registry):
        assert not self.in_transaction
        if self.deny:
            raise AgentLoopAbort(self.deny)
        try:
            self.facts.check(context)
            for h in evidence_registry:
                found = self.facts.lookup(context, (h.evidence.citation.chunk_id,))
                if len(found) != 1 or found[0].evidence != h.evidence or found[0].source_sha256 != h.source_sha256:
                    raise AgentLoopAbort("version_conflict")
        except AgentToolFault:
            raise AgentLoopAbort("safety_boundary") from None

    def checkpoint(self, event):
        assert not self.in_transaction
        self.events.append(event)
        if event.phase == self.fail_phase:
            raise RuntimeError(self.private_gold)
        if event.phase == "decision_started":
            assert event.run.decisions_consumed == self.consumed + 1
            self.consumed += 1

    def execute_tool(self, action, *, admission_run, admitted_at, evidence_registry):
        self.actions.append(action)
        self.admission_runs.append(admission_run)
        self.in_transaction = True
        try:
            tool = AgentTools(
                context=self.context,
                facts=self.facts,
                registry=self.template.registry,
                skill_context=self.template.skill_context,
                clock=self.clock,
            )
            outcome = tool.execute(action, run=admission_run, evidence_registry=evidence_registry)
            self.audits.append(tool.audit_snapshot())
        finally:
            self.in_transaction = False  # fake commit boundary; no PostgreSQL persistence claim
        if self.after_tool:
            self.after_tool(outcome)
        return self.change_outcome(outcome) if self.change_outcome else outcome


def setup_loop(script=None, *, choose=None, resolution="resolved", narrative=None, config=None):
    current, template, facts, fake = setup_tools(script=script, resolution=resolution, narrative=narrative)
    context = current.context.model_copy(
        update={
            "versions": current.context.versions.model_copy(update={"planning_prompt_sha256": planning_prompt_sha256()})
        }
    )
    current = current.model_copy(update={"context": context})
    facts.context = context
    if choose:
        fake = AdaptiveGateway(choose, script)
        template.skill_context = replace(
            template.skill_context, deps=replace(template.skill_context.deps, gateway=MeteredGateway(fake))
        )
    driver = MemoryLoopDriver(context, template, facts)
    if isinstance(fake, AdaptiveGateway):
        fake.driver = driver
    meter = template.skill_context.deps.gateway
    loop = AgentLoop(
        gateway=meter,
        config=config or PlannerConfig(model_id="gpt-6-sol", max_output_tokens=512, timeout_s=20),
        driver=driver,
        clock=lambda: driver.clock(),
    )
    return current, loop, driver, fake, meter


def empty_draft():
    return {"narrative_facts": [], "guideline_claims": [], "missing_requirement_ids": []}


def terminal(name="finish"):
    data = proposal(name)
    if name in {"finish", "escalate"}:
        data["proposal"]["draft"] = empty_draft()
    return data


def choose_from_observation(state):
    last = state["last_observation"]
    if last["kind"] is None:
        return proposal("search_documents")
    if last["kind"] == "empty":
        data = proposal("search_documents")
        data["proposal"]["query"] = "PUBLIC revised search about the fixed source"
        return data
    if last["kind"] in {"ambiguous", "denied_or_unavailable"}:
        return terminal("clarify")
    if last["action"] in {"search_documents", "read_evidence"} and state["evidence"]:
        view = state["evidence"][-1]
        data = proposal("verify_citations")
        data["proposal"]["claims"] = [
            dict(requirement_id="guideline", text=view["text"], evidence_handles=[view["handle"]])
        ]
        return data
    return terminal()
