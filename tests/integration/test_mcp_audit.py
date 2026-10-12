"""Actual MCP protocol, ordinary roles, envelope encryption and transactional rollback.

The only model is a scripted FakeModelGateway. Facts live in the suite's temporary database.
"""

import secrets
import uuid
from datetime import date
from types import SimpleNamespace

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege

from medops.application.payloads import PayloadReader
from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet, RequestPolicies
from medops.bootstrap.search import SearchRuntime
from medops.core.config import Settings
from medops.core.envelope import StaticKeyProvider
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.retrieval_port import RetrievalOutcome
from medops.infrastructure.db.payloads import PgPayloadStore
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelRequest
from medops.mcp.server import McpProductionRuntime, build_server
from medops.retrieval.recheck import recheck_candidates
from tests.mcp_client import call


@pytest.fixture(scope="module")
def facts(db):
    principal, family = uuid.uuid4().hex * 2, uuid.uuid4()
    text = "Synthetic MCP audit source, 12 hours."
    with psycopg.connect(db["owner"]) as conn:
        src = conn.execute(
            "insert into source_objects(source_hash,storage_uri,byte_size,mime,created_by,integrity_status,last_verified_at) "
            "values(%s,'synthetic-mcp-fixture',100,'application/pdf','test','verified',now()) returning source_object_id",
            (uuid.uuid4().hex * 2,),
        ).fetchone()[0]
        job = conn.execute(
            "insert into ingestion_jobs(source_object_id,status,parse_quality,parser_version) "
            "values(%s,'succeeded','trusted','synthetic') returning job_id",
            (src,),
        ).fetchone()[0]
        doc = conn.execute(
            "insert into documents(family_id,title,doc_type,version,status,effective_from,source_object_id,active_ingestion_job_id,parse_quality,owner_dept,language,created_by) "
            "values(%s,'Synthetic audit guide','guideline','v1','active','2026-01-01',%s,%s,'trusted','MA','en','test') returning doc_id",
            (family, src, job),
        ).fetchone()[0]
        conn.execute("insert into document_acl(doc_id,dept,granted_by) values(%s,'MA','test')", (doc,))
        cid = conn.execute(
            "insert into chunks(doc_id,seq,page,section,content) values(%s,0,1,'Synthetic',%s) returning chunk_id",
            (doc, text),
        ).fetchone()[0]
        conn.execute(
            "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values(%s,0,1,0,%s)", (cid, len(text))
        )
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values(%s,'MA',array['analyst'],array['MA:read'],'test')",
            (principal,),
        )
    return dict(principal=principal, family=str(family), cid=str(cid), doc=str(doc), text=text)


def runtime(db, facts, *, fail_retrieval=False):
    user = UserContext(user_id=facts["principal"], dept=Dept.MA, roles=("analyst",), acl_scopes=frozenset({"MA:read"}))
    provider = StaticKeyProvider({"synthetic": secrets.token_bytes(32)}, "synthetic")

    class ScriptedCost(FakeModelGateway):
        def complete(self, request):
            # Synthetic metering only; no provider or real fee ledger is contacted.
            return super().complete(request).model_copy(update={"cost_usd": 0.002})

    gateway = ScriptedCost({"query_translation": [{"translation": "synthetic audit"}]})
    settings = Settings(_env_file=None, database_url=db["users"]["app"], redis_url="redis://localhost:6379/0")
    pol = ReleasedPolicySet(
        (
            ReleasedPolicy(
                str(uuid.uuid4()),
                "retrieval_params",
                "hybrid",
                "synthetic",
                {"query_translation": {"from": "off", "to": "gpt-6-luna"}},
            ),
        )
    )
    routed = RequestPolicies(
        pol,
        VersionSet(
            policy_version="synthetic",
            retrieval_version="synthetic",
            model_config_version="synthetic",
            skill_version_set=(),
        ),
    )

    def build(conn, caller, context, selected, meter):
        def retrieve(request):
            meter.complete(
                ModelRequest(
                    purpose="query_translation",
                    model_id="gpt-6-luna",
                    max_output_tokens=256,
                    messages=({"role": "user", "content": request.query},),
                )
            )
            if fail_retrieval:
                raise InfrastructureError(ErrorCode.dependency_unavailable)
            evidence = recheck_candidates(conn, [facts["cid"]], as_of=context.as_of).evidence
            return RetrievalOutcome(rewritten_queries=(request.query,), candidates=(), evidence=evidence)

        return SimpleNamespace(retrieve=retrieve)

    search = SearchRuntime(
        settings, SimpleNamespace(build=build), SimpleNamespace(route=lambda conn, user: routed), _gateway=gateway
    )
    rt = McpProductionRuntime(
        authenticator=None,
        dev_identity=user,
        readonly_dsn=db["users"]["readonly"],
        app_dsn_for_directory=db["users"]["app"],
        searcher_factory=search,
        settings=settings,
        payload_provider=provider,
    )
    saved = []
    original = rt.audit

    def audit(trace, **kwargs):
        original(trace, **kwargs)
        saved.append(trace)

    rt.audit = audit
    return rt, provider, gateway, saved


