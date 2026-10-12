"""ARCH-15: real request/worker/MCP boundaries; synthetic facts, scripted gateways, ordinary LOGIN roles."""

import concurrent.futures
import queue
import time
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from urllib.parse import urlsplit

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from medops.api.app import create_app
from medops.application.contracts import TaskCreateRequest, TaskStatus
from medops.application.policy_loader import ReleasedPolicySet, RequestPolicies
from medops.application.search import SearchExecution
from medops.application.tasks import TaskRunner, TaskService
from medops.bootstrap.runtime import ProductionRuntime
from medops.core.config import Settings
from medops.core.errors import BusinessError
from medops.harness.dependencies import HarnessDeps
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.identity import Authenticator, PgDirectory, pseudonym
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.mcp.contracts import SearchDocumentsInput
from medops.mcp.server import McpProductionRuntime, build_server
from medops.retrieval.recheck import recheck_candidates
from medops.skills.catalog import default_registry
from tests.integration.lexical_adapter_suite import make_database
from tests.integration.test_migrations import document, job, source_object
from tests.mcp_client import call
from tests.unit.api.test_ask_route import ANSWER, ISSUER_OBJ, PSEUDONYM_KEY, QUERY, auth
from tests.unit.harness._fixtures import versions
from tests.unit.harness.test_run_ask import FakeRetrieval, fast_specs
from tests.unit.skills.test_matrix import SKILLS, scripted

AS_OF = date(2026, 10, 12)


@pytest.fixture(scope="module")
def db(admin_dsn):
    yield from make_database(admin_dsn)


@pytest.fixture
def facts(db, request):
    name = getattr(request, "param", "label_query")
    spec = SKILLS[name]
    dept = spec["dept"]
    pid = pseudonym("user-1", PSEUDONYM_KEY)
    with psycopg.connect(db["owner"]) as conn:
        src = source_object(conn, int(uuid.uuid4().int % (2**60)))
        conn.execute(
            "update source_objects set integrity_status='verified',last_verified_at=now() where source_object_id=%s",
            (src,),
        )
        doc = document(
            conn,
            src,
            job(conn, src),
            status="active",
            parse_quality="trusted",
            owner_dept=dept,
            effective_from=date(2026, 1, 1),
            doc_type="label" if name in ("label_query", "off_label_check") else "guideline",
        )
        conn.execute("insert into document_acl(doc_id,dept,granted_by) values (%s,%s,'arch15')", (doc, dept))
        text = spec["evidence"][0] if spec["evidence"] else "Synthetic event receipt."
        cid = conn.execute(
            "insert into chunks(doc_id,seq,page,section,content) values (%s,0,1,'S1',%s) returning chunk_id",
            (doc, text),
        ).fetchone()[0]
        conn.execute(
            "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,1,0,%s)", (cid, len(text))
        )
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values (%s,%s,array['analyst'],%s,'arch15') on conflict(sub_pseudonym) do update set dept=excluded.dept,roles=excluded.roles,scopes=excluded.scopes,active=true",
            (pid, dept, [f"{dept}:read"]),
        )
    return {
        "db": db,
        "name": name,
        "spec": spec,
        "pid": pid,
        "dept": dept,
        "src": str(src),
        "doc": str(doc),
        "cid": str(cid),
    }


def change(f, kind):
    with psycopg.connect(f["db"]["owner"]) as conn:
        if kind == "acl":
            conn.execute("delete from document_acl where doc_id=%s and dept=%s", (f["doc"], f["dept"]))
        elif kind == "principal":
            conn.execute("update principals set active=false where sub_pseudonym=%s", (f["pid"],))
        elif kind == "scopes":
            conn.execute("update principals set scopes=%s where sub_pseudonym=%s", ([f"{f['dept']}:write"], f["pid"]))
        elif kind == "source":
            conn.execute(
                "update source_objects set integrity_status='failed',last_verified_at=null where source_object_id=%s",
                (f["src"],),
            )
        elif kind == "archive":
            conn.execute(
                "select set_config('medops.actor','arch15',true),set_config('medops.reason','synthetic test',true)"
            )
            conn.execute("update documents set status='archived' where doc_id=%s", (f["doc"],))
        elif kind == "content":
            # Owned throwaway database only: simulate physical corruption; normal immutability remains enabled.
            conn.execute("set session_replication_role = replica")
            conn.execute("update chunks set content=content || ' corrupt' where chunk_id=%s", (f["cid"],))
            conn.execute("set session_replication_role = default")
        elif kind == "extra_offsets":
            conn.execute("delete from chunk_spans where chunk_id=%s", (f["extra"][0],))


