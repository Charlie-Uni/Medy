"""Agent current-condition diagnosis using real transactions and offline providers."""

import hashlib
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from medops.application.agent_replay import AgentReplayRequest, replay_identity
from medops.bootstrap.agent_replay import production_agent_replay
from medops.core.errors import BusinessError, InfrastructureError
from medops.infrastructure.db.agent_runtime import PgAgentRuntime
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from tests.support.agent_audit import audit_runtime
from tests.support.agent_runtime import reopen_case
from tests.support.agent_terminal import PublicRetrievalAgent, retrieval_terminal_case, terminal_case
from tests.support.audit_records import trace
from tests.support.database import database_fixture
from tests.support.documents import document, job, source_object
from tests.support.harness import FakeRetrieval
from tests.support.pv_agent import draft
from tests.support.pv_loop import terminal
from tests.support.pv_review import material_verdict

db = database_fixture("admin_dsn", scope="module")
PURPOSE = "PUBLIC Agent06 diagnostic review"


class Retrieval:
    def __init__(self, case):
        self.case = case

    def build(self, *args, **kwargs):
        from medops.retrieval.recheck import recheck_candidates

        _, user, context, *_ = args
        with kwargs["connection_for_user"](user) as conn:
            fresh = recheck_candidates(
                conn,
                self.case.get("chunks", (self.case["chunk"],)),
                as_of=context.as_of,
                allow_historical=context.historical_requested,
            )
        return FakeRetrieval(*fresh.evidence)

    def reranker_for(self, output):
        return SimpleNamespace(score=lambda q, texts: [1.0] * len(texts))


def prepared(db, kind="finish", *, retrieval=False):
    case, original_fake = retrieval_terminal_case(db) if retrieval else terminal_case(db, kind)
    if kind != "finish":
        # Preserve a REAL ambiguity after current-source resolution. A single
        # exact document ID would legitimately become resolved during diagnosis.
        title = "PUBLIC replay ambiguous " + uuid4().hex
        with psycopg.connect(db["owner"]) as conn:
            conn.execute("update documents set title=%s where doc_id=%s", (title, case["doc"]))
            src = source_object(conn, uuid4().int % 2**55)
            conn.execute("update source_objects set integrity_status='verified' where source_object_id=%s", (src,))
            second = document(
                conn,
                src,
                job(conn, src),
                status="active",
                parse_quality="trusted",
                owner_dept="PV",
                doc_type="guideline",
                version="PUBLIC v2",
                title=title,
                effective_from=case["context"].query_context.as_of,
            )
            conn.execute(
                "insert into document_acl(doc_id,dept,granted_by) values (%s,'PV','PUBLIC-replay-test')", (second,)
            )
        context = case["context"].model_copy(
            update={"source_scope": case["context"].source_scope.model_copy(update={"requested_document": title})}
        )
        final = case["runtime"].resources(case["context"], None).final_config
        case = reopen_case(
            db,
            case["run"].model_copy(update={"context": context}),
            case["binding"],
            case["chunk"],
            original_fake,
            final_config=final,
        )
        case["run"] = case["runtime"].new_run(context)
    with case["runtime"].start(case["run"]) as execution:
        delivery = execution.execute()
    expected = {"finish": "completed", "clarify": "awaiting_clarification", "escalate": "escalated"}[kind]
    assert delivery.run.status == expected, (
        delivery.material.reason,
        len(original_fake.calls),
        execution.heartbeat.failure_type,
    )
    runtime, headers, admin = audit_runtime(case)
    runtime.versions = case["context"].versions.versions
    runtime._retrieval_services = Retrieval(case)
    final_config = case["runtime"].resources(case["context"], None).final_config
    service = production_agent_replay(
        runtime,
        config=case["runtime"].config,
        final_config=final_config,
        database_binding=case["binding"],
        rubric_sha256=case["context"].versions.rubric_sha256,
        lease_s=10,
    )
    if retrieval:
        runtime.gateway = PublicRetrievalAgent()
    elif kind == "finish":
        body = terminal("finish")
        body["proposal"]["draft"] = draft()
        body["proposal"]["draft"]["guideline_claims"] = []
        runtime.gateway = FakeModelGateway(
            {
                "agent_plan": [body],
                "agent_final_material": [
                    material_verdict(
                        draft_value=body["proposal"]["draft"],
                        requirements=[dict(requirement_id="event", complete=True)],
                    )
                ],
            }
        )
    else:
        # Reuse the public reactive terminal replies, not original run receipts.
        from tests.support.agent_terminal import stop_verdict

        body = terminal(kind)
        if kind == "escalate":
            body["proposal"]["reason"] = "source_ambiguous"
        runtime.gateway = FakeModelGateway({"agent_plan": [body], "agent_final_stop": [stop_verdict(kind)]})
    command = AgentReplayRequest(replay_id=uuid4(), reason=PURPOSE)
    return case, original_fake, delivery, runtime, headers["Authorization"], admin, service, command


