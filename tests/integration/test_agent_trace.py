"""Real Agent terminal/Trace/feedback transactions; synthetic inputs, no hosted calls."""

import json
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.agent_terminal import TerminalEnvelope
from medops.application.agent_trace import AgentTraceMetadata, terminal_trace
from medops.application.contracts import ReplayRequest
from medops.application.replay import ReplayService
from medops.core.errors import BusinessError, InfrastructureError
from medops.infrastructure.db.agent_control import PgAgentControl
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.infrastructure.llm.meter import MeteredGateway
from medops.infrastructure.observability import ScoreQueue, harvest_feedback
from medops.loop.observe import PgSignalSource, classify
from tests.support.agent_audit import audit_runtime
from tests.support.agent_runtime import reopen_case, runtime_case
from tests.support.agent_terminal import retrieval_terminal_case, terminal_case
from tests.support.audit_records import trace
from tests.support.database import database_fixture, run_alembic

db = database_fixture("admin_dsn", scope="module")


def saved_trace(case):
    with psycopg.connect(case["db"]["owner"]) as conn:
        return conn.execute(
            "select run_id,kind,task_id,principal,dept::text,query,outcome,reason_codes,versions,"
            "evidence_chunk_ids,cited_chunk_ids,model_calls,tokens,cost_usd,duration_ms,agent_metadata "
            "from traces where trace_id=%s",
            (case["context"].identity.trace_id,),
        ).fetchone()


def owner_case(db, kind="finish"):
    base, fake = terminal_case(db, kind)
    rt, headers, pid = audit_runtime(base, roles=())
    with psycopg.connect(db["owner"]) as conn:
        conn.execute("update principals set dept='PV',scopes=array['PV:read'] where sub_pseudonym=%s", (pid,))
    context = base["context"].model_copy(
        update={"principal": base["context"].principal.model_copy(update={"user_id": pid})}
    )
    case = reopen_case(
        db,
        base["run"].model_copy(update={"context": context}),
        base["binding"],
        base["chunk"],
        fake,
        final_config=base["runtime"].resources(base["context"], MeteredGateway(fake)).final_config,
    )
    case["run"] = case["runtime"].new_run(context)
    return case, fake, rt, headers


@pytest.mark.parametrize(
    "kind,status", [("finish", "completed"), ("clarify", "awaiting_clarification"), ("escalate", "escalated")]
)
def test_real_terminal_trace_has_original_identity_versions_accounting_and_no_body(db, kind, status):
    case, fake = terminal_case(db, kind)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
        assert result.run.status == status
        assert execution.finish() == result
    row = saved_trace(case)
    identity = case["context"].identity
    assert row[:8] == (
        identity.run_id.hex,
        "agent",
        identity.task_id,
        case["context"].principal.user_id,
        "PV",
        "",
        status,
        [result.material.reason],
    )
    assert row[8] == case["context"].versions.versions.model_dump(mode="json")
    meta = AgentTraceMetadata.model_validate(row[15])
    assert (meta.case_id, meta.task_id, meta.run_id, meta.attempt_id) == (
        identity.case_id,
        identity.task_id,
        identity.run_id,
        identity.attempt_id,
    )
    assert meta.versions == case["context"].versions
    assert meta.context_sha256 == result.run.terminal.binding.conditions_sha256
    assert meta.terminal_material_ref == result.run.terminal.material_ref
    assert meta.terminal_material_sha256 == result.run.terminal.material_sha256
    assert meta.accounting_complete and meta.pending_calls == 0
    assert row[11] == meta.accounting.calls == len(fake.calls) == 2
    assert row[12] == meta.accounting.accounted_tokens == result.run.budget.accounted_tokens
    assert float(row[13]) == round(meta.accounting.accounted_cost_usd, 6)
    assert row[14] == (result.run.stopped_at - result.run.started_at).total_seconds() * 1000
    with psycopg.connect(db["owner"]) as conn:
        assert (
            conn.execute("select terminal_ref from agent_run_control where run_id=%s", (identity.run_id,)).fetchone()[0]
            == meta.terminal_event_id
        )
        assert conn.execute("select count(*) from traces where trace_id=%s", (identity.trace_id,)).fetchone()[0] == 1
        assert (
            conn.execute("select count(*) from trace_spans where trace_id=%s", (identity.trace_id,)).fetchone()[0] == 0
        )
    serialized = json.dumps(row[15])
    assert case["context"].narrative not in serialized
    for forbidden in ("narrative", "question", "guideline_claims", "prompt", "messages", "response", "evidence_text"):
        assert forbidden not in row[15]
    assert case["runtime"].result(case["context"], user=case["context"].principal) == result
    assert len(fake.calls) == 2


