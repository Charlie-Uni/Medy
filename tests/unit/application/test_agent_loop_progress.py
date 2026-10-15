"""PUBLIC fake-provider regressions for the approved two-repeat guard."""

import pytest

from tests.support.pv_agent import proposal
from tests.support.pv_loop import setup_loop, terminal
from tests.support.pv_tools import parent


@pytest.mark.parametrize("empty", [False, True])
def test_repeated_tool_result_stops_after_two_decisions_without_a_third_call(empty):
    current, loop, driver, fake, meter = setup_loop({"agent_plan": [proposal(), proposal(), terminal()]})
    if empty:
        driver.template.skill_context.deps.retrieval.items = ()
    with parent():
        result = loop.run(current)
    assert result.reason == "no_progress"
    assert result.run.decisions_consumed == driver.consumed == 2
    assert len(fake.calls) == len(meter.receipts) == len(driver.actions) == 2
    assert result.terminal_request is None and result.run.status == "running"
    assert driver.events[-2].phase == "tool_committed"
    assert driver.events[-1].phase == "handoff"


def test_rationale_and_cosmetic_query_punctuation_do_not_create_progress():
    first, second = proposal(), proposal()
    first["proposal"]["query"] = "PUBLIC query?"
    second["proposal"].update(query="  ＰＵＢＬＩＣ   query！？  ", rationale="PUBLIC changed rationale")
    current, loop, driver, fake, _ = setup_loop({"agent_plan": [first, second, terminal()]})
    with parent():
        result = loop.run(current)
    assert result.reason == "no_progress" and len(fake.calls) == 2


def test_reissued_uuid_for_the_same_evidence_does_not_bypass_repeat_guard():
    from tests.support.pv_agent import uid

    current, loop, driver, fake, _ = setup_loop({"agent_plan": [proposal(), proposal(), terminal()]})

    def reissue(outcome):
        if len(driver.actions) != 2:
            return outcome
        alias = loop._registry[0].model_copy(update={"handle": uid(987)})
        view = outcome.payload.matches[0].model_copy(update={"handle": alias.handle})
        return outcome.model_copy(
            update={
                "payload": outcome.payload.model_copy(update={"matches": (view,)}),
                "issued_handles": (alias,),
                "new_handles_issued": True,
            }
        )

    driver.change_outcome = reissue
    with parent():
        result = loop.run(current)
    assert result.reason == "no_progress" and len(fake.calls) == 2
    assert len(result.evidence_registry) == 2
    committed = [e.progress for e in driver.events if e.phase == "tool_committed"]
    assert committed[0].consecutive == 1 and committed[1].consecutive == 2
    assert committed[0].result_sha256 == committed[1].result_sha256
    assert driver.events[-1].progress == committed[-1]


def test_same_query_that_gains_real_evidence_continues():
    current, loop, driver, fake, _ = setup_loop({"agent_plan": [proposal(), proposal(), terminal()]})
    retrieval = driver.template.skill_context.deps.retrieval
    saved = retrieval.items
    retrieval.items = ()
    driver.after_tool = lambda _: setattr(retrieval, "items", saved)
    with parent():
        result = loop.run(current)
    assert result.reason == "completed" and len(fake.calls) == 3
    assert [o.kind for o in result.outcomes] == ["empty", "ok"]
    assert [e.progress.consecutive for e in driver.events if e.phase == "tool_committed"] == [1, 1]


def test_genuine_query_rewrite_is_allowed_even_if_result_is_the_same():
    changed = proposal()
    changed["proposal"]["query"] = "PUBLIC different search about a missing condition"
    current, loop, driver, fake, _ = setup_loop({"agent_plan": [proposal(), changed, terminal()]})
    with parent():
        result = loop.run(current)
    assert result.reason == "completed" and len(fake.calls) == 3
    assert [e.progress.consecutive for e in driver.events if e.phase == "tool_committed"] == [1, 1]


