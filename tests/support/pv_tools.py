"""Public synthetic Agent adapter setup; never a blind benchmark or real patient data."""

from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentFact
from medops.application.agent_tools import AgentTools, tool_contract_sha256
from medops.domain.agent_execution import AgentSourceScope, AllowedSource
from medops.infrastructure.llm.execution_budget import ExecutionLimits, execution_scope
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillContext
from tests.support.harness import FakeRetrieval, make_deps
from tests.support.pv_agent import DIGEST, NOW, handle, run


class FakeAgentFacts:
    def __init__(self, context, *items):
        self.context = context
        self.items = {e.citation.chunk_id: AgentFact(evidence=e, source_sha256=DIGEST) for e in items}
        self.final_calls = []
        self.deny_final = False
        self.adjacent = {}

    def check(self, context):
        if context != self.context:
            raise AgentToolFault("denied_or_unavailable")

    def sources(self, context):
        self.check(context)
        if context.source_scope.resolution != "resolved":
            raise AgentToolFault(
                "ambiguous" if context.source_scope.resolution == "ambiguous" else "denied_or_unavailable"
            )

    def lookup(self, context, ids):
        self.sources(context)
        allowed = {(s.doc_id, s.version, s.source_sha256) for s in context.source_scope.allowed_sources}
        if any(i not in self.items for i in ids):
            raise AgentToolFault("denied_or_unavailable")
        result = tuple(self.items[i] for i in ids)
        if any(
            (f.evidence.citation.doc_id, f.evidence.citation.version, f.source_sha256) not in allowed for f in result
        ):
            raise AgentToolFault("denied_or_unavailable")
        return result

    def read(self, context, evidence, region):
        if region == "current":
            return self.lookup(context, (evidence.citation.chunk_id,))[0]
        neighbor = self.adjacent.get((evidence.citation.chunk_id, region))
        return self.lookup(context, (neighbor,))[0] if neighbor else None

    def final_check(self, context, facts, *, check_sources=True):
        self.final_calls.append((context, facts, check_sources))
        if self.deny_final:
            raise AgentToolFault("denied_or_unavailable")
        if facts and facts != self.lookup(context, tuple(f.evidence.citation.chunk_id for f in facts)):
            raise AgentToolFault("denied_or_unavailable")


def setup_tools(*, script=None, narrative=None, items=None, resolution="resolved", judge=None):
    registry = default_registry(sleep=lambda _: None, clock=lambda: NOW)
    current = run()
    context = current.context
    if narrative is not None:
        context = context.model_copy(update={"narrative": narrative})
    versions = context.versions.model_copy(
        update={
            "versions": context.versions.versions.model_copy(update={"skill_version_set": registry.version_set()}),
            "tool_contract_sha256": tool_contract_sha256(),
        }
    )
    scope = AgentSourceScope(
        requested_document="PUBLIC guideline",
        requested_version="PUBLIC v1",
        resolution=resolution,
        allowed_sources=(AllowedSource(doc_id="PUBLIC-doc", version="PUBLIC v1", source_sha256=DIGEST),)
        if resolution == "resolved"
        else (),
    )
    context = context.model_copy(update={"versions": versions, "source_scope": scope})
    current = current.model_copy(update={"context": context})
    items = tuple(items) if items is not None else (handle(current).evidence,)
    gateway = FakeModelGateway(script or {})
    meter = MeteredGateway(gateway)
    retrieval = FakeRetrieval(*items)
    deps = make_deps(
        retrieval, meter, judge_model_id=judge, as_of=context.query_context.as_of, query_context=context.query_context
    )
    skill = SkillContext(
        user=context.principal,
        versions=versions.versions,
        deps=deps,
        evidence_lookup=lambda _u, _ids: (),
        doc_type_lookup=lambda _u, _ids: {},
        trace_id=context.identity.trace_id,
        run_id=str(context.identity.run_id),
        as_of=context.query_context.as_of,
    )
    facts = FakeAgentFacts(context, *items)
    tool = AgentTools(context=context, facts=facts, registry=registry, skill_context=skill, clock=lambda: NOW)
    return current, tool, facts, gateway


def parent(**changes):
    values = dict(token_limit=12000, cost_limit_usd=0.6, timeout_s=125)
    values.update(changes)
    return execution_scope(ExecutionLimits(**values))