def mapped(value, cid):
    if isinstance(value, dict):
        return {k: mapped(v, cid) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mapped(v, cid) for v in value]
    return cid if value == "c1" else value


class SyntheticRuntime(ProductionRuntime):
    """Real connection, directory, task/audit stores; replace only retrieval and hosted inference."""

    def route_policies(self, conn, user):
        return RequestPolicies(ReleasedPolicySet.empty(), self.versions)

    def build_deps(self, conn, user, request, routed=None, *, query_context=None):
        from medops.domain.query import resolve_query_context

        selected = query_context or resolve_query_context(
            request.historical.model_dump() if request.historical else None, default_as_of=AS_OF
        )
        ev = recheck_candidates(
            conn,
            [self.facts["cid"], *self.facts.get("extra", ())],
            as_of=selected.as_of,
            allow_historical=selected.historical_requested,
        ).evidence
        return HarnessDeps(
            retrieval=FakeRetrieval(*ev),
            gateway=MeteredGateway(self.gateway),
            answer_model_id="gpt-6-sol",
            judge_model_id="gpt-6-sol" if self.facts["name"] in ("off_label_check", "protocol_deviation") else None,
            specs=fast_specs(),
            sleep=lambda _: None,
            query_context=selected,
            as_of=selected.as_of,
        )


def runtime(f, *, mutate=None):
    source = scripted(f["spec"])
    script = {purpose: [mapped(reply, f["cid"]) for reply in queue] for purpose, queue in source._script.items()}
    if f["name"] == "label_query":
        script["answer"] = [mapped(ANSWER, f["cid"])] * 6

    class Gateway(FakeModelGateway):
        changed = False

        def complete(self, req):
            result = super().complete(req)
            terminal = f["spec"]["purpose"] or "answer"
            if mutate and not self.changed and req.purpose == terminal:
                self.changed = True
                change(f, mutate)
            return result

    rt = SyntheticRuntime(
        settings=Settings(_env_file=None, database_url=f["db"]["users"]["app"], redis_url="redis://localhost:6379/0"),
        authenticator=Authenticator(
            verifier=_Verifier(),
            pseudonym_key=PSEUDONYM_KEY,
        ),
        gateway=Gateway(script),
        embedding=None,
        reranker=None,
        versions=versions().model_copy(update={"skill_version_set": default_registry().version_set()}),
        _dsn=f["db"]["users"]["app"],
        as_of=AS_OF,
    )
    rt.facts = f
    return rt


class _Verifier:
    def verify(self, token):
        from medops.infrastructure.identity import JwtVerifier
        from tests.unit.api._auth_fixtures import AUDIENCE, ISSUER

        return JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=ISSUER_OBJ.jwks).verify(token)


@pytest.mark.parametrize("mutation", ["acl", "principal", "scopes", "source", "archive", "content"])
def test_ask_withholds_a_snapshot_changed_during_generation(facts, mutation):
    from fastapi.testclient import TestClient

    rt = runtime(facts, mutate=mutation)
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert rt.gateway.changed and len(rt.gateway.calls) == 1
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is None
    with rt.connection() as conn:
        row = conn.execute(
            "select outcome,cited_chunk_ids,model_calls,cost_usd from traces where trace_id=%s",
            (response.json()["trace_id"],),
        ).fetchone()
    assert row[0] in ("refused", "escalated") and row[1] == [] and row[2] == 1 and row[3] == 0


@pytest.mark.parametrize("facts", tuple(SKILLS), indirect=True)
def test_five_skills_withhold_results_after_identity_revocation(facts):
    rt = runtime(facts, mutate="principal")
    # citation_verification has no model: pause after its real evidence lookup instead.
    if facts["name"] == "citation_verification":
        original = rt.skill_context

        def context(conn, user, trace_id, historical):
            ctx = original(conn, user, trace_id, historical)
            lookup = ctx.evidence_lookup

            def paused(u, ids):
                ev = lookup(u, ids)
                change(facts, "principal")
                return ev

            return replace(ctx, evidence_lookup=paused)

        rt.skill_context = context
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        task = TaskService(rt.task_store(conn)).create(
            u,
            TaskCreateRequest(
                skill_name=facts["name"], skill_version="1.0.0", input=mapped(facts["spec"]["input"], facts["cid"])
            ),
            None,
        )
    execution = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once()
    assert execution.task_id == task.task_id and execution.record.status is TaskStatus.failed
    assert execution.record.result is None and execution.record.error["code"] == "forbidden"
    with rt.connection() as conn:
        row = conn.execute(
            "select outcome,cited_chunk_ids,model_calls from traces where trace_id=%s", (execution.trace_id,)
        ).fetchone()
    assert row[0] == "escalated" and row[1] == [] and row[2] == len(rt.gateway.calls)


