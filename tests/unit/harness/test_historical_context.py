"""Dates and explicit archival mode propagate through both Skill harness paths."""

from dataclasses import replace
from datetime import date

import pytest

from medops.core.errors import BusinessError
from medops.domain.common import DocStatus, DocType
from medops.domain.query import QueryContext
from medops.domain.skill import SkillStatus
from medops.harness.executions import InMemoryExecutionStore
from medops.harness.runtime import initial_state, run_ask
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills._structured import grounded_run
from medops.skills.catalog import default_registry
from tests.support.harness import LABEL, FakeRetrieval, make_deps
from tests.support.harness_data import evidence, user, versions
from tests.support.label_query import ANSWER, INPUT, ctx

QUERY = "label 儿童剂量？"
HISTORY = QueryContext(as_of=date(2026, 6, 1), historical_requested=True)


@pytest.mark.parametrize("path", ["label", "structured"])
def test_historical_skills_retrieve_archived_evidence_and_keep_the_notice(path):
    reg = default_registry(sleep=lambda _s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, status=DocStatus.archived, historical=True))
    context = ctx(retrieval, FakeModelGateway({"answer": [ANSWER]}), {"doc-1": DocType.label}, reg)
    context = replace(
        context, as_of=HISTORY.as_of, deps=replace(context.deps, as_of=HISTORY.as_of, query_context=HISTORY)
    )
    if path == "label":
        out = reg.execute("label_query", "1.0.0", INPUT, context=context).output
        assert out.status is SkillStatus.completed and out.historical_notice is True
    else:
        run = grounded_run(context, QUERY)
        assert run.state.answer is not None and run.state.answer.historical_notice is True
        assert run.state.query_context == HISTORY
    assert retrieval.requests[0].as_of == HISTORY.as_of
    assert retrieval.requests[0].historical_requested is True


def test_history_without_an_explicit_date_and_conflicting_contexts_fail_before_a_call():
    port, gateway = FakeRetrieval(), FakeModelGateway()
    deps = make_deps(port, gateway)
    state = initial_state(user=user(), query=QUERY, versions=versions(), historical_requested=True)
    with pytest.raises(BusinessError):
        run_ask(state, deps)
    state = initial_state(user=user(), query=QUERY, versions=versions(), query_context=HISTORY)
    with pytest.raises(BusinessError):
        run_ask(state, replace(deps, as_of=date(2026, 6, 2)))
    assert port.requests == [] and gateway.calls == []


def test_same_run_different_day_or_mode_cannot_reuse_operation_results():
    store = InMemoryExecutionStore()
    keys = []
    for context in [QueryContext(as_of=HISTORY.as_of), HISTORY, QueryContext(as_of=date(2026, 6, 2))]:
        state = initial_state(user=user(), query=QUERY, versions=versions(), run_id="same", query_context=context)
        run = run_ask(
            state,
            make_deps(
                FakeRetrieval(), FakeModelGateway(), executions=store, as_of=context.as_of, query_context=context
            ),
        )
        keys.append(run.attempts[0].operation_key)
    assert len(set(keys)) == 3