def test_current_diagnosis_has_fresh_ids_preserved_input_real_trace_and_stable_report(db):
    case, original, delivery, runtime, authorization, admin, service, command = prepared(db)
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert report.replay.metadata.status == "completed", report.replay.metadata.reason
    assert report.conditions.input_complete and report.conditions.input_match
    assert report.conditions.identity_match and report.conditions.evidence_match
    assert report.conditions.original_conditions_reproduced is False
    assert report.conditions.corpus_match is None and report.conditions.source_artifacts_match is None
    assert not report.changed and report.source_scope_match and report.profile_match
    assert report.replay.metadata.run_id == replay_identity(command.replay_id).run_id
    for name in ("case_id", "task_id", "run_id", "attempt_id"):
        assert getattr(report.source.metadata, name) != getattr(report.replay.metadata, name)
    assert report.source.trace_id != report.replay.trace_id
    assert len(original.calls) == len(runtime.gateway.calls) == 2
    serialized = report.model_dump_json()
    assert case["context"].narrative not in serialized and PURPOSE not in serialized
    assert all(r.description not in serialized for r in case["context"].requirements)
    with psycopg.connect(db["owner"]) as conn:
        stored = conn.execute(
            "select report,requested_by,reason from replays where replay_id=%s", (command.replay_id,)
        ).fetchone()
        assert stored[0] == report.model_dump(mode="json") and stored[1] == admin and PURPOSE not in stored[2]
        assert conn.execute("select kind from traces where trace_id=%s", (report.replay.trace_id,)).fetchone() == (
            "agent",
        )
        assert (
            conn.execute(
                "select count(*) from payload_access_log where trace_id=%s", (report.source.trace_id,)
            ).fetchone()[0]
            >= 1
        )
    assert service.replay(case["context"].identity.run_id, command, authorization=authorization) == report
    assert len(runtime.gateway.calls) == 2 and len(original.calls) == 2
    assert case["runtime"].result(case["context"], user=case["context"].principal) == delivery


def test_original_conditions_refused_before_audit_or_prepare_or_provider(db):
    case, original, _, runtime, authorization, _, service, command = prepared(db)
    service.prepare = lambda *a: pytest.fail("must not construct executable dependencies")
    with pytest.raises(BusinessError) as failure:
        service.replay(
            case["context"].identity.run_id,
            command.model_copy(update={"mode": "original_conditions"}),
            authorization=authorization,
        )
    assert failure.value.code.value == "version_conflict"
    assert len(original.calls) == 2 and not runtime.gateway.calls
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select count(*) from payload_access_log where trace_id=%s", (case["context"].identity.trace_id,)
        ).fetchone() == (0,)


def test_report_failure_can_be_repaired_without_another_execution_or_charge(db, monkeypatch):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    record = PgTraceStore.record_replay
    with monkeypatch.context() as patch:
        patch.setattr(
            PgTraceStore,
            "record_replay",
            lambda *a: (_ for _ in ()).throw(RuntimeError("PUBLIC secret report failure")),
        )
        with pytest.raises(InfrastructureError) as failure:
            service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert failure.value.code.value == "audit_unavailable" and len(runtime.gateway.calls) == 2
    monkeypatch.setattr(PgTraceStore, "record_replay", record)
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert report.replay.metadata.status == "completed" and len(runtime.gateway.calls) == 2


@pytest.mark.parametrize("revocation", ["admin", "principal", "source"])
def test_current_authorization_failures_prevent_new_calls(db, revocation):
    case, _, _, runtime, authorization, admin, service, command = prepared(db)
    with psycopg.connect(db["owner"]) as conn:
        if revocation == "admin":
            conn.execute("update principals set roles='{}' where sub_pseudonym=%s", (admin,))
        elif revocation == "principal":
            conn.execute(
                "update principals set scopes='{}' where sub_pseudonym=%s", (case["context"].principal.user_id,)
            )
        else:
            conn.execute("delete from document_acl where doc_id=%s", (case["doc"],))
    with pytest.raises(BusinessError):
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert not runtime.gateway.calls


