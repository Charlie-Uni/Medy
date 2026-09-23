"""Task routes (M3-02) with the fake runtime and the in-memory store: 202 with the queued task, repeated
Idempotency-Key returns the original task (202) and a different payload is 422, GET is creator-only (404
otherwise), retry is 409 unless failed and retryable, and a completed task carries the TaskResult."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.tasks import InMemoryTaskStore
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api._auth_fixtures import TestIssuer
from tests.unit.api.test_ask_route import ISSUER_OBJ, FakeRuntime
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval

BODY = {
    "skill_name": "label_query",
    "skill_version": "1.0.0",
    "input": {"product": "瑪爾胰", "question": "每日最高建議劑量？"},
}


class TaskRuntime(FakeRuntime):
    def __init__(self):
        super().__init__(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway())
        self.tasks = InMemoryTaskStore(clock=lambda: datetime.now(UTC))

    def task_store(self, conn):
        return self.tasks


def client(rt) -> TestClient:
    return TestClient(create_app(rt), raise_server_exceptions=False)


def auth(sub="user-1") -> dict[str, str]:
    return {"Authorization": "Bearer " + ISSUER_OBJ.token(sub=sub)}


def test_create_get_and_idempotency():
    rt = TaskRuntime()
    c = client(rt)
    r = c.post("/v1/tasks", json=BODY, headers={**auth(), "Idempotency-Key": "abc"})
    assert r.status_code == 202, r.text
    task = r.json()
    assert task["status"] == "queued" and task["result"] is None and task["error"] is None and task["trace_id"] is None
    again = c.post("/v1/tasks", json=BODY, headers={**auth(), "Idempotency-Key": "abc"})
    assert again.status_code == 202 and again.json()["task_id"] == task["task_id"]
    mismatch = c.post(
        "/v1/tasks",
        json={**BODY, "input": {"product": "x", "question": "y"}},
        headers={**auth(), "Idempotency-Key": "abc"},
    )
    assert mismatch.status_code == 422 and mismatch.json()["code"] == "idempotency_payload_mismatch"
    fresh = c.post("/v1/tasks", json=BODY, headers=auth())
    assert fresh.status_code == 202 and fresh.json()["task_id"] != task["task_id"]
    got = c.get(f"/v1/tasks/{task['task_id']}", headers=auth())
    assert got.status_code == 200 and got.json()["task_id"] == task["task_id"]
    assert c.get(f"/v1/tasks/{task['task_id']}").status_code == 401
    assert c.get("/v1/tasks/does-not-exist", headers=auth()).status_code == 404
    assert c.post("/v1/tasks", json={**BODY, "dept": "PV"}, headers=auth()).status_code == 422
    assert (
        c.post(
            "/v1/tasks", json={"skill_name": "Bad Name", "skill_version": "1", "input": {}}, headers=auth()
        ).status_code
        == 422
    )


def test_other_principals_cannot_see_the_task():
    rt = TaskRuntime()
    c = client(rt)
    task_id = c.post("/v1/tasks", json=BODY, headers=auth()).json()["task_id"]
    other = TestIssuer(kid="k1")  # different key: rejected outright
    assert c.get(f"/v1/tasks/{task_id}", headers={"Authorization": "Bearer " + other.token()}).status_code == 401
    # a valid token for an unprovisioned subject is forbidden before any lookup
    assert c.get(f"/v1/tasks/{task_id}", headers=auth(sub="someone-else")).status_code == 403


def test_retry_only_for_failed_retryable_and_completed_carries_the_result():
    rt = TaskRuntime()
    c = client(rt)
    task_id = c.post("/v1/tasks", json=BODY, headers=auth()).json()["task_id"]
    assert c.post(f"/v1/tasks/{task_id}/retry", headers=auth()).status_code == 409
    now = datetime.now(UTC)
    claimed = rt.tasks.claim_next("w1", 60, now)
    rt.tasks.fail(
        task_id,
        "w1",
        claimed.attempts,
        "a" * 32,
        {"code": "dependency_timeout", "message": "x", "trace_id": "a" * 32, "retryable": True},
        now,
    )
    failed = c.get(f"/v1/tasks/{task_id}", headers=auth()).json()
    assert failed["status"] == "failed" and failed["error"]["retryable"] is True and failed["trace_id"] == "a" * 32
    r = c.post(f"/v1/tasks/{task_id}/retry", headers=auth())
    assert r.status_code == 202 and r.json()["status"] == "queued" and r.json()["error"] is None
    claimed2 = rt.tasks.claim_next("w1", 60, now)
    result = {
        "skill": "label_query@1.0.0",
        "status": "completed",
        "reason_codes": [],
        "output": {"claims": []},
        "versions": rt.versions.model_dump(mode="json"),
    }
    rt.tasks.complete(task_id, "w1", claimed2.attempts, "b" * 32, result, now)
    done = c.get(f"/v1/tasks/{task_id}", headers=auth()).json()
    assert done["status"] == "completed" and done["result"]["skill"] == "label_query@1.0.0" and done["error"] is None
    assert c.post(f"/v1/tasks/{task_id}/retry", headers=auth()).status_code == 409
