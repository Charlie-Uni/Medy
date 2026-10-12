"""`POST /admin/traces/{id}/replay` (M3-08): admin-only; re-runs the source question under the original
principal with a fresh replay_run_id (no ledger reuse), records the replay as its own trace without an
escalation, and reports the diff; unknown traces are 404."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.policy_loader import ReleasedPolicySet, RequestPolicies
from medops.domain.common import Dept, DocStatus
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.api_runtime import ANSWER, QUERY
from tests.support.harness import LABEL, FakeRetrieval
from tests.support.harness_data import evidence
from tests.support.replay_runtime import ADMIN_PID, USER_PID, ReplayRuntime, auth


def test_admin_replay_reruns_under_the_original_principal_with_a_fresh_run_id():
    rt = ReplayRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER, ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    ledger_before = len(rt.store.rows)
    r = c.post(f"/admin/traces/{src['trace_id']}/replay", json={"reason": "spot check"}, headers=auth("admin-1"))
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["source"]["trace_id"] == src["trace_id"] and report["replay"]["trace_id"] != src["trace_id"]
    assert report["replay"]["run_id"] != report["source"]["run_id"]
    assert report["replay"]["run_id"] != report["replay"]["trace_id"]
    assert report["changed"] == [] and report["versions_match"] is True and report["replay"]["outcome"] == "answered"
    assert len(rt.store.rows) == ledger_before + 5  # every node ran again: no operation-key reuse across runs
    replay_trace = rt.traces.traces[report["replay"]["trace_id"]]
    assert (
        replay_trace.kind == "replay"
        and replay_trace.principal == USER_PID
        and report["replay"]["trace_id"] not in rt.traces.escalations
    )
    assert rt.traces.replays[0].source_trace_id == src["trace_id"] and rt.traces.replays[0].requested_by == ADMIN_PID
    assert rt.bound[-1] == Dept.MA and len(rt.gateway.calls) == 2


def test_replay_reports_changes_and_guards():
    rt = ReplayRuntime(
        FakeRetrieval(evidence("c1", LABEL)),
        FakeModelGateway({"answer": [ANSWER, {"answers_question": False, "claims": []}]}),
    )
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    report = c.post(
        f"/admin/traces/{src['trace_id']}/replay", json={"reason": "drift check"}, headers=auth("admin-1")
    ).json()
    assert report["replay"]["outcome"] == "escalated" and set(report["changed"]) >= {
        "outcome",
        "reason_codes",
        "cited_chunk_ids",
    }
    assert (
        c.post(f"/admin/traces/{src['trace_id']}/replay", json={"reason": "x"}, headers=auth("user-1")).status_code
        == 403
    )
    assert (
        c.post("/admin/traces/" + "f" * 32 + "/replay", json={"reason": "x"}, headers=auth("admin-1")).status_code
        == 404
    )
    replay_id = report["replay"]["trace_id"]
    assert (
        c.post(f"/admin/traces/{replay_id}/replay", json={"reason": "x"}, headers=auth("admin-1")).status_code == 404
    )  # replays are not replayed
    assert c.post(f"/admin/traces/{src['trace_id']}/replay", json={}, headers=auth("admin-1")).status_code == 422


class CanaryRuntime(ReplayRuntime):
    """Every principal is routed to a canary side whose policy version differs from the deployment's base set."""

    def route_policies(self, conn, user):
        routed = self.versions.model_copy(update={"policy_version": self.versions.policy_version + "+canary:abcd"})
        return RequestPolicies(ReleasedPolicySet.empty(), routed)


def test_replay_reports_the_routed_versions_it_ran_with():
    """M4-09: the replay runs under the principal's routed versions; the report's replay side and `versions_match`
    describe those versions, not the base set the service was constructed with (record 144)."""
    rt = CanaryRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER, ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    assert src["versions"]["policy_version"] == "policy-test-1+canary:abcd"
    report = c.post(
        f"/admin/traces/{src['trace_id']}/replay", json={"reason": "canary"}, headers=auth("admin-1")
    ).json()
    assert report["replay"]["versions"]["policy_version"] == "policy-test-1+canary:abcd"
    assert report["versions_match"] is True and report["source"]["versions"] == report["replay"]["versions"]


def test_historical_replay_preserves_explicit_day_mode_and_original_principal():
    port = FakeRetrieval(evidence("c1", LABEL, status=DocStatus.archived, historical=True))
    rt = ReplayRuntime(port, FakeModelGateway({"answer": [ANSWER, ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY, "historical": {"as_of": "2026-06-01"}}, headers=auth("user-1")).json()
    assert src["answer"]["historical_notice"] is True
    response = c.post(
        f"/admin/traces/{src['trace_id']}/replay", json={"reason": "history check"}, headers=auth("admin-1")
    )
    assert response.status_code == 201, response.text
    report = response.json()
    expected = {"as_of": "2026-06-01", "historical_requested": True}
    assert report["source"]["query_context"] == report["replay"]["query_context"] == expected
    assert all(
        r.as_of == date(2026, 6, 1) and r.historical_requested and r.user.user_id == USER_PID for r in port.requests
    )
    replay = rt.traces.traces[report["replay"]["trace_id"]]
    assert replay.query_context == QueryContext.model_validate(expected)
    assert report["changed"] == [] and len(rt.gateway.calls) == 2


@pytest.mark.parametrize("mode", ["legacy", "task", "mcp", "department_changed"])
def test_unknown_or_incompatible_replay_input_is_rejected_before_any_model_call(mode):
    rt = ReplayRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    original = rt.traces.traces[src["trace_id"]]
    if mode == "legacy":
        rt.traces.traces[src["trace_id"]] = replace(original, query_context=None)
    elif mode == "department_changed":
        rt.resolve_user = lambda _conn, _principal: UserContext(
            user_id=USER_PID, dept=Dept.PV, acl_scopes=frozenset({"PV:read"})
        )
    else:
        rt.traces.traces[src["trace_id"]] = replace(original, kind=mode)
    response = c.post(
        f"/admin/traces/{src['trace_id']}/replay", json={"reason": "input check"}, headers=auth("admin-1")
    )
    assert response.status_code == 400 and response.json()["code"] == "invalid_request"
    assert len(rt.gateway.calls) == 1 and rt.traces.replays == []


def test_ordinary_replay_preserves_the_recorded_effective_day_without_enabling_archives():
    port = FakeRetrieval()
    rt = ReplayRuntime(port, FakeModelGateway())
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    original = rt.traces.traces[src["trace_id"]]
    context = QueryContext(as_of=date(2026, 6, 1))
    rt.traces.traces[src["trace_id"]] = replace(original, query_context=context)
    response = c.post(f"/admin/traces/{src['trace_id']}/replay", json={"reason": "date check"}, headers=auth("admin-1"))
    assert response.status_code == 201, response.text
    assert port.requests[-1].as_of == context.as_of and port.requests[-1].historical_requested is False