def test_mcp_search_withholds_evidence_revoked_after_retrieval(facts):
    with psycopg.connect(facts["db"]["users"]["app"]) as conn:
        p = PgDirectory(conn).resolve(facts["pid"])
    from medops.domain.identity import UserContext

    u = UserContext(user_id=facts["pid"], dept=p.dept, roles=p.roles, acl_scopes=p.scopes)

    calls = []

    def factory(conn, _user):
        def search(_query, _k, **_kwargs):
            calls.append(_query)
            ev = recheck_candidates(conn, [facts["cid"]], as_of=AS_OF).evidence
            change(facts, "acl")
            # Synthetic metering exercises preservation; no provider is contacted.
            return SearchExecution(ev, model_calls=1, tokens=7, cost_usd=0.00037)

        return search

    rt = McpProductionRuntime(
        authenticator=None,
        dev_identity=u,
        readonly_dsn=facts["db"]["users"]["readonly"],
        app_dsn_for_directory=facts["db"]["users"]["app"],
        searcher_factory=factory,
    )
    _, result = call(
        build_server(rt),
        "search_documents",
        {"input": SearchDocumentsInput(query="synthetic", k=1).model_dump(mode="json")},
    )
    assert result.is_error
    assert facts["cid"] not in str(result.structured_content) and len(calls) == 1
    with psycopg.connect(facts["db"]["users"]["app"]) as conn:
        row = conn.execute(
            "select outcome,evidence_chunk_ids,model_calls,tokens,cost_usd from traces where kind='mcp' order by created_at desc limit 1"
        ).fetchone()
    assert row[:4] == ("escalated", [], 1, 7) and float(row[4]) == 0.00037


@pytest.mark.parametrize("facts", tuple(SKILLS), indirect=True)
def test_five_skills_unchanged_facts_still_complete(facts):
    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        TaskService(rt.task_store(conn)).create(
            u,
            TaskCreateRequest(
                skill_name=facts["name"], skill_version="1.0.0", input=mapped(facts["spec"]["input"], facts["cid"])
            ),
            None,
        )
    done = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once().record
    assert done.status is TaskStatus.completed and done.result["status"] == "completed", done.error or done.result


def test_ask_unchanged_facts_still_answer(facts):
    from fastapi.testclient import TestClient

    rt = runtime(facts)
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert response.status_code == 200 and response.json()["outcome"] == "answered", response.text
    assert len(rt.gateway.calls) == 1


@pytest.mark.parametrize("facts", ["off_label_check", "protocol_deviation"], indirect=True)
def test_second_stage_skills_recheck_inner_evidence(facts):
    rt = runtime(facts, mutate="source")
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        TaskService(rt.task_store(conn)).create(
            u, TaskCreateRequest(skill_name=facts["name"], skill_version="1.0.0", input=facts["spec"]["input"]), None
        )
    done = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once().record
    assert done.status is TaskStatus.failed and done.result is None
    assert done.error["code"] == "evidence_integrity_failed"
    assert len(rt.gateway.calls) == 3  # answer, business generation and final business judgment


@pytest.mark.parametrize("tool", ["get_chunk", "verify_citation", "list_active_versions", "search_documents"])
def test_mcp_tools_unchanged_facts_still_return(facts, tool):
    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        rt.bind_identity(conn, u)
        ev = recheck_candidates(conn, [facts["cid"]], as_of=AS_OF).evidence
        family = conn.execute("select family_id::text from documents where doc_id=%s", (facts["doc"],)).fetchone()[0]
    inputs = {
        "get_chunk": {"chunk_id": facts["cid"]},
        "verify_citation": {"citation": ev[0].citation.model_dump(mode="json")},
        "list_active_versions": {"family_id": family},
        "search_documents": {"query": "synthetic", "k": 1},
    }
    mcp = McpProductionRuntime(
        authenticator=None,
        dev_identity=u,
        readonly_dsn=facts["db"]["users"]["readonly"],
        app_dsn_for_directory=facts["db"]["users"]["app"],
        searcher_factory=lambda conn, user: (
            lambda _q, _k, **kw: SearchExecution(recheck_candidates(conn, [facts["cid"]], as_of=AS_OF).evidence)
        ),
    )
    _, result = call(build_server(mcp), tool, {"input": inputs[tool]})
    assert not result.is_error


