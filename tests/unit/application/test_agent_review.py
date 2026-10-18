"""PUBLIC item/evidence semantics and compiler failure cases; no hosted calls."""

import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from medops.application.agent_contracts import admit_action
from medops.application.agent_final_gate import check_structure, material_request, parse_material_check
from medops.application.agent_review import compile_review, structure_rejection, validate_review_binding
from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentFact
from medops.core.canonical import sha256_hex
from medops.domain.agent_actions import ReviewDraft
from medops.domain.agent_execution import AgentRequirement
from medops.domain.verification import Verdict
from tests.support.pv_agent import NOW, draft, proposal, run, uid, wire
from tests.support.pv_final import setup_final
from tests.support.pv_review import final_config, material_verdict
from tests.support.pv_tools import parent


def checked(**changes):
    current, tool, facts, fake, action, record = setup_final(
        reserve=10000,
        script={
            "verify": [{"verdict": "supported", "reason": "PUBLIC"}],
            "agent_final_material": [material_verdict(**changes)],
        },
    )
    cfg = final_config()
    with parent():
        proof = tool.verify_final_citations(action, run=current, evidence_registry=(record,), final_config=cfg)
    return current, action, record, proof, cfg


@pytest.mark.parametrize(
    "case",
    [
        "missing_requirement",
        "duplicate_requirement",
        "extra_requirement",
        "missing_claim",
        "duplicate_claim",
        "extra_claim",
        "foreign_handle",
        "cross_claim_handle",
        "v1",
        "boolean_string",
        "extra_field",
        "empty_group",
        "duplicate_group",
        "duplicate_handle",
        "unsupported_with_group",
        "supported_without_group",
        "bad_uuid",
    ],
)
def test_partial_or_malformed_semantic_verdict_never_becomes_complete(case):
    current, value = run(), draft()
    raw = material_verdict()
    req, claims = raw["requirements"], raw["guideline_support"]
    if case == "missing_requirement":
        req.pop()
    elif case == "duplicate_requirement":
        req.append(req[0])
    elif case == "extra_requirement":
        req.append({"requirement_id": "other", "complete": True})
    elif case == "missing_claim":
        claims.clear()
    elif case == "duplicate_claim":
        claims.append(claims[0])
    elif case == "extra_claim":
        claims.append(dict(claims[0], claim_index=1))
    elif case == "cross_claim_handle":
        value["guideline_claims"].append(
            dict(value["guideline_claims"][0], text="PUBLIC second", evidence_handles=[str(uid(11))])
        )
        claims.append(dict(claims[0], claim_index=1, support_groups=[[str(uid(10))]]))
    elif case == "foreign_handle":
        claims[0]["support_groups"] = [[str(uid(99))]]
    elif case == "v1":
        raw = {k: raw[k] for k in ("narrative_supported", "complete", "scope_safe")}
    elif case == "boolean_string":
        req[0]["complete"] = "true"
    elif case == "extra_field":
        raw["gold"] = "PUBLIC ignored fields must fail"
    elif case == "empty_group":
        claims[0]["support_groups"] = [[]]
    elif case == "duplicate_group":
        claims[0]["support_groups"] *= 2
    elif case == "duplicate_handle":
        claims[0]["support_groups"][0] *= 2
    elif case == "unsupported_with_group":
        claims[0]["verdict"] = "not_supported"
    elif case == "supported_without_group":
        claims[0]["support_groups"] = []
    else:
        claims[0]["support_groups"] = [["not-a-uuid"]]
    with pytest.raises((AgentToolFault, ValidationError)):
        parse_material_check(
            raw, current.context, ReviewDraft(**value), final_config(), original_citations_supported=True
        )


@pytest.mark.parametrize("gate", ["narrative", "complete", "item", "scope", "unsupported", "contradicted"])
def test_each_failed_gate_blocks_completion_and_removes_unverified_body(gate):
    raw = material_verdict()
    if gate in {"narrative", "complete", "scope"}:
        raw[{"narrative": "narrative_supported", "complete": "complete", "scope": "scope_safe"}[gate]] = False
    elif gate == "item":
        raw["requirements"][1]["complete"] = False
    else:
        raw["guideline_support"][0].update(
            verdict="not_supported" if gate == "unsupported" else "contradicted", support_groups=[]
        )
    current, action, record, proof, cfg = checked(**raw)
    review = compile_review(current.context, action, (record,), proof, cfg)
    assert not review.completion_eligible and review.reason != "completed"
    assert review.binding == action.binding and review.call_receipt_ids == proof.call_receipt_ids
    if gate == "narrative":
        assert not review.narrative_facts and review.requirements[0].state == "not_supported"
    elif gate == "scope":
        assert not review.narrative_facts and not review.guideline_claims and not review.evidence
        assert all(r.state == "withheld" for r in review.requirements)
    elif gate == "item":
        assert review.requirements[1].state == "incomplete"
    elif gate in {"unsupported", "contradicted"}:
        assert not review.guideline_claims and not review.evidence
        assert review.requirements[1].state == ("not_supported" if gate == "unsupported" else "contradicted")
    validate_review_binding(review, current.context, action, (record,), cfg)