@pytest.mark.parametrize("kind,status", [("clarify", "awaiting_clarification"), ("escalate", "escalated")])
def test_diagnostic_retains_agent_stop_semantics_without_mapping_to_ask(db, kind, status):
    case, _, _, runtime, authorization, _, service, command = prepared(db, kind)
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert report.source.metadata.status == report.replay.metadata.status == status
    assert report.conditions.input_match and not report.changed
    assert len(runtime.gateway.calls) == 2


def test_failed_diagnostic_preserves_unknown_costs_and_does_not_retry(db):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    runtime.gateway = FakeModelGateway({"agent_plan": [ModelTimeout("PUBLIC private provider response")]})
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert report.replay.metadata.status == "failed" and "status" in report.changed
    assert report.conditions.actual_models_match is None
    assert report.replay.metadata.accounting.accounted_cost_usd > 0
    assert "PUBLIC private provider response" not in report.model_dump_json()
    assert service.replay(case["context"].identity.run_id, command, authorization=authorization) == report
    assert len(runtime.gateway.calls) == 1


def test_changed_command_same_id_and_diagnostic_source_are_rejected_without_new_calls(db):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    with pytest.raises(BusinessError) as failure:
        service.replay(
            case["context"].identity.run_id,
            command.model_copy(update={"reason": "PUBLIC changed diagnostic purpose"}),
            authorization=authorization,
        )
    assert failure.value.code.value == "version_conflict"
    with pytest.raises(BusinessError) as failure:
        service.replay(
            report.replay.metadata.run_id,
            AgentReplayRequest(replay_id=uuid4(), reason=PURPOSE),
            authorization=authorization,
        )
    assert failure.value.code.value == "invalid_request" and len(runtime.gateway.calls) == 2


def test_provenance_commit_failure_blocks_provider_and_duplicate_cannot_restart(db, monkeypatch):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    append = PgAgentRuntime.append

    def broken(store, lease, kind, item_id, body, **kwargs):
        if body.get("kind") == "diagnostic_replay":
            raise RuntimeError("PUBLIC private provenance failure")
        return append(store, lease, kind, item_id, body, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(PgAgentRuntime, "append", broken)
        with pytest.raises(InfrastructureError) as failure:
            service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert "PUBLIC private provenance failure" not in str(failure.value)
    assert not runtime.gateway.calls
    with pytest.raises(BusinessError):
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert not runtime.gateway.calls


def test_input_changed_by_trusted_preparer_is_caught_before_control_or_provider(db):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    prepare = service.prepare

    def changed(*args):
        context, executor = prepare(*args)
        return context.model_copy(
            update={"query_context": context.query_context.model_copy(update={"historical_requested": True})}
        ), executor

    service.prepare = changed
    with pytest.raises(BusinessError) as failure:
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert failure.value.code.value == "invalid_request" and not runtime.gateway.calls
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select count(*) from agent_run_control where run_id=%s", (replay_identity(command.replay_id).run_id,)
        ).fetchone() == (0,)


def test_access_log_commit_failure_prevents_preparation_and_provider(db, monkeypatch):
    from contextlib import contextmanager

    case, _, _, runtime, authorization, _, service, command = prepared(db)
    connection = runtime.restricted_connection

    @contextmanager
    def lost_commit():
        with connection() as conn:
            yield conn
            raise RuntimeError("PUBLIC restricted commit unconfirmed")

    monkeypatch.setattr(runtime, "restricted_connection", lost_commit)
    service.prepare = lambda *args: pytest.fail("decrypted input must not be used before access commit")
    with pytest.raises(InfrastructureError) as failure:
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert "PUBLIC restricted commit unconfirmed" not in str(failure.value)
    assert not runtime.gateway.calls


def test_expired_original_material_is_not_reconstructed_from_trace_metadata(db):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    with psycopg.connect(db["owner"]) as conn:
        conn.execute("alter table agent_runtime_heads disable trigger user")
        conn.execute(
            "update agent_runtime_heads set retained_until=clock_timestamp()-interval '1 second' where run_id=%s",
            (case["context"].identity.run_id,),
        )
        conn.execute("alter table agent_runtime_heads enable trigger user")
    with pytest.raises(BusinessError) as failure:
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert failure.value.code.value == "not_found" and not runtime.gateway.calls


