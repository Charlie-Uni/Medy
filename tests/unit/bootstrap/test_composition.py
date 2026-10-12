"""ARCH-08: one production binding for Ask, worker Skill and read-only search."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.support.composition import settings

from medops.application.contracts import AskRequest
from medops.application.policy_loader import (
    ReleasedPolicy,
    ReleasedPolicySet,
    ReleaseState,
    ReleaseTarget,
    RoutedPolicies,
)
from medops.bootstrap import policies as policy_module
from medops.bootstrap import retrieval as retrieval_module
from medops.bootstrap import search as search_module
from medops.bootstrap.policies import PolicyRouter, request_policies
from medops.bootstrap.retrieval import RetrievalServices
from medops.bootstrap.runtime import ProductionRuntime
from medops.bootstrap.search import SearchRuntime
from medops.core.deadline import DeadlineExceeded
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.query import resolve_query_context
from medops.harness.retrieval_port import RetrievalOutcome
from medops.infrastructure.llm.execution_budget import current_budget
from medops.infrastructure.llm.fake import FakeModelGateway


def user(identity="a" * 64):
    return UserContext(user_id=identity, dept=Dept.PV, roles=("PV",), acl_scopes=frozenset({"PV:read"}))


def released(translation):
    return ReleasedPolicySet(
        (
            ReleasedPolicy(
                "12345678-1234-1234-1234-123456789abc",
                "retrieval_params",
                "hybrid",
                "assembly-test-v1",
                {
                    "k_lexical": {"from": 20, "to": 12},
                    "k_vector": {"from": 20, "to": 15},
                    "rerank_output": {"from": 8, "to": 4},
                    "multi_query": {"from": False, "to": True},
                    "doc_focus": {"from": False, "to": True},
                    "source_constraint": {"from": False, "to": True},
                    "query_translation": {"from": "off", "to": translation},
                },
            ),
        )
    )


def outcome():
    return RetrievalOutcome(rewritten_queries=("query",), candidates=(), evidence=(), cache_hit=True)


@pytest.mark.parametrize("translation", ["off", "gpt-6-luna"])
@pytest.mark.parametrize("historical", [False, True])
def test_three_entries_share_dates_config_cache_keys_versions_and_scoped_connection(
    monkeypatch, translation, historical
):
    config = settings()
    policies = released(translation)
    route = ReleaseState((ReleaseTarget("retrieval_params", "hybrid", policies.policies[0], 100, None, None),))
    router = PolicyRouter(config, ("label_query@1.0.0",))
    monkeypatch.setattr(router, "state", lambda conn: route)
    routed = router.route(Mock(), user())
    gateway = FakeModelGateway()
    resources = RetrievalServices(config, Mock(), Mock(), cache=object())
    monkeypatch.setattr(resources, "reranker_for", lambda output: Mock(score=Mock()))
    monkeypatch.setattr(resources, "glossary_for", lambda version: None)
    built, received = [], []

    def builder(**kwargs):
        built.append(kwargs)

        def retrieve(request):
            received.append(request)
            assert current_budget() is not None
            return outcome()

        return SimpleNamespace(retrieve=retrieve)

    monkeypatch.setattr(retrieval_module, "build_retrieval", builder)
    runtime = ProductionRuntime(config, Mock(), gateway, resources.embedding, resources.reranker, routed.versions)
    runtime._policy_router, runtime._retrieval_services = router, resources
    conn = Mock()
    raw = {"as_of": "2025-01-01"} if historical else None
    context = resolve_query_context(raw)
    deps = runtime.build_deps(conn, user(), AskRequest(query="query", historical=raw))
    skill = runtime.skill_context(conn, user(), "1" * 32, raw)
    search = SearchRuntime(config, resources, router, _gateway=gateway)(conn, user())
    result = search("query", 8, as_of=context.as_of if historical else None, allow_historical=historical)
    assert deps.query_context == skill.deps.query_context == context
    assert result.versions == skill.versions == routed.versions
    assert len(built) == 3 and all(item["as_of"] == context.as_of for item in built)
    expected_keys = (routed.versions.retrieval_version, routed.versions.policy_version)
    for item in built:
        assert item["cache"] is resources.cache and item["cache_versions"] == expected_keys
        assert item["config"].k_lexical == 12 and item["config"].k_vector == 15
        assert item["multi_query"] and item["doc_focus"] and item["source_constraint"]
        assert (item["translator"] is not None) == (translation != "off")
        with item["conn_for_user"](user()) as bound:
            assert bound is not None
        with pytest.raises(BusinessError) as exc, item["conn_for_user"](user("b" * 64)):
            pass
        assert exc.value.code is ErrorCode.forbidden
    assert received[0].historical_requested is historical
    assert received[0].as_of == context.as_of and received[0].user == user()
    assert result.cache_hit and gateway.calls == []  # Assembly never makes a provider call.
    assert deps.execution_binding["rerank_output"] == 4


def test_policy_cache_reload_and_per_principal_canary_share_the_same_version_rule(monkeypatch):
    config = settings(policy_reload_ttl_s=5)
    p = released("off").policies[0]
    state = ReleaseState((ReleaseTarget(p.kind, p.name, p, 10, None, None),))
    loader = Mock(return_value=state)
    clock = [0.0]
    monkeypatch.setattr(policy_module, "load_release_state", loader)
    monkeypatch.setattr(policy_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    router = PolicyRouter(config, ())
    versions = set()
    for n in range(100):
        principal = f"{n:064x}"
        routed = router.route(Mock(), user(principal))
        expected = request_policies(state.for_principal(principal), ())
        assert routed == expected
        versions.add(routed.versions.policy_version)
    assert len(versions) == 2 and loader.call_count == 1
    clock[0] = 5.0
    assert router.route(Mock(), user()) == request_policies(state.for_principal(user().user_id), ())
    assert loader.call_count == 2


def test_search_translation_cost_and_versions_survive_a_later_retrieval_failure(monkeypatch):
    config = settings()
    routed = request_policies(RoutedPolicies(released("gpt-6-luna")), ())
    gateway = FakeModelGateway(script={"query_translation": [{"translation": "audit findings"}]})
    resources = RetrievalServices(config, Mock(), Mock())
    monkeypatch.setattr(resources, "reranker_for", lambda output: Mock())
    router = Mock(route=Mock(return_value=routed))
    execution = SearchRuntime(config, resources, router, _gateway=gateway)(Mock(), user())

    def builder(**kwargs):
        def retrieve(request):
            assert kwargs["translator"](request.query) == "audit findings"
            raise InfrastructureError(ErrorCode.dependency_unavailable)

        return SimpleNamespace(retrieve=retrieve)

    monkeypatch.setattr(retrieval_module, "build_retrieval", builder)
    with pytest.raises(InfrastructureError):
        execution("药物审计", 8, as_of=None, allow_historical=False)
    assert len(gateway.calls) == execution.audit_stats.model_calls == 1
    assert execution.audit_stats.tokens > 0 and execution.audit_stats.versions == routed.versions
    assert not execution.audit_stats.cache_hit
    assert execution.audit_stats.query_context.historical_requested is False
    assert execution.audit_stats.conditions["routed"]["query_translation_model"] == "gpt-6-luna"
    record = execution.audit_stats.call_records[0]
    assert record["request"]["messages"] and record["response"]["parsed"] == {"translation": "audit findings"}
    assert execution.audit_stats.call_receipts[0] == record["receipt"]
    assert execution.audit_stats.call_audit_complete and execution.audit_stats.retrieval_snapshot is None


def test_expired_search_assembly_cannot_call_a_provider(monkeypatch):
    config = settings()
    routed = request_policies(RoutedPolicies(released("gpt-6-luna")), ())
    gateway = FakeModelGateway()
    resources = Mock()
    router = Mock(route=Mock(return_value=routed))
    execution = SearchRuntime(config, resources, router, _gateway=gateway)(Mock(), user())
    monkeypatch.setattr(search_module, "default_specs", lambda: {"retrieve": SimpleNamespace(timeout_s=0.005)})

    def build(*args):
        time.sleep(0.02)
        return SimpleNamespace(retrieve=lambda req: outcome())

    resources.build.side_effect = build
    with pytest.raises(DeadlineExceeded):
        execution("query", 8, as_of=None, allow_historical=False)
    assert not gateway.calls and execution.audit_stats.model_calls == 0


def test_invalid_historical_selector_fails_before_search_or_gateway_assembly():
    config = settings()
    routed = request_policies(RoutedPolicies(ReleasedPolicySet.empty()), ())
    resources, router = Mock(), Mock(route=Mock(return_value=routed))
    owner = SearchRuntime(config, resources, router)
    execution = owner(Mock(), user())
    with pytest.raises(BusinessError):
        execution("query", 8, as_of=None, allow_historical=True)
    assert owner._gateway is None and not resources.build.called
    assert execution.audit_stats.versions == routed.versions


def test_lazy_gateway_initializes_once_under_concurrent_search_setup(monkeypatch):
    count = []
    barrier = threading.Barrier(8)
    gateway = FakeModelGateway()

    def build(config, *, require_execution_budget):
        assert require_execution_budget is True
        count.append(1)
        time.sleep(0.01)
        return gateway

    monkeypatch.setattr(search_module, "build_budgeted_gateway", build)
    owner = SearchRuntime(settings(), Mock(), Mock())

    def get_gateway(_):
        barrier.wait(timeout=2)
        return owner.gateway()

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(item is gateway for item in pool.map(get_gateway, range(8)))
    assert count == [1]


def test_search_resource_initialization_failure_closes_inference_process(monkeypatch):
    pinned = Mock()
    monkeypatch.setattr(search_module, "InferenceProcess", lambda **kwargs: pinned)
    monkeypatch.setattr(search_module, "ProcessEmbedding", Mock(side_effect=RuntimeError("cannot initialize")))
    with pytest.raises(RuntimeError):
        SearchRuntime.from_settings(settings())
    pinned.close.assert_called_once()


def test_search_cleanup_closes_inference_even_if_gateway_cleanup_fails():
    pinned, gateway = Mock(), Mock()
    gateway.close.side_effect = RuntimeError("close failed")
    owner = SearchRuntime(settings(), SimpleNamespace(pinned=pinned), Mock(), _gateway=gateway)
    with pytest.raises(RuntimeError):
        owner.close()
    pinned.close.assert_called_once()
