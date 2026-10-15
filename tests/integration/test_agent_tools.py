"""PV adapters on temporary PostgreSQL facts, ordinary RLS roles and offline model replies."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest

from medops.application.agent_contracts import admit_action, context_binding
from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tools import AgentTools
from medops.bootstrap.agent import build_agent_tools
from medops.core.errors import BusinessError, InfrastructureError
from medops.domain.agent_execution import AgentSourceScope, AllowedSource, EvidenceHandle
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.infrastructure.db.agent_facts import PgAgentFacts, bind_fact_database
from medops.infrastructure.db.fact_plane import fact_plane_identity
from medops.infrastructure.llm.execution_budget import ExecutionLimits
from tests.support.documents import document, job, source_object
from tests.support.harness import FakeRetrieval
from tests.support.pv_agent import NOW, proposal, uid, wire
from tests.support.pv_tools import parent, setup_tools


@pytest.fixture
def data(db):
    pid = uuid4().hex * 2
    owner = uuid4().int % 2**55
    user = UserContext(user_id=pid, dept=Dept.PV, acl_scopes=frozenset({"PV:read"}))
    rows = {}
    with psycopg.connect(db["owner"]) as conn:
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values (%s,'PV',array[]::text[],array['PV:read'],'agent-test')",
            (pid,),
        )
        for i, (name, dept, status) in enumerate(
            [
                ("visible", "PV", "active"),
                ("hidden", "MA", "active"),
                ("archived", "PV", "archived"),
                ("other", "PV", "active"),
            ]
        ):
            src = source_object(conn, owner + i)
            conn.execute(
                "update source_objects set integrity_status='verified',last_verified_at=now() where source_object_id=%s",
                (src,),
            )
            title = f"PUBLIC guideline {name} {pid[:16]}"
            doc = document(
                conn,
                src,
                job(conn, src),
                status=status,
                parse_quality="trusted",
                owner_dept=dept,
                doc_type="guideline",
                title=title,
                version="PUBLIC v1",
                effective_from=date(2025, 1, 1),
                effective_to=date(2026, 1, 1) if status == "archived" else None,
            )
            conn.execute("insert into document_acl(doc_id,dept,granted_by) values (%s,%s,'agent-test')", (doc, dept))
            chunks = []
            for seq in range(3):
                text = f"PUBLIC {name} clause {seq}: the source records the report date."
                cid = conn.execute(
                    "insert into chunks(doc_id,seq,page,section,content) values (%s,%s,%s,'PUBLIC',%s) returning chunk_id",
                    (doc, seq, seq + 1, text),
                ).fetchone()[0]
                conn.execute(
                    "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,%s,0,%s)",
                    (cid, seq + 1, len(text)),
                )
                chunks.append(str(cid))
            sha = conn.execute("select source_hash from source_objects where source_object_id=%s", (src,)).fetchone()[0]
            rows[name] = dict(doc=str(doc), source=str(src), sha=sha, title=title, chunks=tuple(chunks))
        identity = fact_plane_identity(conn)
        binding = bind_fact_database(conn)
    return dict(db=db, user=user, rows=rows, fact_id=identity, binding=binding)


@contextmanager
def transaction(data, *, role="app", dept="PV"):
    with psycopg.connect(data["db"]["users"][role]) as conn:
        conn.execute("select set_config('medops.dept',%s,true)", (dept,))
        yield conn


def prepared(data, conn, *, which="visible", historical=False):
    current, previous, _, gateway = setup_tools()
    row = data["rows"][which]
    query = (
        current.context.query_context.model_copy(update={"as_of": date(2025, 6, 1), "historical_requested": True})
        if historical
        else current.context.query_context
    )
    context = current.context.model_copy(
        update={
            "principal": data["user"],
            "query_context": query,
            "source_scope": AgentSourceScope(
                requested_document=row["title"],
                requested_version="PUBLIC v1",
                resolution="resolved",
                allowed_sources=(AllowedSource(doc_id=row["doc"], version="PUBLIC v1", source_sha256=row["sha"]),),
            ),
            "versions": current.context.versions.model_copy(update={"fact_database_id": UUID(data["fact_id"])}),
        }
    )
    current = current.model_copy(update={"context": context})
    facts = PgAgentFacts(conn, data["user"], database_binding=data["binding"])
    skill = replace(
        previous.skill_context,
        user=data["user"],
        deps=replace(previous.skill_context.deps, as_of=query.as_of, query_context=query),
        as_of=query.as_of,
    )
    tool = AgentTools(context=context, facts=facts, registry=previous.registry, skill_context=skill, clock=lambda: NOW)
    return current, tool, facts, gateway


def bound(current, name="search_documents", registry=(), **changes):
    value = proposal(name)
    value["proposal"].update(changes)
    return admit_action(wire(value), run=current, action_id=uid(90), evidence_registry=registry, now=NOW)


def record(current, fact):
    return EvidenceHandle(
        handle=uid(10),
        binding=context_binding(current.context),
        source_sha256=fact.source_sha256,
        evidence=fact.evidence,
        expires_at=current.expires_at,
    )


def test_resolve_visible_name_id_version_and_hide_other_department(data):
    with transaction(data) as conn:
        _, _, facts, _ = prepared(data, conn)
        row = data["rows"]["visible"]
        for selector in (row["title"], row["doc"]):
            scope = facts.resolve_scope(
                selector, "PUBLIC v1", query_context=prepared(data, conn)[0].context.query_context
            )
            assert scope.resolution == "resolved" and scope.allowed_sources[0].doc_id == row["doc"]
        for selector, version in [
            (data["rows"]["hidden"]["title"], None),
            ("PUBLIC missing guideline", None),
            (row["title"], "wrong version"),
        ]:
            scope = facts.resolve_scope(selector, version, query_context=prepared(data, conn)[0].context.query_context)
            assert scope.resolution == "denied_or_unavailable" and not scope.allowed_sources


@pytest.mark.parametrize("region,index", [("current", 1), ("previous", 0), ("next", 2)])
def test_read_and_adjacent_use_fresh_fact_checks_with_exact_source(data, region, index):
    with transaction(data) as conn:
        current, tool, facts, _ = prepared(data, conn)
        initial = facts.lookup(current.context, (data["rows"]["visible"]["chunks"][1],))[0]
        old = record(current, initial)
        with parent():
            result = tool.execute(
                bound(current, "read_evidence", (old,), region=region), run=current, evidence_registry=(old,)
            )
        assert (
            result.kind == "ok"
            and result.payload.evidence.citation.chunk_id == data["rows"]["visible"]["chunks"][index]
        )
        assert result.payload.evidence.citation.page == index + 1 and not result.payload.evidence.truncated
        assert all(h.source_sha256 == data["rows"]["visible"]["sha"] for h in result.issued_handles)


@pytest.mark.parametrize(
    "which,historical,accepted", [("archived", False, False), ("archived", True, True), ("hidden", False, False)]
)
def test_historical_window_and_rls_are_preserved(data, which, historical, accepted):
    with transaction(data) as conn:
        current, _, facts, _ = prepared(data, conn, which=which, historical=historical)
        if accepted:
            result = facts.lookup(current.context, (data["rows"][which]["chunks"][0],))
            assert len(result) == 1 and result[0].evidence.historical
        else:
            with pytest.raises(AgentToolFault, match="denied_or_unavailable"):
                facts.lookup(current.context, (data["rows"][which]["chunks"][0],))


@pytest.mark.parametrize(
    "change", ["acl", "principal", "source", "content", "wrong_db_id", "wrong_dept", "owner_connection"]
)
def test_real_authorization_or_integrity_failures_cannot_issue_handles(data, change):
    with transaction(data, dept="MA" if change == "wrong_dept" else "PV") as conn:
        current, tool, facts, _ = prepared(data, conn)
        cid = data["rows"]["visible"]["chunks"][0]
        if change not in ("wrong_db_id", "wrong_dept", "owner_connection"):
            with psycopg.connect(data["db"]["owner"]) as admin:
                if change == "acl":
                    admin.execute("delete from document_acl where doc_id=%s", (data["rows"]["visible"]["doc"],))
                elif change == "principal":
                    admin.execute("update principals set active=false where sub_pseudonym=%s", (data["user"].user_id,))
                elif change == "source":
                    admin.execute(
                        "update source_objects set integrity_status='failed',last_verified_at=null where source_object_id=%s",
                        (data["rows"]["visible"]["source"],),
                    )
                else:
                    admin.execute("set session_replication_role=replica")
                    admin.execute("update chunks set content=content||' corrupt' where chunk_id=%s", (cid,))
                    admin.execute("set session_replication_role=default")
        if change == "wrong_db_id":
            context = current.context.model_copy(
                update={"versions": current.context.versions.model_copy(update={"fact_database_id": uuid4()})}
            )
        else:
            context = current.context
        if change == "owner_connection":
            with psycopg.connect(data["db"]["owner"]) as owner:
                owner.execute("select set_config('medops.dept','PV',true)")
                with pytest.raises(InfrastructureError):
                    PgAgentFacts(owner, data["user"], database_binding=data["binding"]).lookup(context, (cid,))
        else:
            with pytest.raises((AgentToolFault, BusinessError)):
                facts.lookup(context, (cid,))


def test_search_adapter_rejects_acl_revocation_after_retrieval(data):
    with transaction(data) as conn:
        current, tool, facts, _ = prepared(data, conn)
        old = facts.lookup(current.context, (data["rows"]["visible"]["chunks"][0],))[0]

        class Revoke(FakeRetrieval):
            def retrieve(self, request):
                result = super().retrieve(request)
                with psycopg.connect(data["db"]["owner"]) as admin:
                    admin.execute("delete from document_acl where doc_id=%s", (data["rows"]["visible"]["doc"],))
                return result

        tool.skill_context = replace(
            tool.skill_context, deps=replace(tool.skill_context.deps, retrieval=Revoke(old.evidence))
        )
        with parent():
            result = tool.execute(bound(current), run=current)
        assert result.kind == "denied_or_unavailable" and result.payload is None and not result.issued_handles


def test_final_fact_fence_blocks_acl_write_until_action_transaction_commits(data):
    with transaction(data) as conn:
        current, _, facts, _ = prepared(data, conn)
        observed = facts.lookup(current.context, (data["rows"]["visible"]["chunks"][0],))
        facts.final_check(current.context, observed)
        with psycopg.connect(data["db"]["owner"]) as admin:
            admin.execute("set lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                admin.execute("delete from document_acl where doc_id=%s", (data["rows"]["visible"]["doc"],))
    with psycopg.connect(data["db"]["owner"]) as admin:
        assert (
            admin.execute("delete from document_acl where doc_id=%s", (data["rows"]["visible"]["doc"],)).rowcount == 1
        )


def test_bootstrap_factory_uses_existing_resources_and_checks_versions(data):
    with transaction(data) as conn:
        current, old, facts, _ = prepared(data, conn)
        ev = facts.lookup(current.context, (data["rows"]["visible"]["chunks"][0],))[0].evidence
        received = []
        deps = replace(
            old.skill_context.deps,
            retrieval=FakeRetrieval(ev),
            execution_limits=ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=125),
        )
        routed = SimpleNamespace(versions=current.context.versions.versions)

        class Runtime:
            def route_policies(self, *_):
                return routed

            def build_deps(self, *args, **kwargs):
                received.append((args, kwargs))
                return deps

        tool = build_agent_tools(Runtime(), conn, current.context, database_binding=data["binding"])
        tool.clock = lambda: NOW
        with parent():
            result = tool.execute(bound(current), run=current)
        assert result.kind == "ok" and received[0][1]["query_context"] == current.context.query_context
        assert tool.skill_context.deps.gateway is old.skill_context.deps.gateway and result.issued_handles
        routed.versions = routed.versions.model_copy(update={"model_config_version": "other"})
        with pytest.raises(AgentToolFault):
            build_agent_tools(Runtime(), conn, current.context, database_binding=data["binding"])


def test_app_binding_validation_needs_no_new_access_to_admin_identity_table(data):
    with transaction(data) as conn:
        current, _, facts, _ = prepared(data, conn)
        assert conn.execute("select has_table_privilege(current_user,'fact_plane_identity','SELECT')").fetchone() == (
            False,
        )
        facts.check(current.context)
        bad = PgAgentFacts(
            conn, data["user"], database_binding=data["binding"].model_copy(update={"connection_identity": "b" * 64})
        )
        with pytest.raises(AgentToolFault, match="dependency_error"):
            bad.check(current.context)


def test_principal_revocation_during_model_call_drops_payload_but_keeps_usage(data):
    from medops.infrastructure.llm.fake import FakeModelGateway
    from medops.infrastructure.llm.meter import MeteredGateway

    class RevokingGateway(FakeModelGateway):
        def complete(self, request):
            response = super().complete(request)
            with psycopg.connect(data["db"]["owner"]) as admin:
                admin.execute("update principals set active=false where sub_pseudonym=%s", (data["user"].user_id,))
            return response

    gateway = RevokingGateway(
        {"skill:ae_extraction": [{"elements": [{"kind": "event", "value": "an event", "quote": "reported an event"}]}]}
    )
    with transaction(data) as conn:
        current, old, facts, _ = prepared(data, conn)
        skill = replace(old.skill_context, deps=replace(old.skill_context.deps, gateway=MeteredGateway(gateway)))
        tool = AgentTools(
            context=current.context, facts=facts, registry=old.registry, skill_context=skill, clock=lambda: NOW
        )
        with parent() as budget:
            result = tool.execute(bound(current, "extract_ae"), run=current)
            assert budget.snapshot().calls == 1 and budget.snapshot().accounted_tokens > 0
        assert result.kind == "denied_or_unavailable" and result.payload is None and len(result.call_receipt_ids) == 1
        assert len(gateway.calls) == 1