def test_completed_task_cannot_be_read_after_document_revocation(facts):
    from fastapi.testclient import TestClient

    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        task = TaskService(rt.task_store(conn)).create(
            u, TaskCreateRequest(skill_name="label_query", skill_version="1.0.0", input=facts["spec"]["input"]), None
        )
    done = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once().record
    assert done.status is TaskStatus.completed and done.result["status"] == "completed"
    change(facts, "acl")
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.get(f"/v1/tasks/{task.task_id}", headers=auth())
    assert response.status_code == 500 and response.json()["code"] == "evidence_integrity_failed"
    assert "citation_chunk_ids" not in response.text


def test_completed_task_get_and_idempotent_read_revalidate_private_binding(facts):
    from fastapi.testclient import TestClient

    rt = runtime(facts)
    body = {"skill_name": "label_query", "skill_version": "1.0.0", "input": facts["spec"]["input"]}
    headers = {**auth(), "Idempotency-Key": "arch15-stored-output"}
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        created = client.post("/v1/tasks", json=body, headers=headers)
        assert created.status_code == 202
        task_id = created.json()["task_id"]
        done = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once().record
        assert done.status is TaskStatus.completed and done.output_binding.evidence
        assert '"text":' not in done.output_binding.model_dump_json()
        response = client.get(f"/v1/tasks/{task_id}", headers=auth())
        again = client.post("/v1/tasks", json=body, headers=headers)
        assert response.status_code == 200 and again.status_code == 202
        assert response.json()["result"] == again.json()["result"] == done.result
        assert "output_binding" not in response.json() and len(rt.gateway.calls) == 1
        change(facts, "acl")
        refused = client.post("/v1/tasks", json=body, headers=headers)
        assert refused.status_code == 500 and refused.json()["code"] == "evidence_integrity_failed"
        assert "citation_chunk_ids" not in refused.text and len(rt.gateway.calls) == 1
    with psycopg.connect(facts["db"]["owner"]) as conn:
        with pytest.raises(psycopg.Error, match="immutable"):
            conn.execute("update tasks set output_binding=null where task_id=%s", (task_id,))
        conn.rollback()
        # Only a trusted operator can simulate a pre-migration completed row.
        conn.execute("set session_replication_role = replica")
        conn.execute("update tasks set output_binding=null where task_id=%s", (task_id,))
        conn.execute("set session_replication_role = default")
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        legacy = client.get(f"/v1/tasks/{task_id}", headers=auth())
        assert legacy.status_code == 500 and legacy.json()["code"] == "evidence_integrity_failed"
        assert len(rt.gateway.calls) == 1


@pytest.mark.parametrize("facts", ["off_label_check", "protocol_deviation"], indirect=True)
def test_uncited_inner_evidence_is_required_even_when_final_report_cites_other_chunk(facts):
    with psycopg.connect(facts["db"]["owner"]) as conn:
        extra = conn.execute(
            "insert into chunks(doc_id,seq,page,section,content) values (%s,1,2,'S2',%s) returning chunk_id",
            (facts["doc"], "Additional synthetic condition that also supports the comparison."),
        ).fetchone()[0]
        conn.execute(
            "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,2,0,73)", (extra,)
        )
    facts["extra"] = [str(extra)]
    rt = runtime(facts, mutate="extra_offsets")
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        TaskService(rt.task_store(conn)).create(
            u, TaskCreateRequest(skill_name=facts["name"], skill_version="1.0.0", input=facts["spec"]["input"]), None
        )
    execution = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once()
    assert execution.record.status is TaskStatus.failed
    assert execution.record.error["code"] == "evidence_integrity_failed" and len(rt.gateway.calls) == 3
    with rt.connection() as conn:
        evidence, cited = conn.execute(
            "select evidence_chunk_ids,cited_chunk_ids from traces where trace_id=%s", (execution.trace_id,)
        ).fetchone()
    assert set(evidence) == {facts["cid"], str(extra)} and cited == []


