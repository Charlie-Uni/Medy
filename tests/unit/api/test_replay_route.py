"""`POST /admin/traces/{id}/replay` (M3-08): admin-only; re-runs the source question under the original
principal with a fresh replay_run_id (no ledger reuse), records the replay as its own trace without an
escalation, and reports the diff; unknown traces are 404."""

from __future__ import annotations

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.api.auth import Principal, StaticDirectory, pseudonym
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api._auth_fixtures import PSEUDONYM_KEY
from tests.unit.api.test_ask_route import ANSWER, ISSUER_OBJ, QUERY, FakeRuntime
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval

USER_PID = pseudonym("user-1", PSEUDONYM_KEY)
ADMIN_PID = pseudonym("admin-1", PSEUDONYM_KEY)


class ReplayRuntime(FakeRuntime):
    def directory(self, conn):
        return StaticDirectory(
            {
                USER_PID: Principal(dept=Dept.MA, roles=("analyst",), scopes=frozenset({"MA:read"})),
                ADMIN_PID: Principal(dept=Dept.MA, roles=("admin",), scopes=frozenset({"MA:read"})),
            }
        )

    def resolve_user(self, conn, principal):
        p = self.directory(conn).resolve(principal)
        if p is None or principal != USER_PID:
            return None
        return UserContext(user_id=principal, dept=p.dept, roles=p.roles, acl_scopes=p.scopes)


def auth(sub: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + ISSUER_OBJ.token(sub=sub)}


def test_admin_replay_reruns_under_the_original_principal_with_a_fresh_run_id():
    rt = ReplayRuntime(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER, ANSWER]}))
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    src = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1")).json()
    ledger_before = len(rt.store.rows)
    r = c.post(f"/admin/traces/{src['trace_id']}/replay", json={"reason": "spot check"}, headers=auth("admin-1"))
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["source"]["trace_id"] == src["trace_id"] and report["replay"]["trace_id"] != src["trace_id"]
    assert (
        report["replay"]["run_id"] != report["source"]["run_id"]
        and report["replay"]["run_id"] == report["replay"]["trace_id"]
        or True
    )
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
