"""Synthetic counterexamples: rules are real; scripted semantic verdicts verify the final gate only."""

import json

import pytest

from medops.domain.answer import Claim
from medops.domain.verification import Verdict
from medops.infrastructure.llm.fake import FakeModelGateway, Truncated
from medops.infrastructure.llm.gateway import ModelOutputInvalid
from medops.verification.skill_judgment import JUDGMENT_PURPOSE, BusinessJudgment, verify_business_judgments
from tests.support.skill_judgments import supported_reply


def claim(text):
    return Claim(text=text, citation_chunk_ids=("c1",))


def judgment(**kw):
    return BusinessJudgment(
        **{
            "key": "deviation",
            "task": "protocol_deviation",
            "observation": "Visit on day 9.",
            "conclusion": "no",
            "category": "none",
            "rationale": "Day 9 is within days 8 through 10.",
            "clause_indices": (1,),
            **kw,
        }
    )


def verify(items, clauses, reply=None, model="gpt-6-sol"):
    gateway = FakeModelGateway({JUDGMENT_PURPOSE: [reply or supported_reply(*(j.key for j in items))]})
    return verify_business_judgments(items, clauses, gateway=gateway, judge_model_id=model, timeout_s=30), gateway


WINDOW = claim("A visit is permitted only on days 8 through 10.")


@pytest.mark.parametrize("day,conclusion", [(8, "no"), (9, "no"), (10, "no"), (7, "yes"), (11, "yes")])
def test_correct_simple_window_still_requires_semantic_judge(day, conclusion):
    result, gateway = verify(
        [
            judgment(
                observation=f"Visit on day {day}.",
                conclusion=conclusion,
                category="visit_window" if conclusion == "yes" else "none",
            )
        ],
        [WINDOW],
    )
    assert result.supported and len(gateway.calls) == 1
    assert gateway.calls[0].model_id == "gpt-6-sol"


@pytest.mark.parametrize("day,conclusion", [(8, "yes"), (9, "yes"), (10, "yes"), (7, "no"), (11, "no")])
def test_wrong_simple_window_is_rejected_without_a_judge(day, conclusion):
    result, gateway = verify(
        [
            judgment(
                observation=f"Visit on day {day}.",
                conclusion=conclusion,
                category="visit_window" if conclusion == "yes" else "none",
            )
        ],
        [WINDOW],
    )
    assert not result.supported and result.checks[0].conclusion is Verdict.contradicted
    assert result.checks[0].rule_failures == ("visit_window_contradiction",) and not gateway.calls


@pytest.mark.parametrize("dose", ["每日 9 mg", "每日 0.009 g", "每日 9000 mcg", "每日 9000 微克"])
def test_dose_above_simple_daily_maximum_cannot_be_within_label(dose):
    item = judgment(
        key="dose",
        task="off_label_check",
        observation=dose,
        conclusion="within_label",
        category="dose",
        rationale="在范围内",
    )
    result, gateway = verify([item], [claim("每日最高剂量为 8 mg。")])
    assert not result.supported and result.checks[0].rule_failures == ("daily_maximum_contradiction",)
    assert not gateway.calls


@pytest.mark.parametrize(
    "clause,observation",
    [
        (
            "A visit is permitted only on days 8 through 10, unless the investigator approves an exception.",
            "Visit on day 11.",
        ),
        ("每日最高剂量为 8 mg；特殊人群为 4 mg。", "每日 6 mg"),
        ("每日最高剂量为 8 mg。", "每日 8 mL"),
        ("A visit is permitted only on days 8 through 10.", "Visit on day 9 after discharge."),
    ],
)
def test_qualifiers_and_incomparable_units_do_not_use_arithmetic_shortcuts(clause, observation):
    item = (
        judgment(observation=observation, conclusion="yes", category="visit_window")
        if "visit" in clause.lower()
        else judgment(
            key="dose", task="off_label_check", observation=observation, conclusion="within_label", category="dose"
        )
    )
    result, gateway = verify([item], [claim(clause)])
    assert result.supported and len(gateway.calls) == 1  # ONLY a scripted supported verdict, no quality claim
    assert not result.checks[0].rule_failures