@pytest.mark.parametrize("tool", ["get_chunk", "verify_citation", "list_active_versions"])
@pytest.mark.parametrize("mutation", ["source", "principal"])
def test_mcp_raw_tools_withhold_changed_source_or_identity_and_keep_failure_audit(facts, tool, mutation):
    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        rt.bind_identity(conn, u)
        ev = recheck_candidates(conn, [facts["cid"]], as_of=AS_OF).evidence[0]
        family = conn.execute("select family_id::text from documents where doc_id=%s", (facts["doc"],)).fetchone()[0]
    inputs = {
        "get_chunk": {"chunk_id": facts["cid"]},
        "verify_citation": {"citation": ev.citation.model_dump(mode="json")},
        "list_active_versions": {"family_id": family},
    }
    mcp = McpProductionRuntime(
        authenticator=None,
        dev_identity=u,
        readonly_dsn=facts["db"]["users"]["readonly"],
        app_dsn_for_directory=facts["db"]["users"]["app"],
    )
    original = mcp.service

    @contextmanager
    def service(user):
        with original(user) as svc:
            method = getattr(svc, tool)

            def paused(inp):
                value = method(inp)
                change(facts, mutation)
                return value

            setattr(svc, tool, paused)
            yield svc

    mcp.service = service
    with rt.connection() as conn:
        before = conn.execute("select count(*) from traces where kind='mcp'").fetchone()[0]
    _, result = call(build_server(mcp), tool, {"input": inputs[tool]})
    assert result.is_error and facts["cid"] not in str(result.structured_content)
    with rt.connection() as conn:
        count = conn.execute("select count(*) from traces where kind='mcp'").fetchone()[0]
        audit = conn.execute(
            "select outcome,evidence_chunk_ids,model_calls from traces where kind='mcp' and principal=%s and query like %s order by created_at desc limit 1",
            (facts["pid"], f"{tool} %"),
        ).fetchone()
    assert count == before + 1 and audit[0] in ("escalated", "refused")
    assert audit[1:] == ([], 0)


def test_mcp_final_guard_reauthenticates_bearer_against_changed_directory(facts):
    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.authenticator.authenticate(auth()["Authorization"], rt.directory(conn))
    mcp = McpProductionRuntime(
        authenticator=rt.authenticator,
        dev_identity=None,
        readonly_dsn=facts["db"]["users"]["readonly"],
        app_dsn_for_directory=facts["db"]["users"]["app"],
    )
    from medops.mcp.contracts import GetChunkInput

    with mcp.service(u) as svc:
        inp = GetChunkInput(chunk_id=facts["cid"])
        result = svc.get_chunk(inp).model_dump(mode="json")
        change(facts, "scopes")
        with pytest.raises(BusinessError) as exc:
            with mcp.final_output(u, svc, inp, result, authorization=auth()["Authorization"]):
                pytest.fail("changed bearer identity was accepted")
    assert exc.value.code.value == "forbidden"


@pytest.mark.parametrize("facts", ["citation_verification"], indirect=True)
@pytest.mark.parametrize("grant_during_run", [True, False])
def test_negative_citation_lookup_is_rechecked_at_completion_and_later_reads(facts, grant_during_run):
    from fastapi.testclient import TestClient

    change(facts, "acl")
    rt = runtime(facts)
    original = rt.skill_context

    def grant():
        with psycopg.connect(facts["db"]["owner"]) as conn:
            conn.execute(
                "insert into document_acl(doc_id,dept,granted_by) values (%s,%s,'arch15')",
                (facts["doc"], facts["dept"]),
            )

    def context(conn, user, trace_id, historical):
        ctx = original(conn, user, trace_id, historical)
        lookup = ctx.evidence_lookup

        def paused(u, ids):
            found = lookup(u, ids)
            assert found == ()
            if grant_during_run:
                grant()
            return found

        return replace(ctx, evidence_lookup=paused)

    rt.skill_context = context
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        task = TaskService(rt.task_store(conn)).create(
            u,
            TaskCreateRequest(
                skill_name="citation_verification",
                skill_version="1.0.0",
                input=mapped(facts["spec"]["input"], facts["cid"]),
            ),
            None,
        )
    done = TaskRunner(rt, default_registry(sleep=lambda _: None), worker_id="arch15").run_once().record
    assert rt.gateway.calls == []
    if grant_during_run:
        assert done.status is TaskStatus.failed and done.error["code"] == "evidence_integrity_failed"
    else:
        assert done.status is TaskStatus.completed and done.output_binding.lookups[0].evidence == ()
        with TestClient(create_app(rt), raise_server_exceptions=False) as client:
            before = client.get(f"/v1/tasks/{task.task_id}", headers=auth())
            assert before.status_code == 200
            grant()
            after = client.get(f"/v1/tasks/{task.task_id}", headers=auth())
            assert after.status_code == 500 and after.json()["code"] == "evidence_integrity_failed"


