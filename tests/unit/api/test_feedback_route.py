"""`POST /v1/feedback` (M3-03 first part): 201 receipt bound to one of the caller's traces, Idempotency-Key with
receipt replay, payload mismatch 422, foreign or unknown trace 404, correction text rules from the contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api.test_ask_route import ANSWER, ISSUER_OBJ, QUERY, FakeRuntime
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval


def auth(sub: str = "user-1") -> dict[str, str]:
    return {"Authorization": "Bearer " + ISSUER_OBJ.token(sub=sub)}


def setup() -> tuple[TestClient, str]:
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    trace_id = c.post("/v1/ask", json={"query": QUERY}, headers=auth()).json()["trace_id"]
    return c, trace_id


def test_feedback_receipt_idempotency_and_mismatch():
    c, trace_id = setup()
    r = c.post(
        "/v1/feedback", json={"trace_id": trace_id, "signal": "down"}, headers={**auth(), "Idempotency-Key": "f1"}
    )
    assert r.status_code == 201, r.text
    receipt = r.json()
    assert receipt["trace_id"] == trace_id and receipt["feedback_id"]
    again = c.post(
        "/v1/feedback", json={"trace_id": trace_id, "signal": "down"}, headers={**auth(), "Idempotency-Key": "f1"}
    )
    assert again.status_code == 201 and again.json() == receipt
    mismatch = c.post(
        "/v1/feedback", json={"trace_id": trace_id, "signal": "up"}, headers={**auth(), "Idempotency-Key": "f1"}
    )
    assert mismatch.status_code == 422 and mismatch.json()["code"] == "idempotency_payload_mismatch"
    fresh = c.post("/v1/feedback", json={"trace_id": trace_id, "signal": "up"}, headers=auth())
    assert fresh.status_code == 201 and fresh.json()["feedback_id"] != receipt["feedback_id"]


def test_feedback_needs_a_visible_trace_and_follows_the_correction_rules():
    c, trace_id = setup()
    assert c.post("/v1/feedback", json={"trace_id": "f" * 32, "signal": "up"}, headers=auth()).status_code == 404
    assert (
        c.post(
            "/v1/feedback", json={"trace_id": trace_id, "signal": "up"}, headers=auth(sub="someone-else")
        ).status_code
        == 403
    )
    assert (
        c.post("/v1/feedback", json={"trace_id": trace_id, "signal": "correction"}, headers=auth()).status_code == 422
    )
    assert (
        c.post(
            "/v1/feedback", json={"trace_id": trace_id, "signal": "up", "correction_text": "x"}, headers=auth()
        ).status_code
        == 422
    )
    ok = c.post(
        "/v1/feedback",
        json={"trace_id": trace_id, "signal": "correction", "correction_text": "剂量应为 8 mg"},
        headers=auth(),
    )
    assert ok.status_code == 201
    assert c.post("/v1/feedback", json={"trace_id": trace_id, "signal": "up"}).status_code == 401
