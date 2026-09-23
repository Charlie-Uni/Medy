"""M2-03 through the graph with the in-memory ledger: a repeated run reuses every node without repeating side
effects, a replay run id never touches production rows, failures are recorded per attempt and re-claimed, a
claim held by another worker is not executed twice, and a stale claim is taken over."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from medops.domain.common import ReasonCode
from medops.harness.executions import InMemoryExecutionStore, apply_delta, state_delta
from medops.harness.runtime import run_ask
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelUnavailable
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import CONTRA, LABEL, FakeRetrieval, make_deps, state

ANSWER = {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}
NODES = ["intent", "retrieve", "verify", "safety", "answer"]


def deps_with(store, gateway, retrieval=None, **kw):
    return make_deps(
        retrieval or FakeRetrieval(evidence("c1", LABEL), evidence("c2", CONTRA)), gateway, executions=store, **kw
    )


def test_repeated_run_reuses_every_node_and_repeats_no_side_effect():
    store = InMemoryExecutionStore()
    gateway = FakeModelGateway({"answer": [ANSWER]})
    retrieval = FakeRetrieval(evidence("c1", LABEL), evidence("c2", CONTRA))
    first = run_ask(state(), deps_with(store, gateway, retrieval))
    assert first.outcome == "answered" and [a.node for a in first.attempts] == NODES
    assert sorted(r.node_name for r in store.rows.values()) == sorted(NODES)
    assert all(r.status == "succeeded" and r.run_kind == "production" for r in store.rows.values())
    assert [(c, a.node) for c, a in store.attempts] == [(1, n) for n in NODES]

    second = run_ask(state(), deps_with(store, gateway, retrieval))
    assert second.outcome == "answered" and second.state.answer == first.state.answer
    assert second.attempts == () and len(gateway.calls) == 1 and len(retrieval.requests) == 1
    assert second.state == first.state


def test_replay_run_id_never_reuses_production_results():
    store = InMemoryExecutionStore()
    gateway = FakeModelGateway({"answer": [ANSWER, ANSWER]})
    retrieval = FakeRetrieval(evidence("c1", LABEL), evidence("c2", CONTRA))
    run_ask(state(), deps_with(store, gateway, retrieval))
    replay = run_ask(state(run_id="b" * 32), deps_with(store, gateway, retrieval))
    assert replay.outcome == "answered" and [a.node for a in replay.attempts] == NODES
    assert len(gateway.calls) == 2 and len(retrieval.requests) == 2
    kinds = sorted((r.run_kind, r.node_name) for r in store.rows.values())
    assert kinds == sorted([("production", n) for n in NODES] + [("replay", n) for n in NODES])


def test_failed_node_is_recorded_per_attempt_and_re_claimed_on_the_next_run():
    store = InMemoryExecutionStore()
    gateway = FakeModelGateway({"answer": [ModelUnavailable("down", retryable=True)] * 3 + [ANSWER]})
    first = run_ask(state(), deps_with(store, gateway))
    assert first.outcome == "escalated" and first.state.escalation is not None
    assert first.state.escalation.reason_codes == (ReasonCode.system_failure,)
    row = next(r for r in store.rows.values() if r.node_name == "answer")
    assert row.status == "failed" and row.error_code == "dependency_unavailable" and row.claim_no == 1
    assert [(c, a.attempt, a.outcome) for c, a in store.attempts if a.node == "answer"] == [
        (1, 1, "retry"),
        (1, 2, "retry"),
        (1, 3, "failed"),
    ]

    second = run_ask(state(), deps_with(store, gateway))
    assert second.outcome == "answered" and [a.node for a in second.attempts] == ["answer"]  # the rest reused
    assert row.status == "succeeded" and row.claim_no == 2 and len(gateway.calls) == 4
    assert [(c, a.attempt) for c, a in store.attempts if a.node == "answer"][-1] == (2, 1)


def test_claim_held_by_another_worker_is_not_executed_twice():
    store = InMemoryExecutionStore()
    gateway = FakeModelGateway({"answer": [ANSWER]})
    run_ask(state(), deps_with(store, gateway))
    intent_key = next(k for k, r in store.rows.items() if r.node_name == "intent")
    store.rows[intent_key].status = "running"
    store.rows[intent_key].claimed_at = datetime(2026, 9, 23, tzinfo=UTC)  # same instant as the fake clock
    run = run_ask(state(), deps_with(store, gateway))
    assert run.outcome == "escalated" and run.state.escalation is not None
    assert (
        run.state.escalation.reason_codes == (ReasonCode.system_failure,) and "in flight" in run.state.escalation.detail
    )
    assert [a.node for a in run.attempts] == ["escalate"] and len(gateway.calls) == 1  # only the escalation ran


def test_stale_running_claim_is_taken_over():
    store = InMemoryExecutionStore(stale_after_s=60)
    gateway = FakeModelGateway({"answer": [ANSWER, ANSWER]})
    run_ask(state(), deps_with(store, gateway))
    answer_key = next(k for k, r in store.rows.items() if r.node_name == "answer")
    store.rows[answer_key].status = "running"
    store.rows[answer_key].claimed_at = datetime(2026, 9, 23, tzinfo=UTC) - timedelta(minutes=10)
    run = run_ask(state(), deps_with(store, gateway))
    assert run.outcome == "answered" and [a.node for a in run.attempts] == ["answer"]
    assert store.rows[answer_key].claim_no == 2 and store.rows[answer_key].status == "succeeded"


def test_state_delta_round_trips_through_advance():
    gateway = FakeModelGateway({"answer": [ANSWER]})
    before = state()
    after = run_ask(before, deps_with(None, gateway)).state
    delta = state_delta(before, after)
    assert set(delta) >= {"intent", "evidence", "verify_result", "safety_result", "answer", "budget"}
    assert apply_delta(before, delta) == after