def test_supported_joint_citations_are_projected_as_ids_without_copying_the_text(db):
    case, fake = retrieval_terminal_case(db, joint=True)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
    assert result.run.status == "completed", result.material.reason
    row = saved_trace(case)
    assert set(row[9]) == set(row[10]) == set(case["chunks"])
    assert len(row[9]) == len(row[10]) == 2
    assert all(e.text not in json.dumps(row[15]) for e in result.material.review.evidence)
    assert row[11] == len(fake.calls)


@pytest.mark.parametrize("failure", ["model", "cancel"])
def test_failed_and_cancelled_terminals_are_traced_with_their_real_status(db, failure):
    if failure == "model":
        fake = FakeModelGateway({"agent_plan": [ModelTimeout("PUBLIC private provider text")]})
        case = runtime_case(db, fake)
    else:
        case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        if failure == "cancel":
            with psycopg.connect(db["owner"]) as conn:
                conn.execute(
                    "update agent_run_control set cancelled_at=clock_timestamp() where run_id=%s",
                    (case["context"].identity.run_id,),
                )
        result = execution.finish()
    expected = "failed" if failure == "model" else "cancelled"
    assert result.run.status == expected
    row = saved_trace(case)
    meta = AgentTraceMetadata.model_validate(row[15])
    assert row[6] == meta.status == expected and row[11] == len(fake.calls)
    assert "PUBLIC private provider text" not in json.dumps(row[15])
    assert meta.accounting.accounted_tokens == result.run.budget.accounted_tokens
    assert meta.accounting.reserved_tokens == result.run.budget.reserved_tokens
    assert meta.accounting.known_tokens <= meta.accounting.accounted_tokens


def test_internal_finish_request_without_business_commit_creates_no_fake_trace(db):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        assert execution.run().reason == "completed"
    assert saved_trace(case) is None and len(fake.calls) == 1


def test_budget_free_text_never_enters_the_plain_trace_projection(db):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.execute()
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        body = next(e.body for e in execution.driver._store(conn).events() if e.body.get("kind") == "business_terminal")
    original = TerminalEnvelope.model_validate(body["envelope"])
    private = "PRIVATE_SYNTHETIC_BUDGET_REASON_NOT_FOR_TRACE"
    budget = original.budget.model_copy(
        update={"snapshot": original.budget.snapshot.model_copy(update={"blocked_reason": private})}
    )
    projected = terminal_trace(original.model_copy(update={"budget": budget}), event_id=uuid4())
    assert private not in json.dumps(projected.agent_metadata)
    metadata = AgentTraceMetadata.model_validate(projected.agent_metadata)
    assert metadata.accounting.blocked is True
    assert metadata.accounting.accounted_cost_usd == original.budget.snapshot.accounted_cost_usd
    assert metadata.accounting.known_cost_usd == original.budget.snapshot.known_cost_usd
    assert metadata.accounting.reserved_cost_usd == original.budget.snapshot.reserved_cost_usd
    assert len(fake.calls) == 2


@pytest.mark.parametrize("after_insert", [False, True])
def test_trace_write_failure_rolls_back_terminal_control_event_and_summary(db, monkeypatch, after_insert):
    case, fake = terminal_case(db)
    original = PgTraceStore.record

    def broken(store, record, escalation):
        if after_insert:
            original(store, record, escalation)
        raise RuntimeError("PUBLIC private database failure")

    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        execution.review()
        with monkeypatch.context() as patch:
            patch.setattr(PgTraceStore, "record", broken)
            with pytest.raises(InfrastructureError) as failure:
                execution.finish()
            assert failure.value.code.value == "audit_unavailable"
            assert execution.delivery is None
    assert saved_trace(case) is None
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select terminal_ref from agent_run_control where run_id=%s", (case["context"].identity.run_id,)
        ).fetchone() == (None,)
        assert (
            conn.execute(
                "select count(*) from feedback where trace_id=%s", (case["context"].identity.trace_id,)
            ).fetchone()[0]
            == 0
        )
    with case["connection"]() as conn:
        conn.execute("select set_config('medops.dept','PV',true)")
        assert not any(e.body.get("kind") == "business_terminal" for e in execution.driver._store(conn).events())
    with case["runtime"].recover(case["context"]) as recovered:
        assert recovered.execute().run.status == "completed"
    assert saved_trace(case)[6] == "completed" and len(fake.calls) == 2