def read(db, provider, trace_id):
    admin = UserContext(user_id="c" * 64, dept=Dept.MA, roles=("admin",), acl_scopes=frozenset())
    with psycopg.connect(db["users"]["restricted"]) as conn:
        response = PayloadReader(PgPayloadStore(conn), provider).read(admin, trace_id, "synthetic incident review")
    return {item.kind: item.payload for item in response.items}


@pytest.mark.parametrize("tool", ["get_chunk", "search_documents", "verify_citation", "list_active_versions"])
def test_four_tools_store_typed_input_actual_output_and_observed_facts_atomically(db, facts, tool):
    rt, provider, gateway, saved = runtime(db, facts)
    inp = {
        "get_chunk": {"chunk_id": facts["cid"]},
        "search_documents": {"query": "synthetic query 中文 " * 80, "k": 3},
        "verify_citation": {
            "citation": {
                "doc_id": facts["doc"],
                "version": "v1",
                "effective_date": "2026-01-01",
                "page": 1,
                "section": "Synthetic",
                "chunk_id": facts["cid"],
            }
        },
        "list_active_versions": {"family_id": facts["family"]},
    }[tool]
    _, response = call(build_server(rt), tool, {"input": inp})
    assert not response.is_error and len(saved) == 1
    material = read(db, provider, saved[0].trace_id)
    assert set(material) == {"input", "evidence_snapshot", "model_output"}
    assert all(item["format_version"] == "mcp-audit-v1" for item in material.values())
    assert all(material["input"]["input"][key] == value for key, value in inp.items())
    assert material["model_output"]["tool_result"] == response.structured_content
    assert material["evidence_snapshot"]["observation_available"]
    if tool == "search_documents":
        assert len(gateway.calls) == len(material["model_output"]["model_calls"]) == 1
        assert material["input"]["conditions"]["routed"]["query_translation_model"] == "gpt-6-luna"
        assert material["input"]["query_context"]["as_of"] == date.today().isoformat()
        record = material["model_output"]["model_calls"][0]
        assert record["request"]["messages"][0]["content"] == inp["query"]
        assert record["response"]["parsed"] == {"translation": "synthetic audit"}
        assert record["receipt"]["call"]["run_id"] == saved[0].trace_id
        assert material["evidence_snapshot"]["observed"]["retrieval"]["evidence"][0]["text"] == facts["text"]
    else:
        assert not gateway.calls and material["model_output"]["model_calls"] == []
    with psycopg.connect(db["users"]["app"]) as app:
        with pytest.raises(InsufficientPrivilege):
            app.execute("select * from trace_payloads")
    with psycopg.connect(db["users"]["restricted"]) as conn:
        cipher = conn.execute(
            "select ciphertext from trace_payloads where trace_id=%s", (saved[0].trace_id,)
        ).fetchall()
        assert len(cipher) == 3 and all(facts["text"].encode() not in bytes(row[0]) for row in cipher)
    with psycopg.connect(db["users"]["admin"]) as conn:
        log = conn.execute("select purpose from payload_access_log where trace_id=%s", (saved[0].trace_id,)).fetchone()
        assert log == ("synthetic incident review",)


def test_failed_retrieval_retains_model_request_reply_and_fee_receipt_without_success(db, facts):
    rt, provider, gateway, saved = runtime(db, facts, fail_retrieval=True)
    _, response = call(build_server(rt), "search_documents", {"input": {"query": "synthetic failed search"}})
    assert response.is_error and len(gateway.calls) == len(saved) == 1
    assert saved[0].outcome == "escalated" and saved[0].cost_usd > 0
    body = read(db, provider, saved[0].trace_id)["model_output"]
    assert body["tool_result"] is None and body["error_type"] == "InfrastructureError"
    assert body["model_calls"][0]["response"]["parsed"] == {"translation": "synthetic audit"}
    assert body["call_receipts"][0]["accounted_cost_usd"] == saved[0].cost_usd


def test_partial_payload_failure_rolls_back_trace_and_first_blob_and_does_not_rerun_model(db, facts, monkeypatch):
    rt, _, gateway, saved = runtime(db, facts)
    with psycopg.connect(db["users"]["admin"]) as conn:
        before = conn.execute("select count(*) from traces where principal=%s", (facts["principal"],)).fetchone()[0]
    original = PgPayloadStore.put
    attempted = []

    def put(self, trace, node, kind, *args):
        attempted.append(kind)
        if kind == "evidence_snapshot":
            raise RuntimeError("synthetic-private-store-error")
        return original(self, trace, node, kind, *args)

    monkeypatch.setattr(PgPayloadStore, "put", put)
    _, response = call(build_server(rt), "search_documents", {"input": {"query": "synthetic atomic failure"}})
    assert response.is_error and "audit unavailable" in response.content[0].text
    assert "synthetic-private-store-error" not in response.content[0].text
    assert len(gateway.calls) == 1 and not saved and attempted == ["input", "evidence_snapshot"]
    with psycopg.connect(db["users"]["admin"]) as conn:
        assert (
            conn.execute("select count(*) from traces where principal=%s", (facts["principal"],)).fetchone()[0]
            == before
        )
