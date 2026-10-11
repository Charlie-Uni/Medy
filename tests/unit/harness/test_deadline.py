"""Total deadlines, nested ownership, overload and refusal of late side effects."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from medops.core.deadline import DeadlineExceeded, check_deadline, deadline_scope, remaining_timeout
from medops.core.errors import ErrorCode, InfrastructureError
from medops.harness.contracts import NodeFailure, NodeSpec, run_node
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import OPENAI_PRICES, Message, ModelRequest, PriceTable
from medops.infrastructure.llm.meter import MeteredGateway

KEY = "deadline-proof"


def test_nested_execution_inherits_parent_time_and_stays_on_the_callers_thread():
    caller = threading.get_ident()
    observed = []

    def parent():
        time.sleep(0.015)
        return run_node(
            NodeSpec(name="inner", timeout_s=10),
            KEY,
            lambda: observed.append((threading.get_ident(), remaining_timeout(10))),
        )

    run_node(NodeSpec(name="outer", timeout_s=0.1), KEY, parent)
    assert observed[0][0] == caller and 0 < observed[0][1] < 0.09
    assert remaining_timeout(5) == 5  # no context leaked into the next request


def test_deadline_covers_all_retries_and_stops_before_a_backoff_that_cannot_fit():
    calls, slept = [], []

    def failed():
        calls.append(remaining_timeout(1))
        raise InfrastructureError(ErrorCode.dependency_unavailable, retryable=True)

    with pytest.raises(NodeFailure) as exc:
        run_node(NodeSpec(name="n", timeout_s=0.03, backoff_base_s=0.1), KEY, failed, sleep=slept.append)
    assert len(calls) == 1 and not slept
    assert exc.value.attempts[-1].error_code == "dependency_timeout"


def test_expiry_prevents_new_sql_and_model_reservations():
    class Conn:
        def cursor(self):
            raise AssertionError("no cursor must be opened after expiry")

    inner, ledger = FakeModelGateway(default=["late"]), InMemorySpendLedger()
    gateway = BudgetedGateway(inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=1)
    request = ModelRequest(
        purpose="proof", model_id="gpt-6-luna", messages=(Message(role="user", content="q"),), max_output_tokens=10
    )
    with deadline_scope(0.01):
        time.sleep(0.02)
        with pytest.raises(DeadlineExceeded):
            gateway.complete(request)
        with pytest.raises(DeadlineExceeded):
            DeadlineConnection(Conn()).execute("select 1")
    assert not inner.calls and not ledger._reservations


def test_gateway_receives_remaining_time_and_started_billing_settles_before_node_exits():
    class LateGateway(FakeModelGateway):
        def complete(self, request):
            assert 0 < request.timeout_s <= 0.03
            time.sleep(0.04)
            return super().complete(request)

    ledger, inner = InMemorySpendLedger(), LateGateway(default=["late"])
    gateway = MeteredGateway(BudgetedGateway(inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=1))
    request = ModelRequest(
        purpose="proof", model_id="gpt-6-luna", messages=(Message(role="user", content="q"),), max_output_tokens=10
    )
    with pytest.raises(NodeFailure):
        run_node(NodeSpec(name="n", timeout_s=0.03), KEY, lambda: gateway.complete(request))
    assert len(inner.calls) == 1 and gateway.calls == 1
    assert len(ledger._reservations) == 1
    assert all(actual is not None for _, _, actual in ledger._reservations.values())


def test_admission_bounds_root_bodies_and_nested_nodes_do_not_deadlock():
    entered = threading.Barrier(9)
    release = threading.Event()

    def occupied():
        def body():
            run_node(NodeSpec(name="nested", timeout_s=2), KEY, check_deadline)
            entered.wait(timeout=2)
            release.wait(timeout=2)

        return run_node(NodeSpec(name="root", timeout_s=3), KEY, body)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(occupied) for _ in range(8)]
        try:
            entered.wait(timeout=2)
            with pytest.raises(NodeFailure) as exc:
                run_node(NodeSpec(name="overload", timeout_s=1), KEY, lambda: pytest.fail("overload body started"))
            assert exc.value.attempts[-1].error_code == "dependency_timeout"
        finally:
            release.set()
        for future in futures:
            future.result(timeout=2)


def test_expiry_during_reservation_refuses_provider_and_releases_unspent_capacity():
    class SlowLedger(InMemorySpendLedger):
        def reserve(self, *args):
            reservation = super().reserve(*args)
            time.sleep(0.03)
            return reservation

    inner, ledger = FakeModelGateway(default=["late"]), SlowLedger()
    gateway = BudgetedGateway(inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=1)
    request = ModelRequest(
        purpose="proof", model_id="gpt-6-luna", messages=(Message(role="user", content="q"),), max_output_tokens=10
    )
    with pytest.raises(NodeFailure):
        run_node(NodeSpec(name="n", timeout_s=0.02), KEY, lambda: gateway.complete(request))
    assert not inner.calls
    assert len(ledger._reservations) == 1 and all(v[2] == 0 for v in ledger._reservations.values())
    assert gateway.run_accounted_cost_usd == 0


def test_real_langgraph_execution_propagates_the_enclosing_skill_deadline():
    from medops.domain import Dept, UserContext
    from medops.domain.state import VersionSet
    from medops.harness.dependencies import HarnessDeps
    from medops.harness.retrieval_port import RetrievalOutcome
    from medops.harness.runtime import initial_state, run_ask

    observed = []

    class Retrieval:
        def retrieve(self, request):
            observed.append(remaining_timeout(20))
            return RetrievalOutcome(rewritten_queries=(request.query,), candidates=(), evidence=())

    deps = HarnessDeps(retrieval=Retrieval(), gateway=FakeModelGateway(), answer_model_id="gpt-6-sol")
    state = initial_state(
        user=UserContext(user_id="u", dept=Dept.PV),
        query="According to GVP Module IV, how are audit findings graded?",
        versions=VersionSet(policy_version="p", retrieval_version="r", skill_version_set=(), model_config_version="m"),
    )
    with deadline_scope(3):
        run = run_ask(state, deps)
    assert run.outcome == "escalated" and len(observed) == 1 and 0 < observed[0] <= 3
