"""`McpService` on the real schema under the read-only LOGIN user: visibility follows RLS and status (other
department, draft and withdrawn documents do not exist; archived only with the explicit historical version),
verify_citation compares every field with the fact plane, list_active_versions returns the single active
version, search applies the same visibility to whatever the searcher returns, and the connection cannot write."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import Dept, DocStatus
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.mcp.contracts import GetChunkInput, ListActiveVersionsInput, SearchDocumentsInput, VerifyCitationInput
from medops.mcp.service import McpService
from tests.integration.lexical_adapter_suite import make_database
from tests.integration.test_migrations import document, job, source_object


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    """One chunk per case; returns chunk ids, doc ids and family ids."""
    out: dict[str, dict] = {}
    counter = 900
    with psycopg.connect(db["owner"]) as conn:

        def make(
            name,
            *,
            dept="MA",
            acl=("MA",),
            status="active",
            version=None,
            family=None,
            effective_from=date(2026, 1, 1),
            effective_to=None,
        ):
            nonlocal counter
            counter += 1
            src = source_object(conn, counter)
            conn.execute(
                "update source_objects set integrity_status = 'verified', last_verified_at = now() where source_object_id = %s",
                (src,),
            )
            fam = family or uuid.uuid4()
            ver = version or f"v{counter}"
            if status == "draft":
                doc = document(conn, src, None, family_id=fam, owner_dept=dept, version=ver, title=f"doc {name}")
            else:
                doc = document(
                    conn,
                    src,
                    job(conn, src, quality="trusted"),
                    family_id=fam,
                    owner_dept=dept,
                    version=ver,
                    status=status,
                    parse_quality="trusted",
                    effective_from=effective_from,
                    effective_to=effective_to,
                    title=f"doc {name}",
                )
            for d in acl:
                conn.execute(
                    "insert into document_acl (doc_id, dept, granted_by) values (%s, %s, 'admin-01')", (doc, d)
                )
            text = f"{name}: 每日最高之建議劑量為 8mg。"
            cid = conn.execute(
                "insert into chunks (doc_id, seq, page, section, content, chunk_content_hash) values (%s, 0, 3, %s, %s, null) returning chunk_id",
                (doc, "用法用量", text),
            ).fetchone()[0]
            out[name] = {
                "chunk_id": str(cid),
                "doc_id": str(doc),
                "family_id": str(fam),
                "version": ver,
                "text": text,
                "effective_from": effective_from,
            }
            return out[name]

        make("visible")
        make("other_dept", dept="PV", acl=("PV",))
        make("draft", status="draft")
        fam = uuid.uuid4()
        make(
            "archived",
            status="archived",
            family=fam,
            version="2024",
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 1, 1),
        )
        make("current", family=fam, version="2026", effective_from=date(2026, 1, 1))
        conn.commit()
    return out


def service(db, dept="MA"):
    conn = psycopg.connect(db["users"]["readonly"])
    conn.execute("select set_config('medops.dept', %s, true)", (dept,))
    user = UserContext(user_id="u-" + dept.lower(), dept=Dept(dept), acl_scopes=frozenset({f"{dept}:read"}))
    return conn, McpService(conn, user)


def citation(row, **overrides) -> Citation:
    base = dict(
        doc_id=row["doc_id"],
        version=row["version"],
        effective_date=row["effective_from"],
        page=3,
        section="用法用量",
        chunk_id=row["chunk_id"],
    )
    base.update(overrides)
    return Citation(**base)


def test_get_chunk_follows_rls_status_and_historical_rules(db, seed):
    conn, svc = service(db)
    with conn:
        view = svc.get_chunk(GetChunkInput(chunk_id=seed["visible"]["chunk_id"]))
        assert view.content == seed["visible"]["text"] and view.status is DocStatus.active and view.citation.page == 3
        for name in ("other_dept", "draft", "archived"):
            with pytest.raises(BusinessError) as exc:
                svc.get_chunk(GetChunkInput(chunk_id=seed[name]["chunk_id"]))
            assert exc.value.code is ErrorCode.not_found, name
        hist = svc.get_chunk(GetChunkInput(chunk_id=seed["archived"]["chunk_id"], historical_version="2024"))
        assert hist.status is DocStatus.archived and hist.historical is True
        with pytest.raises(BusinessError):
            svc.get_chunk(
                GetChunkInput(chunk_id=seed["archived"]["chunk_id"], historical_version="2023")
            )  # wrong label
        with pytest.raises(BusinessError):
            svc.get_chunk(GetChunkInput(chunk_id="not-a-uuid"))


def test_verify_citation_compares_every_field_and_hides_invisible_documents(db, seed):
    conn, svc = service(db)
    with conn:
        ok = svc.verify_citation(VerifyCitationInput(citation=citation(seed["visible"])))
        assert ok.exists and ok.status is DocStatus.active and ok.fields_match
        off = svc.verify_citation(VerifyCitationInput(citation=citation(seed["visible"], page=4)))
        assert off.exists and not off.fields_match
        wrong_version = svc.verify_citation(VerifyCitationInput(citation=citation(seed["visible"], version="v0")))
        assert wrong_version.exists and not wrong_version.fields_match
        for name in ("other_dept", "draft"):
            gone = svc.verify_citation(VerifyCitationInput(citation=citation(seed[name])))
            assert gone.exists is False and gone.status is None and gone.fields_match is False
        archived = svc.verify_citation(VerifyCitationInput(citation=citation(seed["archived"])))
        assert archived.exists and archived.status is DocStatus.archived and archived.fields_match


def test_list_active_versions_returns_the_single_active_version(db, seed):
    conn, svc = service(db)
    with conn:
        out = svc.list_active_versions(ListActiveVersionsInput(family_id=seed["current"]["family_id"]))
        assert (
            out.active is not None and out.active.version == "2026" and out.active.doc_id == seed["current"]["doc_id"]
        )
        assert (
            svc.list_active_versions(ListActiveVersionsInput(family_id=seed["other_dept"]["family_id"])).active is None
        )
        assert svc.list_active_versions(ListActiveVersionsInput(family_id="nope")).active is None


def test_search_applies_visibility_to_the_searcher_output_and_the_connection_cannot_write(db, seed):
    conn, svc = service(db)
    with conn:

        def evidence_for(name):
            row = seed[name]
            import hashlib

            status = DocStatus.archived if name == "archived" else DocStatus.active
            return Evidence(
                citation=citation(row),
                text=row["text"],
                evidence_text_hash=hashlib.sha256(row["text"].encode()).hexdigest(),
                chunk_content_hash=hashlib.sha256(row["text"].encode()).hexdigest(),
                status=status,
                historical=status is DocStatus.archived,
            )

        calls = []

        def searcher(query, k, *, as_of, allow_historical):
            calls.append((query, k, as_of, allow_historical))
            return [evidence_for("visible"), evidence_for("archived"), evidence_for("visible")]

        svc2 = McpService(conn, svc.user, searcher)
        out = svc2.search_documents(SearchDocumentsInput(query="劑量", k=5))
        assert [h.citation.chunk_id for h in out.hits] == [
            seed["visible"]["chunk_id"]
        ] and out.candidate_exhausted is True
        assert calls[-1][2] is None and calls[-1][3] is False
        hist = svc2.search_documents(SearchDocumentsInput(query="劑量", k=5, historical_version="2024"))
        assert [h.status for h in hist.hits] == [DocStatus.active, DocStatus.archived] and hist.hits[
            1
        ].historical is True
        assert calls[-1][2] == date(2025, 1, 1) and calls[-1][3] is True
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "insert into document_acl (doc_id, dept, granted_by) values (%s, 'PV', 'x')",
                (seed["visible"]["doc_id"],),
            )
        conn.rollback()


def test_production_runtime_audit_writes_an_mcp_trace_through_the_app_role(db, seed):
    """Record 73: the runtime's audit path uses the application role and lands a kind='mcp' row."""
    from medops.application.audit import TraceRecord
    from medops.domain.common import Dept
    from medops.domain.identity import UserContext
    from medops.mcp.server import McpProductionRuntime

    user = UserContext(user_id="a" * 64, dept=Dept.MA, roles=("analyst",), acl_scopes=frozenset({"MA:read"}))
    runtime = McpProductionRuntime(
        authenticator=None,
        dev_identity=user,
        readonly_dsn=db["users"]["readonly"],
        app_dsn_for_directory=db["users"]["app"],
    )
    trace = TraceRecord(
        trace_id="c" * 32,
        run_id="c" * 32,
        kind="mcp",
        principal=user.user_id,
        dept=Dept.MA,
        query="get_chunk {}",
        outcome="answered",
        reason_codes=(),
        versions={"mcp_server": "0.0.1"},
        evidence_chunk_ids=(),
        cited_chunk_ids=(),
        flagged_chunk_ids=(),
        model_calls=0,
        tokens=0,
        cost_usd=0.0,
        duration_ms=1.0,
        spans=(),
    )
    runtime.audit(trace)
    with psycopg.connect(db["users"]["admin"]) as conn:
        row = conn.execute("select kind, principal, outcome from traces where trace_id = %s", ("c" * 32,)).fetchone()
    assert row == ("mcp", "a" * 64, "answered")
