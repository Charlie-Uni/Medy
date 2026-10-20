"""PUBLIC S0 inputs through the durable Agent, not a hosted-model benchmark.

The reactive fake sees only real planner projections. Expectations/private S0
environment stay in the fixture builder; UUIDs and PUBLIC v1 bind physical facts.
"""

import json
from dataclasses import replace
from pathlib import Path

import psycopg

from medops.domain.query import QueryContext
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.agent_runtime import reopen_case, runtime_case
from tests.support.agent_terminal import stop_verdict
from tests.support.harness import FakeRetrieval
from tests.support.pv_review import final_config

S0 = Path(__file__).resolve().parents[2] / "evals/agent/development/S0-pv-case-spec-v1.json"


class PublicS0Gateway:
    """Deterministic fault-injection double; never evidence of model competence."""

    provider = "fake"

    def __init__(self, defect=None, *, extract=False):
        self.calls = []
        self.boards = []
        self.defect = defect
        self.extract = extract

    def complete(self, request):
        self.calls.append(request)
        if request.purpose == "skill:ae_extraction":
            reply = {
                "elements": [
                    dict(kind=k, value=v, quote=v)
                    for k, v in (
                        ("patient", "一名成年人"),
                        ("suspect_drug", "合成药品A"),
                        ("event", "皮疹"),
                        ("onset", "2026-10-01"),
                    )
                ]
            }
        elif request.purpose == "agent_plan":
            board = json.loads(request.messages[1].content)
            self.boards.append(board)
            reply = {"proposal": self.choose(board)}
        elif request.purpose == "verify":
            reply = {"verdict": "supported", "reason": "PUBLIC controlled positive verifier"}
        elif request.purpose == "agent_final_material":
            data = json.loads(request.messages[1].content)
            reply = dict(
                narrative_supported=self.defect != "changed_date",
                complete=self.defect != "omitted_condition",
                scope_safe=True,
                requirements=[
                    dict(
                        requirement_id=r["requirement_id"],
                        complete=not (self.defect == "omitted_condition" and r["kind"] == "guideline"),
                    )
                    for r in data["requirements"]
                ],
                guideline_support=[
                    dict(
                        claim_index=i,
                        verdict="supported",
                        support_groups=[c["evidence_handles"]],
                    )
                    for i, c in enumerate(data["draft"]["guideline_claims"])
                ],
            )
        else:
            assert request.purpose == "agent_final_stop"
            data = json.loads(request.messages[1].content)
            reply = stop_verdict(data["action"]["action"])
        return (
            FakeModelGateway(default=[reply])
            .complete(request)
            .model_copy(update={"response_id": f"PUBLIC-S0-{len(self.calls)}"})
        )

    def choose(self, board):
        action = dict(rationale="PUBLIC visible information gap")
        if board["source"]["resolution"] != "resolved":
            return action | dict(
                action="clarify",
                questions=[dict(field="source_version", question="请确认可核对的版本。", reason="当前版本未解析。")],
            )
        if self.extract and board["extracted_unverified"] is None:
            return action | dict(action="extract_ae", narrative_ref="task_narrative", source_type=board["source_type"])
        views = board["evidence"]
        if not views:
            return action | dict(
                action="search_documents",
                query="药品名称 事件描述 原文引用"
                if board["last_observation"]["kind"] != "empty"
                else "资料摘要 缺失 不推断 因果判断",
            )
        # Direct finish proposals are allowed to quote the task narrative. The
        # actual final gate still validates every span/value and completeness.
        facts = []
        for quote in ("一名成年人", "合成药品A", "皮疹", "2026-10-01"):
            start = board["narrative"].index(quote)
            facts.append(
                dict(requirement_id="event", value=quote, quote=quote, char_start=start, char_end=start + len(quote))
            )
        draft = dict(narrative_facts=facts, guideline_claims=[], missing_requirement_ids=[])
        if "最大文件大小" in board["requirements"][-1]["description"]:
            return action | dict(
                action="escalate",
                reason="insufficient_evidence",
                draft=dict(
                    narrative_facts=[],
                    guideline_claims=[],
                    missing_requirement_ids=[r["requirement_id"] for r in board["requirements"]],
                ),
            )
        if len(views) == 1:
            return action | dict(action="read_evidence", handle=views[0]["handle"], region="next")
        if self.defect == "changed_date":
            facts[-1]["value"] = "2026-10-02"
        draft["guideline_claims"] = [
            dict(requirement_id="guideline", text=v["text"], evidence_handles=[v["handle"]]) for v in views
        ]
        if self.defect == "omitted_condition":
            # Deliberately omit the no-causality requirement while retaining a
            # valid citation to the remaining statement. Final completeness,
            # rather than mere citation existence, has to reject the material.
            draft["guideline_claims"] = draft["guideline_claims"][:1]
        return action | dict(action="finish", draft=draft)