@pytest.mark.parametrize("after_commit", [False, True])
def test_commit_acknowledgement_loss_preserves_trace_terminal_atomicity_and_no_rebilling(db, monkeypatch, after_commit):
    case, fake = terminal_case(db)
    flag = {"armed": False}
    seal = PgAgentControl.seal

    def armed(*args, **kwargs):
        value = seal(*args, **kwargs)
        flag["armed"] = True
        return value

    with case["runtime"].start(case["run"]) as execution:
        execution.run()
        execution.review()
        connection = execution.driver.connection

        @contextmanager
        def unreliable():
            with connection() as conn:
                yield conn
                if flag["armed"]:
                    flag["armed"] = False
                    if after_commit:
                        conn.commit()
                    raise RuntimeError("PUBLIC terminal acknowledgement lost")

        with monkeypatch.context() as patch:
            patch.setattr(PgAgentControl, "seal", armed)
            execution.driver.connection = unreliable
            with pytest.raises(RuntimeError, match="acknowledgement"):
                execution.finish()
            assert execution.delivery is None
            execution.driver.connection = connection
    assert (saved_trace(case) is not None) == after_commit
    if after_commit:
        assert case["runtime"].result(case["context"], user=case["context"].principal).run.status == "completed"
    else:
        with case["runtime"].recover(case["context"]) as recovered:
            assert recovered.execute().run.status == "completed"
    assert saved_trace(case)[6] == "completed" and len(fake.calls) == 2


@pytest.mark.parametrize("kind", ["finish", "clarify", "escalate"])
def test_real_http_feedback_owns_agent_trace_is_idempotent_and_rejects_foreign_revoked_or_anonymous(db, kind):
    case, fake, rt, headers = owner_case(db, kind)
    with case["runtime"].start(case["run"]) as execution:
        result = execution.execute()
    assert (
        result.run.status == {"finish": "completed", "clarify": "awaiting_clarification", "escalate": "escalated"}[kind]
    )
    payload = {"trace_id": case["context"].identity.trace_id, "signal": "down"}
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        idem = {**headers, "Idempotency-Key": "PUBLIC-agent-feedback"}
        first = client.post("/v1/feedback", json=payload, headers=idem)
        assert first.status_code == 201, first.text
        again = client.post("/v1/feedback", json=payload, headers=idem)
        assert again.status_code == 201 and again.json() == first.json()
        assert client.post("/v1/feedback", json={**payload, "signal": "up"}, headers=idem).status_code == 422
        assert client.post("/v1/feedback", json=payload).status_code == 401
        _, foreign, _ = audit_runtime(case)
        assert client.post("/v1/feedback", json=payload, headers=foreign).status_code == 404
        with psycopg.connect(db["owner"]) as conn:
            conn.execute(
                "update principals set active=false where sub_pseudonym=%s", (case["context"].principal.user_id,)
            )
        assert client.post("/v1/feedback", json=payload, headers=idem).status_code == 403
    with psycopg.connect(db["owner"]) as conn:
        assert (
            conn.execute("select count(*) from feedback where trace_id=%s", (payload["trace_id"],)).fetchone()[0] == 1
        )
    assert len(fake.calls) == 2 and not rt.gateway.calls


def test_http_feedback_cannot_see_uncommitted_agent_trace_then_uses_same_key_after_commit(db, monkeypatch):
    case, fake, rt, headers = owner_case(db)
    payload = {"trace_id": case["context"].identity.trace_id, "signal": "up"}
    headers = {**headers, "Idempotency-Key": "PUBLIC-before-commit"}
    original = PgTraceStore.record
    seen = []
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:

        def record(store, summary, escalation):
            original(store, summary, escalation)
            seen.append(client.post("/v1/feedback", json=payload, headers=headers).status_code)

        with monkeypatch.context() as patch:
            patch.setattr(PgTraceStore, "record", record)
            with case["runtime"].start(case["run"]) as execution:
                result = execution.execute()
        assert result.run.status == "completed" and seen == [404]
        response = client.post("/v1/feedback", json=payload, headers=headers)
        assert response.status_code == 201, response.text
    assert len(fake.calls) == 2


