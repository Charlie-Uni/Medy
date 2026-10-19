"""AGENT-06: current admin + purpose + durable access log before any historical plaintext."""

from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.agent_audit import AgentAuditReader
from medops.core.envelope import StaticKeyProvider
from medops.infrastructure.db.agent_audit import PgAgentAuditStore
from tests.support.agent_audit import audit_runtime
from tests.support.agent_terminal import retrieval_terminal_case, terminal_case
from tests.support.database import database_fixture, run_alembic

db = database_fixture("admin_dsn", scope="module")
audit_policy_db = database_fixture("admin_dsn", scope="function")
PURPOSE = "PUBLIC incident review Agent06"


def request(case, runtime=None, headers=None, **params):
    if runtime is None:
        runtime, headers, _ = audit_runtime(case)
    with TestClient(create_app(runtime), raise_server_exceptions=False) as client:
        return client.get(
            f"/admin/agent-runs/{case['context'].identity.run_id}/audit",
            params={"purpose": PURPOSE, **params},
            headers=headers,
        )


def logs(case):
    with psycopg.connect(case["db"]["users"]["admin"]) as conn:
        return conn.execute(
            "select principal,purpose from payload_access_log where trace_id=%s order by log_id",
            (case["context"].identity.trace_id,),
        ).fetchall()


def completed(db, kind="finish"):
    case, fake = terminal_case(db, kind)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
    return case, fake, result


