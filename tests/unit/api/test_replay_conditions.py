"""ARCH-07: restore actual Ask inputs, compare observed bindings and refuse false reproduction."""

from contextlib import contextmanager
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.api.routes import ask as ask_route
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.policy_loader import ReleasedPolicySet, RequestPolicies
from medops.domain.intent import Entity
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api.test_ask_route import ANSWER, QUERY
from tests.unit.api.test_payload_route import PROVIDER, MemoryPayloads
from tests.unit.api.test_replay_route import ReplayRuntime, auth
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval


class AuditedReplayRuntime(ReplayRuntime):
    def __init__(self):
        super().__init__(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER, ANSWER]}))
        self.payloads = MemoryPayloads()
        self.focus = "off"
        self.bad_input = False
        self.bad_call = False
        self.requests = []
        self.policy_hash = "original"

    def build_deps(self, conn, user, request, routed=None, *, query_context=None):
        self.requests.append(request)
        return replace(
            super().build_deps(conn, user, request, routed, query_context=query_context),
            evidence_focus=self.focus,
            execution_binding={"policy_snapshot": self.policy_hash},
        )

    def payload_writer(self, conn):
        return PayloadWriter(self.payloads, PROVIDER)

    @contextmanager
    def restricted_connection(self):
        yield "restricted"

    def payload_reader(self, conn):
        owner = self

        class Reader(PayloadReader):
            def read(self, user, tid, purpose):
                response = super().read(user, tid, purpose)
                if owner.bad_input:
                    for item in response.items:
                        if item.kind == "input":
                            item.payload["execution_input"]["query"] = "different input"
                if owner.bad_call:
                    for item in response.items:
                        if item.kind == "model_output":
                            item.payload["model_calls"][0]["request"].pop("purpose")
                return response

        return Reader(self.payloads, PROVIDER)


def start(rt, **fields):
    client = TestClient(create_app(rt), raise_server_exceptions=False)
    result = client.post("/v1/ask", json={"query": QUERY, **fields}, headers=auth("user-1"))
    assert result.status_code == 200, result.text
    return client, result.json()["trace_id"]


def replay(client, tid, **fields):
    return client.post(
        f"/admin/traces/{tid}/replay", json={"reason": "incident investigation", **fields}, headers=auth("admin-1")
    )


def test_replay_restores_raw_request_and_initial_session_entities_and_reports_unknown_corpus(monkeypatch):
    original = ask_route.initial_state
    entities = (Entity(kind="drug", value="example drug"),)
    monkeypatch.setattr(ask_route, "initial_state", lambda **kw: original(**kw, session_entities=entities))
    rt = AuditedReplayRuntime()
    c, tid = start(rt, session_id="session-example")
    result = replay(c, tid)
    assert result.status_code == 201, result.text
    report = result.json()
    assert rt.requests[0] == rt.requests[1]
    assert rt.retrieval.requests[0].session_entities == rt.retrieval.requests[1].session_entities == entities
    assert report["mode"] == "diagnostic_current"
    assert report["conditions"]["input_complete"] and report["conditions"]["input_match"]
    assert report["conditions"]["identity_match"] and report["conditions"]["evidence_match"]
    assert report["conditions"]["rendered_evidence_match"] and report["conditions"]["actual_models_match"]
    assert report["conditions"]["corpus_match"] is None and not report["conditions"]["original_conditions_reproduced"]
    assert len(rt.payloads.access) == 1 and rt.payloads.access[0][1] == tid
    output = PayloadReader(rt.payloads, PROVIDER).read(
        rt.resolve_user(None, rt.traces.traces[tid].principal), tid, "test input review"
    )
    calls = next(i.payload["model_calls"] for i in output.items if i.kind == "model_output")
    assert calls[0]["response"]["response_id"] == "fake-1" and calls[0]["response"]["system_fingerprint"] == "fake"


@pytest.mark.parametrize("change", ["evidence", "rendering", "policy"])
def test_same_version_labels_do_not_claim_same_facts_rendering_or_policy_contents(change):
    rt = AuditedReplayRuntime()
    c, tid = start(rt)
    if change == "evidence":
        rt.retrieval = FakeRetrieval(evidence("c1", LABEL + " Additional source condition."))
    elif change == "rendering":
        rt.focus = "compact-v1"
    else:
        rt.policy_hash = "changed"
    result = replay(c, tid)
    assert result.status_code == 201, result.text
    report = result.json()
    assert report["versions_match"] and not report["conditions"]["original_conditions_reproduced"]
    field = {"evidence": "evidence_match", "rendering": "rendered_evidence_match", "policy": "routed_policy_match"}[
        change
    ]
    assert report["conditions"][field] is False
    if change == "rendering":
        assert report["conditions"]["evidence_match"] is True


def test_original_conditions_refused_before_reading_or_model_spend_even_when_versions_match():
    rt = AuditedReplayRuntime()
    c, tid = start(rt)
    result = replay(c, tid, mode="original_conditions")
    assert result.status_code == 409 and result.json()["code"] == "version_conflict"
    assert len(rt.gateway.calls) == 1 and rt.payloads.access == []
    assert len(rt.traces.traces) == 1


def test_long_reason_keeps_access_purpose_within_existing_contract():
    rt = AuditedReplayRuntime()
    c, tid = start(rt)
    result = replay(c, tid, reason="x" * 500)
    assert result.status_code == 201, result.text
    assert len(rt.payloads.access[0][2]) == 500
    assert rt.traces.replays[0].reason == "x" * 500


def test_replay_binds_configuration_and_version_from_one_policy_resolution():
    class ChangingPolicies(AuditedReplayRuntime):
        route_count = 0

        def route_policies(self, conn, user):
            self.route_count += 1
            versions = self.versions.model_copy(update={"policy_version": f"routed-{self.route_count}"})
            return RequestPolicies(ReleasedPolicySet.empty(), versions)

    rt = ChangingPolicies()
    c, tid = start(rt)
    result = replay(c, tid)
    assert result.status_code == 201, result.text
    assert rt.route_count == 2
    assert result.json()["replay"]["versions"]["policy_version"] == "routed-2"


def test_corrupted_complete_input_refused_before_model_and_purged_input_marked_unknown():
    rt = AuditedReplayRuntime()
    c, tid = start(rt)
    rt.bad_input = True
    result = replay(c, tid)
    assert result.status_code == 400 and len(rt.gateway.calls) == 1
    assert "different input" not in result.text
    rt.bad_input = False
    rt.payloads.rows.clear()
    result = replay(c, tid)
    assert result.status_code == 201, result.text
    conditions = result.json()["conditions"]
    assert not conditions["input_complete"] and conditions["input_match"] is None
    assert "complete_source_input_unavailable" in conditions["limitations"]


def test_corrupted_call_record_is_rejected_before_model_and_report_write_failure_is_closed():
    rt = AuditedReplayRuntime()
    c, tid = start(rt)
    rt.bad_call = True
    result = replay(c, tid)
    assert result.status_code == 400 and len(rt.gateway.calls) == 1
    rt.bad_call = False

    def fail_report(record):
        raise RuntimeError("private report write failure")

    rt.traces.record_replay = fail_report
    result = replay(c, tid)
    assert result.status_code == 503 and result.json()["code"] == "audit_unavailable"
    assert "private report write failure" not in result.text and len(rt.gateway.calls) == 2