def test_feedback_export_keeps_agent_trace_and_stable_score_id_without_correction_or_query(db, tmp_path):
    case, fake, rt, headers = owner_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.execute()
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/feedback",
            json={
                "trace_id": case["context"].identity.trace_id,
                "signal": "correction",
                "correction_text": "PRIVATE_PUBLIC_SYNTHETIC_CORRECTION",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
    path = tmp_path / "agent-feedback.db"
    with psycopg.connect(db["owner"]) as conn:
        conn.read_only = True
        queue = ScoreQueue(path, "PUBLIC-agent-project")
        harvest_feedback(conn, queue)
        before = queue.conn.execute("select id,payload from scores order by id").fetchall()
        queue.close()
        queue = ScoreQueue(path, "PUBLIC-agent-project")
        harvest_feedback(conn, queue)
        harvest_feedback(conn, queue)
        after = queue.conn.execute("select id,payload from scores order by id").fetchall()
        queue.close()
    assert before == after
    matches = [json.loads(payload) for _, payload in after if case["context"].identity.trace_id in payload]
    assert len(matches) == 1
    assert "PRIVATE_PUBLIC_SYNTHETIC_CORRECTION" not in str(after) and case["context"].narrative not in str(after)
    with psycopg.connect(db["users"]["loop"]) as conn:
        conn.read_only = True
        signals = PgSignalSource(conn).for_trace(case["context"].identity.trace_id)
        assert signals.kind == "agent" and classify(signals) == (None, ())
    assert len(fake.calls) == 2


def test_existing_ask_replay_explicitly_refuses_agent_before_building_dependencies(db):
    case, fake = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.execute()

    def forbidden(*_args):
        pytest.fail("Agent must not enter Ask replay")

    with psycopg.connect(db["users"]["app"]) as conn:
        service = ReplayService(store=PgTraceStore(conn), build_deps=forbidden, resolve_user=forbidden)
        with pytest.raises(BusinessError, match="Ask traces only"):
            service.replay(
                case["context"].principal,
                case["context"].identity.trace_id,
                ReplayRequest(reason="PUBLIC inspect agent"),
            )
    assert len(fake.calls) == 2


def test_agent_trace_collision_fails_closed_without_overwriting_another_summary(db):
    case, fake = terminal_case(db)
    occupied = replace(trace(case["context"].identity.trace_id), query="PUBLIC pre-existing unrelated Ask")
    with psycopg.connect(db["users"]["app"]) as conn:
        PgTraceStore(conn).record(occupied, None)
    with case["runtime"].start(case["run"]) as execution:
        with pytest.raises(InfrastructureError):
            execution.execute()
    assert saved_trace(case)[1] == "ask" and saved_trace(case)[5] == occupied.query
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select terminal_ref from agent_run_control where run_id=%s", (case["context"].identity.run_id,)
        ).fetchone() == (None,)
    assert len(fake.calls) == 2


@pytest.mark.parametrize("metadata", [None, {}, {"schema_version": "wrong"}])
def test_new_agent_trace_requires_metadata_but_legacy_rows_cannot_claim_agent_only_status(db, metadata):
    with psycopg.connect(db["users"]["app"]) as conn:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            PgTraceStore(conn).record(
                replace(trace(uuid4().hex), kind="agent", outcome="completed", agent_metadata=metadata), None
            )
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            PgTraceStore(conn).record(replace(trace(uuid4().hex), outcome="awaiting_clarification"), None)


def test_trace_append_only_and_metadata_are_preserved_and_downgrade_refuses_retained_rows(db):
    case, _ = terminal_case(db)
    with case["runtime"].start(case["run"]) as execution:
        execution.execute()
    before = saved_trace(case)
    for sql in ("update traces set agent_metadata='{}' where trace_id=%s", "delete from traces where trace_id=%s"):
        with psycopg.connect(db["owner"]) as conn:
            with pytest.raises(psycopg.Error):
                conn.execute(sql, (case["context"].identity.trace_id,))
    with pytest.raises(Exception, match="retained Agent traces prevent downgrade"):
        run_alembic(db["owner"], "downgrade", "0031")
    assert saved_trace(case) == before


def test_migration_round_trip_and_legacy_store_without_new_column(scratch_database):
    run_alembic(scratch_database, "upgrade", "head")
    run_alembic(scratch_database, "downgrade", "0031")
    with psycopg.connect(scratch_database) as conn:
        old = trace(uuid4().hex)
        PgTraceStore(conn).record(old, None)
        assert conn.execute("select query from traces where trace_id=%s", (old.trace_id,)).fetchone() == (old.query,)
        assert (
            conn.execute(
                "select count(*) from information_schema.columns where table_name='traces' and column_name='agent_metadata'"
            ).fetchone()[0]
            == 0
        )
    run_alembic(scratch_database, "upgrade", "head")
    with psycopg.connect(scratch_database) as conn:
        assert conn.execute("select agent_metadata from traces where trace_id=%s", (old.trace_id,)).fetchone() == (
            None,
        )