@pytest.mark.parametrize(
    "table", ["principals", "document_acl", "documents", "source_objects", "chunks", "chunk_spans"]
)
def test_fact_mutations_are_blocked_between_real_ask_final_check_and_audit_commit(facts, table):
    from fastapi.testclient import TestClient

    rt = runtime(facts)
    observed = []
    statements = {
        "principals": ("update principals set active=false where sub_pseudonym=%s", facts["pid"]),
        "document_acl": ("delete from document_acl where doc_id=%s", facts["doc"]),
        "documents": ("update documents set status='archived' where doc_id=%s", facts["doc"]),
        "source_objects": (
            "update source_objects set integrity_status='failed',last_verified_at=null where source_object_id=%s",
            facts["src"],
        ),
        "chunks": ("update chunks set content=content where chunk_id=%s", facts["cid"]),
        "chunk_spans": ("delete from chunk_spans where chunk_id=%s", facts["cid"]),
    }

    def writer():
        try:
            with psycopg.connect(
                facts["db"]["owner"], options="-c lock_timeout=150ms -c statement_timeout=2000ms"
            ) as conn:
                conn.execute("select set_config('medops.actor','arch15',true),set_config('medops.reason','test',true)")
                sql, value = statements[table]
                conn.execute(sql, (value,))
        except psycopg.Error as exc:
            return exc.sqlstate
        return "unexpected_write"

    class Store(PgTraceStore):
        def record(self, trace, escalation):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                observed.append(pool.submit(writer).result(timeout=3))
            super().record(trace, escalation)

    rt.trace_store = lambda conn: Store(conn)
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert response.json()["outcome"] == "answered" and observed == ["55P03"], response.text
    # A normal mutation succeeds after commit: the fence is short, not a permanent lock.
    change(facts, "acl")


def test_writer_committing_before_final_fence_is_seen_by_fresh_queries(facts):
    rt = runtime(facts)
    with rt.connection() as conn:
        u = rt.resolve_user(conn, facts["pid"])
        rt.bind_identity(conn, u)
        ev = recheck_candidates(conn, [facts["cid"]], as_of=AS_OF).evidence
    ready = queue.Queue()

    def reader():
        with rt.connection() as conn:
            rt.bind_identity(conn, u)
            ready.put(conn.info.backend_pid)
            try:
                from medops.domain.query import QueryContext

                rt.validate_final_output(conn, u, ev, QueryContext(as_of=AS_OF))
            except BusinessError as exc:
                return exc.code.value
        return "unexpected_output"

    with psycopg.connect(facts["db"]["owner"]) as writer, concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute("update principals set active=false where sub_pseudonym=%s", (facts["pid"],))
        future = pool.submit(reader)
        pid = ready.get(timeout=2)
        waiting = False
        until = time.monotonic() + 0.6
        while time.monotonic() < until:
            if writer.execute(
                "select exists(select 1 from pg_locks where pid=%s and locktype='advisory' and not granted)", (pid,)
            ).fetchone()[0]:
                waiting = True
                break
            time.sleep(0.01)
        writer.commit()
        assert waiting and future.result(timeout=3) == "forbidden"


def test_final_lock_timeout_withholds_answer_but_keeps_failure_and_usage_audit(facts):
    from fastapi.testclient import TestClient

    rt = runtime(facts)
    complete = rt.gateway.complete
    with psycopg.connect(facts["db"]["owner"]) as writer:

        def hold(req):
            result = complete(req).model_copy(update={"cost_usd": 0.0123})  # synthetic known usage, no provider
            writer.execute("update principals set active=false where sub_pseudonym=%s", (facts["pid"],))
            return result

        rt.gateway.complete = hold
        with TestClient(create_app(rt), raise_server_exceptions=False) as client:
            response = client.post("/v1/ask", json={"query": QUERY}, headers=auth())
        writer.rollback()
    assert response.status_code == 200 and response.json()["answer"] is None
    assert response.json()["escalation"]["reason_codes"] == ["system_failure"]
    with rt.connection() as conn:
        row = conn.execute(
            "select outcome,cited_chunk_ids,model_calls,cost_usd,tokens from traces where trace_id=%s",
            (response.json()["trace_id"],),
        ).fetchone()
    assert row[:3] == ("escalated", [], 1) and float(row[3]) == 0.0123 and row[4] > 0


