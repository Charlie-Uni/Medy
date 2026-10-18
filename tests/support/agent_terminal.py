"""PUBLIC terminal test inputs. Fake provider, real temporary PG, never unseen data."""

from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.agent_runtime import runtime_case
from tests.support.pv_agent import draft
from tests.support.pv_loop import terminal
from tests.support.pv_review import final_config, material_verdict


def stop_verdict(kind="clarify", **changes):
    return (
        dict(
            decision_supported=True,
            scope_safe=True,
            narrative_supported=True,
            questions=[dict(field="source_version", necessary=True, grounded=True)] if kind == "clarify" else [],
        )
        | changes
    )


def terminal_case(db, kind="finish", *, missing=False, reply=None, resolution=None):
    body = terminal(kind)
    if kind == "finish" and not missing:
        body["proposal"]["draft"] = draft()
        body["proposal"]["draft"]["guideline_claims"] = []
    if kind == "escalate":
        body["proposal"]["reason"] = "source_ambiguous"
    purpose = "agent_final_material" if kind == "finish" else "agent_final_stop"
    response = (
        material_verdict(
            draft_value=body["proposal"].get("draft", {}), requirements=[dict(requirement_id="event", complete=True)]
        )
        if kind == "finish"
        else stop_verdict(kind)
    )
    fake = FakeModelGateway({"agent_plan": [body], purpose: [response if reply is None else reply]})
    case = runtime_case(
        db,
        fake,
        final_config=final_config(max_review_user_bytes=1500, max_citation_judges=0),
        narrative_only=(kind == "finish"),
        scope_resolution=resolution or ("resolved" if kind == "finish" else "ambiguous"),
    )
    return case, fake


class PublicRetrievalAgent:
    """PUBLIC reactive script, not a model quality benchmark or gold oracle."""

    provider = "fake"

    def __init__(self):
        self.calls = []

    def complete(self, request):
        import json

        from tests.support.pv_agent import proposal

        self.calls.append(request)
        data = json.loads(request.messages[1].content) if request.purpose != "verify" else {}
        if request.purpose == "agent_plan":
            views = data["evidence"]
            if not views:
                reply = proposal("search_documents")
            else:
                reply = terminal("finish")
                reply["proposal"]["draft"] = draft()
                reply["proposal"]["draft"]["guideline_claims"] = [
                    dict(
                        requirement_id="guideline",
                        text=" ".join(v["text"] for v in views),
                        evidence_handles=[v["handle"] for v in views],
                    )
                ]
        elif request.purpose == "verify":
            reply = {"verdict": "supported", "reason": "PUBLIC exact quoted joint material"}
        else:
            assert request.purpose == "agent_final_material"
            reply = dict(
                narrative_supported=True,
                complete=True,
                scope_safe=True,
                requirements=[dict(requirement_id=r["requirement_id"], complete=True) for r in data["requirements"]],
                guideline_support=[
                    dict(claim_index=i, verdict="supported", support_groups=[c["evidence_handles"]])
                    for i, c in enumerate(data["draft"]["guideline_claims"])
                ],
            )
        return (
            FakeModelGateway(default=[reply])
            .complete(request)
            .model_copy(update={"response_id": f"PUBLIC-terminal-{len(self.calls)}"})
        )


def retrieval_terminal_case(db, *, joint=False):
    import psycopg

    fake = PublicRetrievalAgent()
    case = runtime_case(
        db,
        fake,
        final_config=final_config(
            max_review_user_bytes=1800 if joint else 2000,
            max_citation_judges=1 if joint else 0,
            max_citation_user_bytes=600,
            citation_attempts=1 if joint else 3,
        ),
    )
    if joint:
        with psycopg.connect(db["owner"]) as conn:
            text = "PUBLIC additional condition: retain the follow-up date."
            second = conn.execute(
                "insert into chunks(doc_id,seq,page,section,content) values (%s,1,2,'PUBLIC condition',%s) returning chunk_id",
                (case["doc"], text),
            ).fetchone()[0]
            conn.execute(
                "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,2,0,%s)",
                (second, len(text)),
            )
        case["chunks"] = (case["chunk"], str(second))
    return case, fake