def test_original_citation_failure_cannot_be_overridden_by_new_true_verdict():
    current, action, record, proof, cfg = checked()
    old = proof.payload.checks[0].model_copy(update={"verdict": Verdict.not_supported})
    # Construct the actual typed original failure, not an unchecked string enum.
    old = type(old).model_validate(old.model_dump(mode="json"))
    material = parse_material_check(
        material_verdict(), current.context, action.proposal.draft, cfg, original_citations_supported=False
    )
    proof = replace(proof, payload=proof.payload.model_copy(update={"checks": (old,)}), material_check=material)
    review = compile_review(current.context, action, (record,), proof, cfg)
    assert not review.completion_eligible and not review.guideline_claims and not review.evidence
    assert review.gates.citations_supported == "fail"


@pytest.mark.parametrize("groups", [[[10, 11]], [[10], [11]]])
def test_actual_two_excerpt_support_preserves_and_groups_or_alternatives(groups):
    current, tool, facts, fake, _, first = setup_final(reserve=10000)
    text = "PUBLIC SYNTHETIC second necessary condition."
    second = first.model_copy(
        update={
            "handle": uid(11),
            "evidence": first.evidence.model_copy(
                update={
                    "citation": first.evidence.citation.model_copy(update={"chunk_id": "PUBLIC-chunk-2"}),
                    "text": text,
                    "evidence_text_hash": sha256_hex(text),
                }
            ),
        }
    )
    facts.items[second.evidence.citation.chunk_id] = AgentFact(
        evidence=second.evidence, source_sha256=second.source_sha256
    )
    body = proposal("finish")
    body["proposal"]["draft"]["guideline_claims"][0]["evidence_handles"].append(str(uid(11)))
    action = admit_action(
        wire(body),
        run=current.model_copy(update={"decisions_consumed": 0}),
        action_id=uid(302),
        evidence_registry=(first, second),
        now=NOW,
    )
    response = material_verdict(draft_value=body["proposal"]["draft"])
    response["guideline_support"][0]["support_groups"] = [[str(uid(n)) for n in g] for g in groups]
    # A real fake gateway call through the original checker plus actual final model path.
    from medops.infrastructure.llm.fake import FakeModelGateway

    scripted = FakeModelGateway(
        {"verify": [{"verdict": "supported", "reason": "PUBLIC"}], "agent_final_material": [response]}
    )
    fake.complete = scripted.complete
    cfg = final_config(max_review_user_bytes=3000)
    with parent():
        proof = tool.verify_final_citations(action, run=current, evidence_registry=(first, second), final_config=cfg)
    review = compile_review(current.context, action, (first, second), proof, cfg)
    assert review.completion_eligible
    assert review.guideline_claims[0].support_groups == tuple(tuple(uid(n) for n in g) for g in groups)
    assert {e.handle for e in review.evidence} == {uid(10), uid(11)}
    request = json.loads(scripted.calls[-1].messages[1].content)
    assert [r["text"] for r in request["evidence"]] == [first.evidence.text, second.evidence.text]
    assert set(request) == {"narrative", "requirements", "draft", "evidence"}
    validate_review_binding(review, current.context, action, (first, second), cfg)


def test_multiple_rows_for_one_requirement_and_optional_gap_are_not_structural_failures():
    current, value = run(), draft()
    optional = AgentRequirement(
        requirement_id="optional", description="PUBLIC optional", kind="narrative", required=False
    )
    context = current.context.model_copy(update={"requirements": current.context.requirements + (optional,)})
    value["narrative_facts"].append(dict(value["narrative_facts"][0], value="PUBLIC second fact"))
    value["missing_requirement_ids"] = ["optional"]
    check_structure(context, ReviewDraft(**value))
    raw = material_verdict(current=current.model_copy(update={"context": context}), draft_value=value)
    raw["requirements"][-1]["complete"] = False
    result = parse_material_check(raw, context, ReviewDraft(**value), final_config(), original_citations_supported=True)
    assert result.requirements_complete and result.semantic_supported