def test_same_chunk_ids_with_changed_text_are_reported_as_content_changes(db):
    case, original, _, runtime, authorization, _, service, command = prepared(db, retrieval=True)
    before = len(original.calls)
    with psycopg.connect(db["owner"]) as conn:
        # Model a restored/corrupt snapshot in OUR disposable database. Normal
        # production writes must keep rejecting mutation of immutable chunks.
        assert conn.info.dbname.startswith("medops_test_")
        conn.execute("alter table chunks disable trigger user")
        conn.execute("alter table chunk_spans disable trigger user")
        changed = "PUBLIC revised clause: keep the report date and the follow-up date."
        conn.execute(
            "update chunks set content=%s,chunk_content_hash=%s where chunk_id=%s",
            (changed, hashlib.sha256(changed.encode()).hexdigest(), case["chunk"]),
        )
        conn.execute("update chunk_spans set char_end=%s where chunk_id=%s", (len(changed), case["chunk"]))
        conn.execute("alter table chunk_spans enable trigger user")
        conn.execute("alter table chunks enable trigger user")
    report = service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert report.source.metadata.status == report.replay.metadata.status == "completed"
    assert report.source.cited_chunk_ids == report.replay.cited_chunk_ids
    assert report.conditions.input_match and report.conditions.evidence_match is False
    assert "evidence_sha256" in report.changed and "output_sha256" in report.changed
    assert changed not in report.model_dump_json()
    assert len(original.calls) == before and runtime.gateway.calls


def test_parallel_duplicate_commands_have_only_one_executable_root(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    case, _, _, runtime, authorization, _, service, command = prepared(db)
    prepare = service.prepare
    barrier = Barrier(2)

    def simultaneous(*args):
        result = prepare(*args)
        barrier.wait(timeout=20)
        return result

    service.prepare = simultaneous

    def invoke():
        try:
            return service.replay(case["context"].identity.run_id, command, authorization=authorization)
        except BusinessError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: invoke(), range(2)))
    assert sum(not isinstance(o, BusinessError) for o in outcomes) == 1, [type(o).__name__ for o in outcomes]
    assert sum(isinstance(o, BusinessError) and o.code.value == "version_conflict" for o in outcomes) == 1
    assert len(runtime.gateway.calls) == 2
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select count(*) from agent_run_control where run_id=%s", (replay_identity(command.replay_id).run_id,)
        ).fetchone() == (1,)
        assert conn.execute("select count(*) from replays where replay_id=%s", (command.replay_id,)).fetchone() == (1,)


def test_admin_revoked_during_provider_call_stops_further_calls_but_retains_settlement(db):
    from medops.application.agent_loop_ports import AgentLoopAbort

    case, _, _, runtime, authorization, admin, service, command = prepared(db)
    fake = runtime.gateway

    class RevokingProvider:
        provider = "fake"

        def complete(self, request):
            response = fake.complete(request)
            with psycopg.connect(db["owner"]) as conn:
                conn.execute("update principals set roles='{}' where sub_pseudonym=%s", (admin,))
            return response

    runtime.gateway = RevokingProvider()
    with pytest.raises((BusinessError, AgentLoopAbort)):
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert len(fake.calls) == 1
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select count(*) from agent_runtime_events where run_id=%s and kind='call_settled'",
            (replay_identity(command.replay_id).run_id,),
        ).fetchone() == (1,)
        assert conn.execute("select count(*) from replays where replay_id=%s", (command.replay_id,)).fetchone() == (0,)


def test_surviving_trace_blocks_reusing_identity_without_runtime_before_any_charge(db):
    case, _, _, runtime, authorization, _, service, command = prepared(db)
    identity = replay_identity(command.replay_id)
    # A legitimate retained Trace can outlive its restricted runtime material.
    # Seed that state without deleting any audit or altering retention policy.
    with psycopg.connect(db["owner"]) as conn:
        PgTraceStore(conn).record(trace(trace_id=identity.trace_id), None)
    with pytest.raises(BusinessError) as failure:
        service.replay(case["context"].identity.run_id, command, authorization=authorization)
    assert failure.value.code.value == "version_conflict" and not runtime.gateway.calls
    with psycopg.connect(db["owner"]) as conn:
        assert conn.execute(
            "select count(*) from agent_run_control where run_id=%s", (identity.run_id,)
        ).fetchone() == (0,)