def test_readonly_fence_grants_no_fact_writes_and_rejects_old_snapshots(facts):
    with psycopg.connect(facts["db"]["users"]["readonly"]) as conn:
        conn.execute("select medops_acquire_output_fence()")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("update principals set active=false where sub_pseudonym=%s", (facts["pid"],))
        conn.rollback()
        conn.execute("begin isolation level repeatable read")
        with pytest.raises(psycopg.Error) as exc:
            conn.execute("select medops_acquire_output_fence()")
        assert exc.value.sqlstate == "55000"


def test_explicit_historical_ask_remains_usable(facts):
    from fastapi.testclient import TestClient

    change(facts, "archive")
    rt = runtime(facts)
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/ask", json={"query": QUERY, "historical": {"as_of": AS_OF.isoformat()}}, headers=auth()
        )
    assert response.status_code == 200 and response.json()["outcome"] == "answered"
    assert response.json()["answer"]["historical_notice"] is True


# Review 197: reject stale/privileged MCP connections and stale admin identity.
def mcp_runtime(f):
    rt = runtime(f)
    with rt.connection() as conn:
        user = rt.resolve_user(conn, f["pid"])
        rt.bind_identity(conn, user)
        ev = recheck_candidates(conn, [f["cid"]], as_of=date.today()).evidence[0]
        family = conn.execute("select family_id::text from documents where doc_id=%s", (f["doc"],)).fetchone()[0]
    mcp = McpProductionRuntime(
        authenticator=None,
        dev_identity=user,
        readonly_dsn=f["db"]["users"]["readonly"],
        app_dsn_for_directory=f["db"]["users"]["app"],
        searcher_factory=lambda conn, _user: (
            lambda _q, _k, **_kw: recheck_candidates(conn, [f["cid"]], as_of=date.today()).evidence
        ),
    )
    return mcp, {
        "get_chunk": {"chunk_id": f["cid"]},
        "verify_citation": {"citation": ev.citation.model_dump(mode="json")},
        "list_active_versions": {"family_id": family},
        "search_documents": {"query": "synthetic", "k": 1},
    }


@pytest.mark.parametrize("tool", ["get_chunk", "verify_citation", "list_active_versions", "search_documents"])
@pytest.mark.parametrize("isolation", ["repeatable read", "serializable"])
def test_mcp_rejects_stale_fact_transactions_and_records_failure(facts, tool, isolation):
    mcp, inputs = mcp_runtime(facts)
    parsed = urlsplit(mcp.readonly_dsn)
    with psycopg.connect(facts["db"]["owner"]) as conn:
        conn.execute(
            sql.SQL("alter role {} in database {} set default_transaction_isolation to {}").format(
                sql.Identifier(parsed.username), sql.Identifier(parsed.path.lstrip("/")), sql.Literal(isolation)
            )
        )
    original = mcp.service

    @contextmanager
    def paused(user):
        with original(user) as svc:
            method = getattr(svc, tool)

            def revoked(inp):
                result = method(inp)
                change(facts, "acl")
                return result

            setattr(svc, tool, revoked)
            yield svc

    mcp.service = paused
    try:
        _, result = call(build_server(mcp), tool, {"input": inputs[tool]})
    finally:
        with psycopg.connect(facts["db"]["owner"]) as conn:
            conn.execute(
                sql.SQL("alter role {} in database {} reset default_transaction_isolation").format(
                    sql.Identifier(parsed.username), sql.Identifier(parsed.path.lstrip("/"))
                )
            )
    assert result.is_error, "old fact snapshot passed the final authorization boundary"
    assert facts["cid"] not in str(result.structured_content)
    with psycopg.connect(facts["db"]["users"]["app"]) as conn:
        row = conn.execute(
            "select outcome,model_calls from traces where kind='mcp' and principal=%s order by created_at desc limit 1",
            (facts["pid"],),
        ).fetchone()
    assert row == ("escalated", 0)