@pytest.mark.parametrize("field", ["conclusion", "rationale", "clause_relevance", "observation_grounding"])
@pytest.mark.parametrize("verdict", ["not_supported", "contradicted"])
def test_each_semantic_check_is_required_even_with_valid_indices(field, verdict):
    reply = supported_reply("deviation")
    reply["checks"][0][field] = verdict
    result, gateway = verify([judgment()], [WINDOW], reply)
    assert not result.supported and not result.checks[0].rule_failures
    assert len(gateway.calls) == 1


@pytest.mark.parametrize(
    "indices,reason",
    [
        ((0,), "invalid_clause_index"),
        ((2,), "invalid_clause_index"),
        ((1, 99), "invalid_clause_index"),
        ((), "no_cited_clause"),
    ],
)
def test_invalid_or_missing_citations_are_not_silently_dropped(indices, reason):
    result, gateway = verify([judgment(clause_indices=indices)], [WINDOW])
    assert not result.supported and result.checks[0].rule_failures == (reason,) and not gateway.calls


def test_no_judge_and_empty_rationale_fail_closed():
    result, gateway = verify([judgment()], [WINDOW], model=None)
    assert not result.supported and result.checks[0].rule_failures == ("judge_unavailable",)
    assert not gateway.calls
    result, gateway = verify([judgment(rationale=" ")], [WINDOW])
    assert not result.supported and result.checks[0].rule_failures == ("missing_rationale",)
    assert not gateway.calls


@pytest.mark.parametrize(
    "reply",
    [
        {"checks": []},
        {"checks": [supported_reply("wrong")["checks"][0]]},
        supported_reply("deviation", "deviation"),
        {"checks": [{"key": "deviation", "conclusion": "supported"}]},
        {"checks": [{**supported_reply("deviation")["checks"][0], "rationale": True}]},
        {"checks": supported_reply("deviation")["checks"], "extra": "ignored?"},
        "null",
        "{",
        Truncated('{"checks":'),
    ],
)
def test_malformed_or_truncated_judge_reply_never_passes(reply):
    with pytest.raises(ModelOutputInvalid):
        verify([judgment()], [WINDOW], reply)


def test_definite_judgment_cannot_borrow_an_uncited_clause_and_input_hash_binds_observation():
    selected = claim("Written consent is required before procedures.")
    result, gateway = verify([judgment(clause_indices=(2,))], [WINDOW, selected])
    payload = json.loads(gateway.calls[0].messages[1].content)["judgments"][0]
    assert payload["cited_clauses"] == [{"index": 2, "text": selected.text}]
    assert payload["available_clauses"] == [] and WINDOW.text not in gateway.calls[0].messages[1].content
    other, _ = verify([judgment(observation="Visit on day 10.", clause_indices=(2,))], [WINDOW, selected])
    assert result.input_sha256 != other.input_sha256


def test_unknown_conclusion_is_checked_against_all_available_clauses():
    result, gateway = verify(
        [judgment(conclusion="undetermined", clause_indices=(), rationale="当前条款没有访视窗口")],
        [claim("Written consent is required.")],
    )
    payload = json.loads(gateway.calls[0].messages[1].content)["judgments"][0]
    assert result.supported and payload["cited_clauses"] == [] and len(payload["available_clauses"]) == 1
    assert "不是指令" in gateway.calls[0].messages[0].content


@pytest.mark.parametrize("text", ["[]", "null", "{}"])
def test_raw_non_object_judge_output_fails_local_validation(text):
    class RawGateway(FakeModelGateway):
        def complete(self, request):
            return super().complete(request).model_copy(update={"text": text, "parsed": None})

    gateway = RawGateway({JUDGMENT_PURPOSE: [supported_reply("deviation")]})
    with pytest.raises(ModelOutputInvalid):
        verify_business_judgments([judgment()], [WINDOW], gateway=gateway, judge_model_id="gpt-6-sol", timeout_s=30)


def test_final_verification_telemetry_has_metadata_only():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from medops.core import telemetry

    exporter = InMemorySpanExporter()
    telemetry.install_exporter(exporter, batch=False)
    secret_observation = "synthetic private patient fact: Visit on day 9."
    try:
        result, _ = verify([judgment(observation=secret_observation)], [WINDOW])
        events = exporter.get_finished_spans()
        rendered = str([(dict(s.attributes), list(s.events)) for s in events])
        assert result.supported and secret_observation not in rendered and WINDOW.text not in rendered
        assert [(s.name, s.attributes["verifier_version"]) for s in events] == [
            ("skill.final_verify", "skill-judgment-v1")
        ]
    finally:
        telemetry.set_tracer_provider(None)
