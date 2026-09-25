"""Knowledge-gap tickets (M4-05): only knowledge_gap cases get one, the ticket carries the question and a gap line and
nothing else, and a human override note replaces the rule note."""

from __future__ import annotations

from medops.loop.tickets import GAP_MAX, TOPIC_MAX, build_ticket


def case(**kw):
    base = {
        "case_id": "c1",
        "dept": "PV",
        "attribution": "knowledge_gap",
        "attribution_note": "nothing retrieved",
        "human_override": None,
    }
    base.update(kw)
    return base


def test_only_knowledge_gap_cases_become_tickets():
    assert build_ticket(case(attribution="retrieval"), query="q") is None
    assert (
        build_ticket(
            case(
                attribution="retrieval",
                human_override={"attribution": "knowledge_gap", "note": "", "by": "r", "at": "x"},
            ),
            query="q",
        )
        is not None
    )
    assert (
        build_ticket(
            case(
                attribution="knowledge_gap",
                human_override={"attribution": "generation", "note": "", "by": "r", "at": "x"},
            ),
            query="q",
        )
        is None
    )


def test_ticket_carries_question_and_gap_only():
    t = build_ticket(case(), query="  GVP   Module VI  的 ICSR 提交时限？ ")
    assert (
        t is not None
        and t.topic == "GVP Module VI 的 ICSR 提交时限？"
        and t.gap == "knowledge gap (PV): nothing retrieved"
    )
    assert set(t.__dataclass_fields__) == {"case_id", "dept", "topic", "gap"}  # no field could hold an answer
    long = build_ticket(case(attribution_note="n" * 2000), query="q" * 2000)
    assert long is not None and len(long.topic) == TOPIC_MAX and len(long.gap) == GAP_MAX


def test_human_note_wins_over_the_rule_note():
    t = build_ticket(
        case(
            human_override={
                "attribution": "knowledge_gap",
                "note": "corpus lacks the 2024 revision",
                "by": "r",
                "at": "x",
            }
        ),
        query="q",
    )
    assert t is not None and t.gap.endswith("corpus lacks the 2024 revision")