def test_admin_reads_real_actions_reasons_evidence_receipts_versions_without_any_new_call(db):
    case, fake = retrieval_terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
    assert result.run.status == "completed", (result.material.reason, len(fake.calls))
    rt, headers, pid = audit_runtime(case)  # MA admin, original run belongs to PV.
    before = len(fake.calls)
    response = request(case, rt, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert body["trace_id"] == case["context"].identity.trace_id and body["purpose"] == PURPOSE
    head, *events = body["items"]
    assert head["payload"]["control"]["terminal_status"] == "completed"
    assert head["payload"]["body"]["run"]["status"] == "running"
    assert head["payload"]["body"]["run"]["context"] == case["context"].model_dump(mode="json")
    assert head["payload"]["head"]["budget_state"]["snapshot"]["calls"] == before
    assert any(e["kind"] == "tool_committed" for e in events)
    assert sum(e["kind"] == "call_admitted" for e in events) == before
    assert sum(e["kind"] == "call_settled" for e in events) == before
    terminal = next(e for e in events if e["payload"]["event_id"] == head["payload"]["control"]["terminal_ref"])
    assert terminal["payload"]["body"]["envelope"]["delivery"] == result.model_dump(mode="json")
    history = head["payload"]["body"]["loop"]["history"]
    assert history and history[0]["action"]["proposal"]["action"] == "search_documents"
    assert logs(case) == [(pid, PURPOSE)]
    assert len(fake.calls) == before and not rt.gateway.calls
    again = request(case, rt, headers)
    assert again.status_code == 200 and again.json() == body
    assert logs(case) == [(pid, PURPOSE), (pid, PURPOSE)]


@pytest.mark.parametrize("kind", ["clarify", "escalate"])
def test_saved_stop_material_is_available_as_historical_audit(db, kind):
    case, fake, result = completed(db, kind)
    response = request(case)
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["payload"]["control"]["terminal_status"] == result.run.status
    assert len(fake.calls) == 2 and len(logs(case)) == 1


def test_current_prompt_or_tool_versions_do_not_prevent_reading_original_historical_material(db, monkeypatch):
    import medops.application.agent_loop_state as current_execution
    from medops.application.agent_runtime_state import RuntimeBody

    case, fake, result = completed(db)
    monkeypatch.setattr(current_execution, "planning_prompt_sha256", lambda: "f" * 64)
    monkeypatch.setattr(current_execution, "tool_contract_sha256", lambda: "e" * 64)
    response = request(case)
    assert response.status_code == 200, response.text
    original = response.json()["items"][0]["payload"]["body"]["run"]["context"]
    assert original == case["context"].model_dump(mode="json")
    assert original["versions"]["planning_prompt_sha256"] != "f" * 64
    assert result.run.status == "completed" and len(fake.calls) == 2 and len(logs(case)) == 1
    with pytest.raises(ValueError, match="invalid_agent_loop_state"):
        RuntimeBody.model_validate(response.json()["items"][0]["payload"]["body"])


@pytest.mark.parametrize("roles", [("analyst",), ("approver",), ()])
def test_other_business_roles_cannot_open_the_restricted_reader(db, roles):
    case, _, _ = completed(db)
    rt, headers, _ = audit_runtime(case, roles=roles)
    rt.agent_audit_reader = lambda _: pytest.fail("non-admin reached the reader")
    assert request(case, rt, headers).status_code == 403
    assert not logs(case)


def test_missing_identity_is_rejected_before_restricted_access(db):
    case, _, _ = completed(db)
    rt, _, _ = audit_runtime(case)
    rt.agent_audit_reader = lambda _: pytest.fail("anonymous caller reached the reader")
    assert request(case, rt, {}).status_code == 401
    assert not logs(case)


@pytest.mark.parametrize("purpose", ["short", " " * 10, "x" * 501])
def test_invalid_purpose_never_reads_or_decrypts_material(db, purpose):
    case, _, _ = completed(db)
    rt, headers, _ = audit_runtime(case)
    rt.agent_audit_reader = lambda conn: AgentAuditReader(
        type("NoRead", (), {"load": lambda *_: pytest.fail("invalid purpose loaded material")})(), case["provider"]
    )
    assert request(case, rt, headers, purpose=purpose).status_code == 400
    assert not logs(case)


def test_absent_runtime_and_invalid_run_identifier_do_not_return_material(db):
    case, _ = terminal_case(db)
    assert request(case).status_code == 404
    rt, headers, _ = audit_runtime(case)
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        invalid = client.get("/admin/agent-runs/not-a-uuid/audit", params={"purpose": PURPOSE}, headers=headers)
    assert invalid.status_code == 400 and not logs(case)


def test_revocation_between_initial_authentication_and_restricted_connection_is_rechecked(db):
    case, _, _ = completed(db)
    rt, headers, pid = audit_runtime(case)
    original = rt.restricted_connection

    @contextmanager
    def revoked():
        with psycopg.connect(db["owner"]) as conn:
            conn.execute("update principals set active=false where sub_pseudonym=%s", (pid,))
        with original() as conn:
            yield conn

    rt.restricted_connection = revoked
    rt.agent_audit_reader = lambda _: pytest.fail("revoked admin reached plaintext")
    assert request(case, rt, headers).status_code == 403 and not logs(case)


def test_wrong_fact_database_is_rejected_before_reader(db, scratch_database):
    case, _, _ = completed(db)
    rt, headers, _ = audit_runtime(case)

    @contextmanager
    def wrong_database():
        with psycopg.connect(scratch_database) as conn, conn.transaction():
            yield conn

    rt.restricted_connection = wrong_database
    rt.agent_audit_reader = lambda _: pytest.fail("wrong fact database reached reader")
    assert request(case, rt, headers).status_code == 403 and not logs(case)


@pytest.mark.parametrize("fault", ["log", "key", "commit"])
def test_no_plaintext_leaves_when_logging_decryption_or_commit_fails(db, fault):
    case, _, _ = completed(db)
    rt, headers, _ = audit_runtime(case)
    if fault == "log":

        class Broken(PgAgentAuditStore):
            def log_access(self, *args):
                super().log_access(*args)
                raise RuntimeError("PRIVATE_AUDIT_LOG_FAILURE")

        rt.agent_audit_reader = lambda conn: AgentAuditReader(Broken(conn), case["provider"])
    elif fault == "key":
        rt._key_provider = StaticKeyProvider({"PUBLIC-test-key": b"W" * 32}, "PUBLIC-test-key")
    else:
        original = rt.restricted_connection

        @contextmanager
        def failed_commit():
            with original() as conn:
                yield conn
                raise RuntimeError("PRIVATE_AUDIT_COMMIT_FAILURE")

        rt.restricted_connection = failed_commit
    response = request(case, rt, headers)
    assert response.status_code == (500 if fault == "commit" else 503)
    assert "items" not in response.json() and "PRIVATE_AUDIT" not in response.text
    assert case["context"].narrative not in response.text and not logs(case)


@pytest.mark.parametrize("change", ["head", "event"])
def test_concurrent_head_or_event_change_rejects_the_entire_snapshot(db, change):
    case, _ = terminal_case(db)
    rt, headers, _ = audit_runtime(case)
    faults = []
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        d = execution.driver

        class Changing(PgAgentAuditStore):
            reads = 0

            def _advance(self):
                try:
                    updated = None
                    with d.connection() as conn:
                        store = d._store(conn)
                        head = store.read()
                        if change == "head":
                            # A real next checkpoint has a fresh ID; reusing the old
                            # ID is correctly rejected by the existing replay guard.
                            budget = head.budget.model_copy(update={"checkpoint_id": uuid4()})
                            updated = store.save(d.lease, head.body, budget, expected_revision=head.revision)
                        else:
                            store.append(
                                d.lease,
                                "late_stop",
                                uuid4(),
                                {"kind": "PUBLIC-audit-race"},
                                retained_until=head.retained_until,
                            )
                    if updated is not None:
                        d.head = updated
                except Exception as exc:
                    faults.append((type(exc).__name__, getattr(exc, "reason", None)))
                    raise

            def _head(self, *args):
                if change == "head":
                    self.reads += 1
                    if self.reads == 2:
                        self._advance()
                return super()._head(*args)

            def _manifest(self, *args):
                if change == "event":
                    self.reads += 1
                    if self.reads == 2:
                        self._advance()
                return super()._manifest(*args)

        rt.agent_audit_reader = lambda conn: AgentAuditReader(Changing(conn), case["provider"])
        response = request(case, rt, headers)
        assert response.status_code == 409 and response.json()["code"] == "version_conflict", faults
    assert not logs(case)


def test_size_and_event_count_are_checked_before_ciphertext_decryption(db, monkeypatch):
    import medops.infrastructure.db.agent_audit as storage

    case, _, _ = completed(db)
    monkeypatch.setattr(storage, "MAX_AGENT_AUDIT_BYTES", 1)
    assert request(case).status_code == 503
    monkeypatch.setattr(storage, "MAX_AGENT_AUDIT_BYTES", 32 * 1024 * 1024)
    monkeypatch.setattr(storage, "MAX_AGENT_AUDIT_EVENTS", 1)
    assert request(case).status_code == 503 and not logs(case)


def test_expired_ciphertext_is_not_returned_even_before_retention_purge(db):
    case, _, _ = completed(db)
    # Simulate an old retained backup in this disposable database, not a live writer path.
    with psycopg.connect(db["owner"]) as conn:
        conn.execute("alter table agent_runtime_heads disable trigger user")
        conn.execute(
            "update agent_runtime_heads set retained_until=clock_timestamp()-interval '1 second' where run_id=%s",
            (case["context"].identity.run_id,),
        )
        conn.execute("alter table agent_runtime_heads enable trigger user")
    assert request(case).status_code == 404 and not logs(case)


def test_authenticated_ciphertext_cannot_be_relabelled_as_another_event(db):
    case, _, _ = completed(db)
    rt, headers, _ = audit_runtime(case)

    class Relabelled(PgAgentAuditStore):
        def load(self, *args):
            bundle = super().load(*args)
            first, second, *rest = bundle.items
            # AAD remains bound to the real original event; substituting a different sealed body fails.
            return replace(bundle, items=(first, replace(second, sealed=first.sealed), *rest))

    rt.agent_audit_reader = lambda conn: AgentAuditReader(Relabelled(conn), case["provider"])
    response = request(case, rt, headers)
    assert response.status_code == 503 and "items" not in response.json() and not logs(case)


def test_restricted_reader_cannot_mutate_live_heads_events_or_control(db):
    case, _, _ = completed(db)
    run_id = case["context"].identity.run_id
    with psycopg.connect(db["users"]["app"]) as conn:
        conn.execute("select set_config('medops.dept','MA',true)")
        assert conn.execute("select count(*) from agent_runtime_heads where run_id=%s", (run_id,)).fetchone()[0] == 0
        conn.execute("select set_config('medops.dept','PV',true)")
        assert conn.execute("select count(*) from agent_runtime_heads where run_id=%s", (run_id,)).fetchone()[0] == 1
    with psycopg.connect(db["users"]["restricted"]) as conn:
        for table in ("agent_run_control", "agent_runtime_heads", "agent_runtime_events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(f"update {table} set run_id=run_id where run_id=%s", (run_id,))
        assert conn.execute("delete from agent_runtime_heads where run_id=%s", (run_id,)).rowcount == 0
        assert conn.execute("delete from agent_runtime_events where run_id=%s", (run_id,)).rowcount == 0
        assert conn.execute("select count(*) from agent_runtime_heads where run_id=%s", (run_id,)).fetchone()[0] == 1


def test_new_read_policies_round_trip_without_rewriting_existing_ciphertext(audit_policy_db):
    # A retained execution journal without a business terminal. Retained
    # terminal Traces must prevent downgrade and may not be deleted here.
    db = audit_policy_db
    case, _ = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
    run_id = case["context"].identity.run_id
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute("select count(*) from traces where kind='agent'").fetchone()[0] == 0
        before = conn.execute(
            "select ciphertext,nonce,dek_wrapped,kek_version,revision from agent_runtime_heads where run_id=%s",
            (run_id,),
        ).fetchone()
    try:
        run_alembic(db["owner"], "downgrade", "0030")
        with psycopg.connect(db["users"]["restricted"]) as conn:
            assert (
                conn.execute("select count(*) from agent_runtime_heads where run_id=%s", (run_id,)).fetchone()[0] == 0
            )
    finally:
        run_alembic(db["owner"], "upgrade", "head")
    with psycopg.connect(db["owner"]) as conn:
        after = conn.execute(
            "select ciphertext,nonce,dek_wrapped,kek_version,revision from agent_runtime_heads where run_id=%s",
            (run_id,),
        ).fetchone()
    assert before == after and request(case).status_code == 200
