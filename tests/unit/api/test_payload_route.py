"""M3-07 / DEC-013: the ask route seals its input, evidence snapshot and model output in the request transaction;
the admin payload route decrypts them only for an admin with a purpose and logs the read first."""

from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.domain.common import Dept
from medops.infrastructure.identity import Principal, StaticDirectory, pseudonym
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.api_runtime import ANSWER, ISSUER_OBJ, QUERY, FakeRuntime
from tests.support.harness import LABEL, FakeRetrieval
from tests.support.harness_data import evidence
from tests.support.identity import PSEUDONYM_KEY
from tests.support.payloads import PROVIDER, MemoryPayloads


class PayloadRuntime(FakeRuntime):
    def __init__(self) -> None:
        super().__init__(FakeRetrieval(evidence("c1", LABEL)), FakeModelGateway({"answer": [ANSWER]}))
        self.payloads = MemoryPayloads()

    def directory(self, conn):
        return StaticDirectory(
            {
                pseudonym("user-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=("analyst",), scopes=frozenset({"MA:read"})
                ),
                pseudonym("admin-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=("admin",), scopes=frozenset({"MA:read"})
                ),
            }
        )

    def payload_writer(self, conn):
        return PayloadWriter(store=self.payloads, provider=PROVIDER, retention_days=90)

    @contextmanager
    def restricted_connection(self):
        yield "restricted"

    def payload_reader(self, conn):
        return PayloadReader(store=self.payloads, provider=PROVIDER)


def test_ask_payload_storage_failure_uses_shared_fail_closed_contract():
    rt = PayloadRuntime()

    def broken(*args, **kwargs):
        raise RuntimeError("private storage detail")

    rt.payloads.put = broken
    client = TestClient(create_app(rt), raise_server_exceptions=False)
    response = client.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1"))
    assert response.status_code == 503 and response.json()["code"] == "audit_unavailable"
    assert "answer" not in response.json() and "private storage detail" not in response.text


def auth(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {ISSUER_OBJ.token(sub)}"}


def test_ask_seals_three_payloads_and_only_an_admin_with_a_purpose_can_read_them():
    rt = PayloadRuntime()
    c = TestClient(create_app(rt), raise_server_exceptions=False)
    ask = c.post("/v1/ask", json={"query": QUERY}, headers=auth("user-1"))
    assert ask.status_code == 200
    trace_id = ask.json()["trace_id"]
    kinds = sorted(r["kind"] for r in rt.payloads.list(trace_id))
    assert kinds == ["evidence_snapshot", "input", "model_output"]
    assert all(
        b"glimepiride" not in r["sealed"].ciphertext and b"query" not in r["sealed"].ciphertext
        for r in rt.payloads.rows
    )
    assert (
        c.get(f"/admin/traces/{trace_id}/payload?purpose=incident%20review%2042", headers=auth("user-1")).status_code
        == 403
    )
    assert c.get(f"/admin/traces/{trace_id}/payload?purpose=short", headers=auth("admin-1")).status_code == 400
    assert c.get(f"/admin/traces/{trace_id}/payload?purpose=incident%20review%2042").status_code == 401
    ok = c.get(f"/admin/traces/{trace_id}/payload?purpose=incident%20review%2042", headers=auth("admin-1"))
    assert ok.status_code == 200
    body = ok.json()
    assert body["trace_id"] == trace_id and body["purpose"] == "incident review 42"
    by_kind = {i["kind"]: i for i in body["items"]}
    assert by_kind["input"]["payload"]["query"] == QUERY
    assert by_kind["input"]["payload"]["query_context"] == rt.traces.read_trace(trace_id).query_context.model_dump(
        mode="json"
    )
    assert by_kind["evidence_snapshot"]["payload"]["evidence"][0]["text"]
    assert by_kind["model_output"]["payload"]["answer"]["claims"]
    assert all(i["kek_version"] == "k1" for i in body["items"])
    assert rt.payloads.access == [(pseudonym("admin-1", PSEUDONYM_KEY), trace_id, "incident review 42")]
    assert (
        c.get(f"/admin/traces/{'0' * 32}/payload?purpose=incident%20review%2042", headers=auth("admin-1")).status_code
        == 404
    )
