"""Journal ordering, nested ownership and failures; no provider network."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import pytest

from medops.core.deadline import deadline_scope
from medops.infrastructure.llm.execution_budget import ExecutionLimits, complete_in_execution, execution_scope
from medops.infrastructure.llm.execution_journal import execution_journal_scope
from tests.support.model_gateway import _FixedCost, req


class Journal:
    def __init__(self, fail=None):
        self.events, self.fail = [], fail

    def admitted(self, request, budget):
        state = budget.journal_state()
        assert state["pending"] and not state["settled"]
        self.events.append(("admitted", state))
        if self.fail == "admitted":
            raise RuntimeError("PUBLIC admission failure")

    def settled(self, request, receipt, response, budget):
        self.events.append(("settled", receipt))
        assert not budget.snapshot().reserved_tokens
        if self.fail == "settled":
            raise RuntimeError("PUBLIC settlement failure")


@pytest.mark.parametrize("fail,calls,accounted", [(None, 1, 15), ("admitted", 0, 0), ("settled", 1, 15)])
def test_commit_before_provider_and_retention_when_persistence_fails(fail, calls, accounted):
    journal, gateway = Journal(fail), _FixedCost(0.001)
    limits = ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=125)
    with execution_scope(limits) as budget, execution_journal_scope(journal):
        if fail:
            with pytest.raises(RuntimeError):
                complete_in_execution(req(), gateway.complete, provider="stub")
        else:
            complete_in_execution(req(), gateway.complete, provider="stub")
        assert gateway.calls == calls and budget.snapshot().accounted_tokens == accounted
        assert budget.snapshot().calls == calls and not budget.snapshot().reserved_tokens
        if calls:
            assert budget.snapshot().known_cost_usd == 0.001
    assert journal.events[0][0] == "admitted"


def test_nested_gateway_and_copied_thread_context_share_one_journal_and_original_deadline():
    journal, gateway = Journal(), _FixedCost(0.001)
    limits = ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=125)
    with execution_scope(limits) as budget, execution_journal_scope(journal):

        def operation(request):
            return complete_in_execution(request, gateway.complete, provider="stub")

        with deadline_scope(3), ThreadPoolExecutor(1) as executor:
            result = executor.submit(
                copy_context().run, complete_in_execution, req(), operation, provider="stub"
            ).result()
        assert result.text == "ok" and budget.snapshot().calls == 1
        assert journal.events[0][1]["remaining_timeout_s"] > 120
        assert [e[0] for e in journal.events] == ["admitted", "settled"]
        with pytest.raises(ValueError, match="cannot_replace"):
            with execution_journal_scope(Journal()):
                pass
        with execution_journal_scope(journal):
            pass


@pytest.mark.parametrize("failure", ["deadline", "ownership"])
def test_admission_commit_cannot_authorize_a_late_or_no_longer_owned_provider_call(failure):
    import time

    from medops.core.deadline import DeadlineExceeded
    from medops.infrastructure.llm.accounting import call_scope

    journal, gateway = Journal(), _FixedCost(0.001)
    admitted = journal.admitted
    owned = {"value": True}

    def guard():
        if not owned["value"]:
            raise RuntimeError("PUBLIC ownership lost during commit")

    def committed(request, budget):
        admitted(request, budget)
        if failure == "deadline":
            time.sleep(0.03)
        else:
            owned["value"] = False

    journal.admitted = committed
    limits = ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=125)
    with execution_scope(limits) as root, execution_journal_scope(journal), call_scope(before_call=guard):
        with deadline_scope(0.02 if failure == "deadline" else 2), pytest.raises((DeadlineExceeded, RuntimeError)):
            complete_in_execution(req(), gateway.complete, provider="stub")
        assert gateway.calls == root.snapshot().calls == root.snapshot().accounted_tokens == 0
        assert not root.snapshot().reserved_tokens
        assert journal.events[-1][0] == "settled" and not journal.events[-1][1].provider_started
        assert journal.events[-1][1].accounted_cost_usd == 0