def test_repeated_verified_claim_stops_without_a_fourth_planning_call():
    def choose(state):
        if state["last_observation"]["kind"] is None:
            return proposal()
        data = proposal("verify_citations")
        view = state["evidence"][0]
        data["proposal"]["claims"] = [
            dict(requirement_id="guideline", text=view["text"], evidence_handles=[view["handle"]])
        ]
        return data

    current, loop, driver, fake, _ = setup_loop(choose=choose)
    with parent():
        result = loop.run(current)
    assert result.reason == "no_progress" and len(fake.calls) == 3
    assert [a.proposal.action for a in driver.actions] == ["search_documents", "verify_citations", "verify_citations"]
    assert result.run.decisions_consumed == 3


def test_longer_read_is_progress_but_repeating_the_same_full_read_stops():
    from medops.application.agent_tool_results import AgentFact
    from tests.support.harness_data import evidence
    from tests.support.pv_agent import DIGEST

    def choose(state):
        if state["last_observation"]["kind"] is None:
            return proposal()
        data = proposal("read_evidence")
        data["proposal"].update(handle=state["evidence"][0]["handle"], region="current")
        return data

    current, loop, driver, fake, _ = setup_loop(choose=choose)
    text = "PUBLIC condition. " * 35 + "Do NOT infer causality at 1.5 mg."
    actual = evidence("PUBLIC-chunk", text, doc_id="PUBLIC-doc", version="PUBLIC v1")
    driver.facts.items["PUBLIC-chunk"] = AgentFact(evidence=actual, source_sha256=DIGEST)
    driver.template.skill_context.deps.retrieval.items = (actual,)
    with parent():
        result = loop.run(current)
    assert result.reason == "no_progress" and len(fake.calls) == 3
    assert result.outcomes[0].payload.matches[0].truncated
    assert result.outcomes[1].payload.evidence.text == text
    assert [e.progress.consecutive for e in driver.events if e.phase == "tool_committed"] == [1, 1, 2]


def test_invalid_decision_breaks_consecutive_tool_repeat_streak_but_costs_a_step():
    current, loop, driver, fake, _ = setup_loop({"agent_plan": [proposal(), "bad", proposal(), terminal()]})
    with parent():
        result = loop.run(current)
    assert result.reason == "completed" and result.run.decisions_consumed == 4 and len(fake.calls) == 4
    assert [e.progress.consecutive for e in driver.events if e.phase == "tool_committed"] == [1, 1]
    assert [e.progress.consecutive for e in driver.events if e.phase == "proposal_rejected"] == [0]


@pytest.mark.parametrize("fault", ["cancelled", "lease_lost", "checkpoint_failure", "corrupt_result"])
def test_repeat_guard_cannot_override_a_second_action_boundary_failure(fault):
    from tests.support.pv_agent import uid

    current, loop, driver, fake, meter = setup_loop({"agent_plan": [proposal(), proposal(), terminal()]})

    def after_tool(_):
        if len(driver.actions) == 2:
            if fault == "checkpoint_failure":
                driver.fail_phase = "tool_committed"
            elif fault != "corrupt_result":
                driver.deny = fault

    def corrupt(outcome):
        if fault == "corrupt_result" and len(driver.actions) == 2:
            return outcome.model_copy(update={"action_id": uid(999)})
        return outcome

    driver.after_tool, driver.change_outcome = after_tool, corrupt
    with parent():
        result = loop.run(current)
    assert result.reason == (fault if fault in {"cancelled", "lease_lost"} else "audit_failure")
    assert len(fake.calls) == len(meter.receipts) == 2 and result.terminal_request is None
    assert result.run.decisions_consumed == 2 and result.run.budget.accounted_tokens == meter.tokens


@pytest.mark.parametrize("rejected", ["old_run", "foreign_parent"])
def test_rejected_budget_binding_never_emits_a_fresh_zero_progress_checkpoint(rejected):
    from medops.infrastructure.llm.execution_budget import CallAllowance

    current, loop, driver, fake, _ = setup_loop()
    if rejected == "old_run":
        current = current.model_copy(update={"decisions_consumed": 1})
    with parent() as budget:
        if rejected == "foreign_parent":
            budget.reserve(CallAllowance("PUBLIC-foreign-pending", 10, 0.001))
        result = loop.run(current)
    assert result.reason == "unsupported_recovery" and not fake.calls
    assert driver.events[-1].progress is None  # unbound: must not erase any stored old progress