@pytest.mark.parametrize(
    "mutation", ["binding", "action", "draft", "policy", "receipts", "derived", "claim_body", "source", "evidence"]
)
def test_forged_or_mismatched_internal_proof_and_sources_fail_closed(mutation):
    current, action, record, proof, cfg = checked()
    registry = (record,)
    if mutation == "binding":
        proof = replace(proof, binding=proof.binding.model_copy(update={"run_id": uid(99)}))
    elif mutation == "action":
        proof = replace(proof, action_id=uid(99))
    elif mutation == "draft":
        proof = replace(proof, draft_sha256="b" * 64)
    elif mutation == "policy":
        proof = replace(proof, material_check=proof.material_check.model_copy(update={"policy_sha256": "b" * 64}))
    elif mutation == "receipts":
        proof = replace(proof, call_receipt_ids=())
    elif mutation == "derived":
        proof = replace(proof, material_check=proof.material_check.model_copy(update={"requirements_complete": False}))
    elif mutation == "claim_body":
        proof = replace(
            proof,
            payload=proof.payload.model_copy(
                update={"checks": (proof.payload.checks[0].model_copy(update={"text": "PUBLIC different"}),)}
            ),
        )
    elif mutation == "source":
        registry = (record.model_copy(update={"source_sha256": "b" * 64}),)
    else:
        registry = (
            record.model_copy(update={"evidence": record.evidence.model_copy(update={"text": "PUBLIC corrupted"})}),
        )
    with pytest.raises((AgentToolFault, ValidationError)):
        compile_review(current.context, action, registry, proof, cfg)


def test_local_safety_cannot_be_overridden_by_all_true_model_flags():
    current, action, record, proof, cfg = checked()
    changed = action.proposal.draft.model_copy(
        update={
            "narrative_facts": (
                action.proposal.draft.narrative_facts[0].model_copy(update={"value": "you should take this medicine"}),
            )
        }
    )
    action = action.model_copy(update={"proposal": action.proposal.model_copy(update={"draft": changed})})
    from medops.core.canonical import canonical_hash

    digest = canonical_hash(changed.model_dump(mode="json"))
    proof = replace(
        proof, draft_sha256=digest, material_check=proof.material_check.model_copy(update={"draft_sha256": digest})
    )
    review = compile_review(current.context, action, (record,), proof, cfg)
    assert review.reason == "safety_boundary" and not review.completion_eligible
    assert not review.narrative_facts and not review.guideline_claims and not review.evidence


def test_missing_required_structure_has_no_fabricated_semantic_verdict_or_text():
    current, _, _, _, action, _ = setup_final(reserve=10000)
    action = action.model_copy(
        update={
            "proposal": action.proposal.model_copy(
                update={
                    "draft": ReviewDraft(
                        narrative_facts=(), guideline_claims=(), missing_requirement_ids=("event", "guideline")
                    )
                }
            )
        }
    )
    result = structure_rejection(current.context, action, final_config())
    assert not result.completion_eligible and result.reason == "unsupported_requirement"
    assert result.gates.narrative_supported == result.gates.scope_safe == result.gates.citations_supported == "not_run"
    assert not result.call_receipt_ids and not result.narrative_facts and not result.guideline_claims
    assert all(r.state == "missing" for r in result.requirements)


def test_committed_material_reuse_rejects_changed_content_and_binding():
    current, action, record, proof, cfg = checked()
    review = compile_review(current.context, action, (record,), proof, cfg)
    validate_review_binding(review, current.context, action, (record,), cfg)
    with pytest.raises(AgentToolFault):
        validate_review_binding(
            review,
            current.context,
            action,
            (record.model_copy(update={"evidence": record.evidence.model_copy(update={"text": "PUBLIC changed"})}),),
            cfg,
        )
    with pytest.raises(AgentToolFault):
        validate_review_binding(
            review.model_copy(update={"action_id": uid(99)}), current.context, action, (record,), cfg
        )


def test_material_request_requires_every_used_actual_handle():
    with pytest.raises(AgentToolFault):
        material_request(run().context, ReviewDraft(**draft()), final_config(), evidence_registry=())


def test_source_content_drift_between_citation_and_material_call_prevents_second_provider():
    current, tool, facts, fake, action, record = setup_final(
        reserve=10000,
        script={"verify": [{"verdict": "supported", "reason": "PUBLIC"}], "agent_final_material": [material_verdict()]},
    )
    original = fake.complete

    def changed(request):
        response = original(request)
        facts.items[record.evidence.citation.chunk_id] = AgentFact(
            evidence=record.evidence.model_copy(
                update={"text": "PUBLIC changed source", "evidence_text_hash": sha256_hex("PUBLIC changed source")}
            ),
            source_sha256=record.source_sha256,
        )
        return response

    fake.complete = changed
    with parent() as root, pytest.raises(AgentToolFault):
        tool.verify_final_citations(action, run=current, evidence_registry=(record,), final_config=final_config())
    assert [r.purpose for r in fake.calls] == ["verify"]
    assert root.finalization_snapshot().state == "closed"
