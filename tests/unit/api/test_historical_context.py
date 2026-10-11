"""ARCH-02: production assembly must preserve the task's explicit historical selector."""

from datetime import date
from unittest.mock import Mock

import pytest

from medops.application.contracts import AskRequest
from medops.application.policy_loader import ReleasedPolicySet, RequestPolicies
from medops.bootstrap.runtime import ProductionRuntime
from medops.core.config import Settings
from medops.core.errors import BusinessError
from medops.domain.query import resolve_query_context
from medops.harness.dependencies import HarnessDeps
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.harness._fixtures import user, versions
from tests.unit.harness.test_run_ask import FakeRetrieval


def test_skill_assembly_forwards_the_requested_date_to_retrieval():
    rt = ProductionRuntime(
        settings=Mock(),
        authenticator=Mock(),
        gateway=FakeModelGateway(),
        embedding=Mock(),
        reranker=Mock(),
        versions=versions(),
        as_of=date(2026, 10, 11),
    )
    rt.route_policies = Mock(return_value=Mock(versions=versions()))

    def deps(_conn, _user, request, _routed, *, query_context=None):
        return HarnessDeps(
            retrieval=FakeRetrieval(),
            gateway=rt.gateway,
            answer_model_id="fake",
            as_of=request.historical.as_of if request.historical else rt.as_of,
            query_context=query_context,
        )

    rt.build_deps = Mock(side_effect=deps)
    ctx = rt.skill_context(Mock(), user(), "a" * 32, {"as_of": "2025-01-01", "version": None})
    assert ctx.as_of == date(2025, 1, 1)
    assert ctx.deps.as_of == ctx.as_of


@pytest.mark.parametrize("raw", [None, {"as_of": "2025-01-01"}])
def test_production_assembly_shares_one_context_with_channels_and_lookups(monkeypatch, raw):
    import medops.bootstrap.retrieval as module

    rt = ProductionRuntime(
        settings=Settings(
            _env_file=None, database_url="postgresql://test:test@localhost/test", redis_url="redis://localhost:6379/0"
        ),
        authenticator=Mock(),
        gateway=FakeModelGateway(),
        embedding=Mock(),
        reranker=Mock(),
        versions=versions(),
        as_of=date(2026, 10, 11),
    )
    routed = RequestPolicies(ReleasedPolicySet.empty(), versions())
    rt.route_policies = Mock(return_value=routed)
    rt.retrieval_services.reranker_for = Mock(return_value=Mock())
    rt.retrieval_services.glossary_for = Mock(return_value=None)
    builder, lookup = Mock(return_value=FakeRetrieval()), Mock(return_value=lambda _u, _ids: ())
    monkeypatch.setattr(module, "build_retrieval", builder)
    import medops.bootstrap.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "evidence_lookup", lookup)
    expected = resolve_query_context(raw, default_as_of=rt.as_of)
    ask = rt.build_deps(Mock(), user(), AskRequest(query="label", historical=raw), routed)
    skill = rt.skill_context(Mock(), user(), "a" * 32, raw)
    assert ask.query_context == skill.query_context == expected
    assert ask.as_of == skill.as_of == expected.as_of
    assert [call.kwargs["as_of"] for call in builder.call_args_list] == [expected.as_of] * 2
    assert lookup.call_args.kwargs == {"as_of": expected.as_of, "allow_historical": expected.historical_requested}


def test_legacy_queued_version_selector_fails_before_dependency_assembly():
    rt = ProductionRuntime(Mock(), Mock(), FakeModelGateway(), Mock(), Mock(), versions())
    rt.build_deps = Mock()
    with pytest.raises(BusinessError):
        rt.skill_context(Mock(), user(), "a" * 32, {"version": "v1", "as_of": None})
    rt.build_deps.assert_not_called()


@pytest.mark.parametrize("value", [20250101, True, "20250101", "2025-01-01T00:00:00", "2025-W01-3", "2025-02-30"])
def test_http_selector_does_not_coerce_numbers_or_timestamps_into_calendar_dates(value):
    from pydantic import ValidationError

    from medops.application.contracts import TaskCreateRequest

    for constructor, body in [
        (AskRequest, {"query": "label"}),
        (TaskCreateRequest, {"skill_name": "label_query", "skill_version": "1.0.0", "input": {}}),
    ]:
        with pytest.raises(ValidationError):
            constructor(**body, historical={"as_of": value})
