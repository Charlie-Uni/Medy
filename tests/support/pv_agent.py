"""Public synthetic PV contract fixtures, not unseen tasks or a business benchmark."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from medops.application.agent_contracts import context_binding
from medops.domain.agent_execution import (
    AgentBudget,
    AgentContext,
    AgentIdentity,
    AgentProfile,
    AgentRequirement,
    AgentSourceScope,
    AgentVersions,
    AllowedSource,
    EvidenceHandle,
    PVAgentRun,
    TerminalRecord,
)
from medops.domain.common import Dept
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.domain.state import VersionSet

NOW = datetime(2026, 10, 15, tzinfo=UTC)
NARRATIVE = "PUBLIC SYNTHETIC narrative: patient reported an event."
CANARY = "PUBLIC-SYNTHETIC-PRIVATE-CONTENT"
DIGEST = "a" * 64


def uid(value):
    return UUID(int=value)


def run():
    context = AgentContext(
        identity=AgentIdentity(case_id=uid(1), task_id=uid(2), run_id=uid(3), attempt_id=uid(4), trace_id="1" * 32),
        principal=UserContext(user_id="PUBLIC-user", dept=Dept.PV, acl_scopes=frozenset({"PV:read"})),
        query_context=QueryContext(as_of=date(2026, 10, 15)),
        narrative=NARRATIVE,
        synthetic=True,
        source_type="other",
        source_scope=AgentSourceScope(
            requested_document="PUBLIC guideline",
            requested_version="PUBLIC v1",
            resolution="resolved",
            allowed_sources=(AllowedSource(doc_id="PUBLIC-doc", version="PUBLIC v1", source_sha256=DIGEST),),
        ),
        requirements=(
            AgentRequirement(requirement_id="event", description="PUBLIC narrative event", kind="narrative"),
            AgentRequirement(requirement_id="guideline", description="PUBLIC guideline rule", kind="guideline"),
        ),
        clarifiable_fields=("source_version",),
        versions=AgentVersions(
            versions=VersionSet(
                policy_version="PUBLIC-p1", retrieval_version="PUBLIC-r1", model_config_version="PUBLIC-m1"
            ),
            planning_prompt_sha256=DIGEST,
            tool_contract_sha256=DIGEST,
            verification_policy_sha256=DIGEST,
            rubric_sha256=DIGEST,
            fact_database_id=uid(5),
            fact_conditions_sha256=DIGEST,
        ),
        profile=AgentProfile(final_reserve_tokens=1000, final_reserve_cost_microusd=50000),
    )
    return PVAgentRun(
        context=context,
        status="running",
        decisions_consumed=0,
        budget=AgentBudget(accounted_tokens=0, reserved_tokens=0, accounted_cost_microusd=0, reserved_cost_microusd=0),
        started_at=NOW,
        expires_at=NOW + timedelta(seconds=125),
    )


def handle(current, number=10):
    text = "PUBLIC SYNTHETIC evidence."
    return EvidenceHandle(
        handle=uid(number),
        binding=context_binding(current.context),
        source_sha256=DIGEST,
        expires_at=current.expires_at,
        evidence=Evidence(
            citation=Citation(
                doc_id="PUBLIC-doc",
                version="PUBLIC v1",
                effective_date=date(2026, 1, 1),
                page=1,
                section="PUBLIC",
                chunk_id="PUBLIC-chunk",
            ),
            text=text,
            evidence_text_hash=hashlib.sha256(text.encode()).hexdigest(),
            chunk_content_hash=DIGEST,
            status="active",
        ),
    )


def draft(current=None):
    return dict(
        narrative_facts=[dict(requirement_id="event", value="PUBLIC", quote="PUBLIC", char_start=0, char_end=6)],
        guideline_claims=[
            dict(requirement_id="guideline", text="PUBLIC supported rule", evidence_handles=[str(uid(10))])
        ],
        missing_requirement_ids=[],
    )


def proposal(name="search_documents"):
    value = {"action": name, "rationale": "PUBLIC purpose"}
    if name == "extract_ae":
        value.update(narrative_ref="task_narrative", source_type="other")
    elif name == "search_documents":
        value.update(query="PUBLIC query")
    elif name == "read_evidence":
        value.update(handle=str(uid(10)), region="current")
    elif name == "verify_citations":
        value.update(claims=draft()["guideline_claims"])
    elif name == "clarify":
        value.update(
            questions=[dict(field="source_version", question="PUBLIC version?", reason="PUBLIC missing version")]
        )
    elif name == "finish":
        value.update(draft=draft())
    elif name == "escalate":
        value.update(reason="insufficient_evidence", draft=draft())
    return {"proposal": value}


def wire(value):
    return json.dumps(value, ensure_ascii=False)


def stopped(current, status="completed", reason="completed"):
    record = TerminalRecord(
        binding=context_binding(current.context),
        status=status,
        reason=reason,
        material_ref=uid(21),
        material_sha256=DIGEST,
        audit_ref=uid(22),
        verification_ref=uid(23) if status == "completed" else None,
    )
    return current.model_copy(update=dict(status=status, stopped_at=NOW + timedelta(seconds=1), terminal=record))