@pytest.mark.parametrize("role", ["owner", "admin"])
@pytest.mark.parametrize("tool", ["get_chunk", "verify_citation", "list_active_versions"])
def test_mcp_refuses_fact_connections_that_bypass_acl(facts, role, tool):
    mcp, inputs = mcp_runtime(facts)
    change(facts, "acl")
    mcp.readonly_dsn = facts["db"]["owner"] if role == "owner" else facts["db"]["users"][role]
    _, result = call(build_server(mcp), tool, {"input": inputs[tool]})
    assert result.is_error, "privileged fact connection exposed a document hidden from the user"
    assert facts["cid"] not in str(result.structured_content)


@pytest.mark.parametrize("operation", ["list", "acl"])
def test_admin_reauthenticates_before_privileged_read_or_write(facts, operation):
    rt = runtime(facts)
    rt._admin_dsn = facts["db"]["users"]["admin"]
    with psycopg.connect(facts["db"]["owner"]) as conn:
        conn.execute("update principals set roles=array['admin'] where sub_pseudonym=%s", (facts["pid"],))
        conn.execute(
            "update documents set document_key=%s where doc_id=%s",
            ("review-197-" + facts["doc"].replace("-", ""), facts["doc"]),
        )
    original = rt.admin_connection

    @contextmanager
    def revoked():
        change(facts, "principal")
        with original() as conn:
            yield conn

    rt.admin_connection = revoked
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        if operation == "list":
            result = client.get("/admin/documents", headers=auth())
        else:
            result = client.patch(
                f"/admin/documents/{facts['doc']}/acl",
                json={"grant": ["PV"], "reason": "synthetic review 197"},
                headers=auth(),
            )
    assert result.status_code == 403, "revoked administrator retained a privileged operation"
    with psycopg.connect(facts["db"]["owner"]) as conn:
        assert not conn.execute(
            "select exists(select 1 from document_acl where doc_id=%s and dept='PV')", (facts["doc"],)
        ).fetchone()[0]


@pytest.mark.parametrize("mutation", [False, True])
def test_privileged_identity_fence_blocks_revocation_until_transaction_commit(facts, mutation):
    rt = runtime(facts)
    rt._admin_dsn = facts["db"]["users"]["admin"]
    with rt.connection() as identity, rt.admin_connection() as target:
        user = rt.authenticator.authenticate(auth()["Authorization"], rt.directory(identity))
        rt.validate_privileged_access(identity, target, user, authorization=auth()["Authorization"], mutation=mutation)
        with psycopg.connect(facts["db"]["owner"], options="-c lock_timeout=150ms") as writer:
            with pytest.raises(psycopg.errors.LockNotAvailable):
                writer.execute("update principals set active=false where sub_pseudonym=%s", (facts["pid"],))
            writer.rollback()
        if mutation:
            # The write connection must reacquire the trigger's fence without
            # waiting on a shared lock held by its own separate identity connection.
            target.execute(
                "insert into document_acl(doc_id,dept,granted_by) values (%s,'PV','review197')", (facts["doc"],)
            )
    change(facts, "principal")  # once the session commits, normal revocation succeeds


def test_privileged_target_must_be_the_identity_database(facts, scratch_database):
    from medops.core.errors import ErrorCode

    rt = runtime(facts)
    with rt.connection() as identity, psycopg.connect(scratch_database) as target, target.transaction():
        user = rt.authenticator.authenticate(auth()["Authorization"], rt.directory(identity))
        with pytest.raises(BusinessError) as exc:
            rt.validate_privileged_access(identity, target, user, authorization=auth()["Authorization"], mutation=True)
    assert exc.value.code is ErrorCode.forbidden


def test_restricted_payload_read_rejects_revocation_before_plaintext_access(facts):
    rt = runtime(facts)
    with psycopg.connect(facts["db"]["owner"]) as conn:
        conn.execute("update principals set roles=array['admin'] where sub_pseudonym=%s", (facts["pid"],))

    @contextmanager
    def restricted():
        change(facts, "principal")
        with psycopg.connect(facts["db"]["users"]["restricted"]) as conn, conn.transaction():
            yield conn

    rt.restricted_connection = restricted
    rt.payload_reader = lambda _conn: pytest.fail("revoked administrator reached the plaintext reader")
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        result = client.get(
            "/admin/traces/" + "a" * 32 + "/payload", params={"purpose": "synthetic review 197"}, headers=auth()
        )
    assert result.status_code == 403