class PublicS0Retrieval:
    def __init__(self, items, *, empty_first=False, partial=False, timeout=False):
        self.items = items
        self.empty_first, self.partial, self.timeout = empty_first, partial, timeout
        self.requests = []

    def model_requests(self, request):
        return ()

    def retrieve(self, request):
        self.requests.append(request)
        if self.timeout:
            raise TimeoutError("PUBLIC injected retrieval timeout")
        items = self.items
        if self.empty_first and len(self.requests) == 1:
            items = ()
        elif self.partial:
            items = items[:1]
        return FakeRetrieval(*items).retrieve(request)


def s0_case(
    db, *, defect=None, empty_first=False, partial=False, timeout=False, history=False, missing=False, extract=False
):
    spec = json.loads(S0.read_text())
    gateway = PublicS0Gateway(defect, extract=extract)
    # Stop judgement includes committed observations as well as current
    # evidence, so this explicit fixture reserves its larger real envelope.
    cfg = final_config(max_review_user_bytes=3300 if missing else 2900, max_citation_judges=0)
    original = runtime_case(db, gateway, final_config=cfg)
    chunks = []
    with psycopg.connect(db["owner"]) as conn:
        for seq, row in enumerate(spec["private_environment"]["visible_evidence"], 1):
            chunk = conn.execute(
                "insert into chunks(doc_id,seq,page,section,content) values (%s,%s,%s,'PUBLIC S0',%s) returning chunk_id",
                (original["doc"], seq, row["page"], row["text"]),
            ).fetchone()[0]
            conn.execute(
                "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,%s,0,%s)",
                (chunk, row["page"], len(row["text"])),
            )
            chunks.append(str(chunk))
    context = original["context"].model_copy(
        update={"narrative": spec["common_task_input"]["narrative"], "source_type": "call_note"}
    )
    if missing:
        req = context.requirements[-1].model_copy(update={"description": "资料附件允许的最大文件大小是多少MB？"})
        context = context.model_copy(update={"requirements": (context.requirements[0], req)})
    if history:
        context = context.model_copy(
            update={
                "query_context": QueryContext(as_of="2020-01-01", historical_requested=True),
                "source_scope": context.source_scope.model_copy(
                    update={
                        "requested_version": "PUBLIC unavailable v0",
                        "resolution": "ambiguous",
                        "allowed_sources": (),
                    }
                ),
            }
        )
    case = reopen_case(
        db,
        original["run"].model_copy(update={"context": context}),
        original["binding"],
        chunks[0],
        gateway,
        final_config=cfg,
    )
    case["chunks"] = tuple(chunks)
    base_resources = case["resources"]
    retrieval = None

    def resources(ctx, meter):
        nonlocal retrieval
        bundle = base_resources(ctx, meter)
        if retrieval is None:
            retrieval = PublicS0Retrieval(
                bundle.skill_context.deps.retrieval.items, empty_first=empty_first, partial=partial, timeout=timeout
            )
            case["retrieval"] = retrieval
        return replace(
            bundle,
            skill_context=replace(bundle.skill_context, deps=replace(bundle.skill_context.deps, retrieval=retrieval)),
        )

    case["runtime"].resources = resources
    case["run"] = case["runtime"].new_run(context)
    case["gateway"] = gateway
    return case
