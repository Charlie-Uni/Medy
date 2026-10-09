"""The MCP server exposes exactly the four read-only tools, takes identity only from the verified bearer token
(HTTP) or the fixed stdio identity, refuses unauthenticated HTTP calls, and reports tool failures as errors
without leaking internals. Driven in-process over memory streams with the SDK client."""

from __future__ import annotations

from contextlib import contextmanager

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from starlette.testclient import TestClient

from medops.api.auth import Authenticator, JwtVerifier, Principal, StaticDirectory, pseudonym
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept, DocStatus, DocType
from medops.mcp.contracts import (
    MCP_TOOLS,
    ChunkView,
    DocumentVersionView,
    ListActiveVersionsOutput,
    SearchDocumentsOutput,
    VerifyCitationOutput,
)
from medops.mcp.server import build_server
from medops.mcp.service import SearchExecution
from tests.unit.api._auth_fixtures import AUDIENCE, ISSUER, PSEUDONYM_KEY, TestIssuer
from tests.unit.harness._fixtures import evidence, user

ISSUER_OBJ = TestIssuer()
CHUNK = evidence(
    "11111111-1111-4111-8111-111111111111", "每日最高之建議劑量為 8mg。", doc_id="22222222-2222-4222-8222-222222222222"
)


class FakeService:
    def __init__(self, user):
        self.user = user
        self.audit_stats = SearchExecution(())

    def search_documents(self, inp):
        self.audit_stats = SearchExecution(
            (),
            model_calls=1,
            tokens=17,
            cost_usd=0.002,
            retrieval_version="retrieval-canary",
            policy_version="policy-canary",
            cache_hit=False,
        )
        if inp.query == "fail-after-model":
            raise InfrastructureError(ErrorCode.dependency_unavailable, "retrieval failed")
        return SearchDocumentsOutput(hits=(), requested_k=inp.k, candidate_exhausted=True)

    def get_chunk(self, inp):
        if inp.chunk_id != CHUNK.citation.chunk_id:
            raise BusinessError(ErrorCode.not_found, "chunk not found")
        import hashlib

        return ChunkView(
            citation=CHUNK.citation,
            content=CHUNK.text,
            content_hash=hashlib.sha256(CHUNK.text.encode()).hexdigest(),
            status=DocStatus.active,
        )

    def verify_citation(self, inp):
        return VerifyCitationOutput(
            exists=inp.citation.chunk_id == CHUNK.citation.chunk_id,
            status=DocStatus.active if inp.citation.chunk_id == CHUNK.citation.chunk_id else None,
            fields_match=inp.citation == CHUNK.citation,
        )

    def list_active_versions(self, inp):
        view = DocumentVersionView(
            doc_id=CHUNK.citation.doc_id,
            family_id=inp.family_id,
            title="瑪爾胰仿單",
            doc_type=DocType.label,
            version="v1",
            effective_from=CHUNK.citation.effective_date,
        )
        return ListActiveVersionsOutput(family_id=inp.family_id, active=view)


class FakeRuntime:
    def __init__(self, *, with_auth: bool, dev_identity=None):
        self.authenticator = (
            Authenticator(
                verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=ISSUER_OBJ.jwks),
                pseudonym_key=PSEUDONYM_KEY,
            )
            if with_auth
            else None
        )
        self.dev_identity = dev_identity
        self.served: list[str] = []
        self.audited: list = []
        self.fail_audit = False

    @contextmanager
    def directory(self):
        yield StaticDirectory(
            {pseudonym("user-1", PSEUDONYM_KEY): Principal(dept=Dept.MA, scopes=frozenset({"MA:read"}))}
        )

    @contextmanager
    def service(self, user):
        self.served.append(user.dept.value)
        yield FakeService(user)

    def audit(self, trace):
        if self.fail_audit:
            raise RuntimeError("audit store down")
        self.audited.append(trace)


def call(server, tool: str, arguments: dict):
    async def main():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            low = server._lowlevel_server
            async with anyio.create_task_group() as tg:
                tg.start_soon(low.run, server_streams[0], server_streams[1], low.create_initialization_options())
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    result = await session.call_tool(tool, arguments)
                tg.cancel_scope.cancel()
            return tools, result

    return anyio.run(main)


def test_exactly_the_four_read_only_tools_and_no_identity_in_their_inputs():
    server = build_server(FakeRuntime(with_auth=False, dev_identity=user(Dept.MA)))
    tools, _ = call(server, "list_active_versions", {"input": {"family_id": "33333333-3333-4333-8333-333333333333"}})
    assert sorted(t.name for t in tools.tools) == sorted(t.name for t in MCP_TOOLS)
    for t in tools.tools:
        assert (
            t.annotations is not None
            and t.annotations.read_only_hint is True
            and t.annotations.destructive_hint is False
        )
        assert not ({"dept", "scopes", "user_id", "sub"} & set(str(t.input_schema)))


def test_tools_run_under_the_call_identity_and_errors_do_not_leak():
    rt = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(rt)
    _, ok = call(server, "get_chunk", {"input": {"chunk_id": CHUNK.citation.chunk_id}})
    assert (
        not ok.is_error
        and ok.structured_content["citation"]["chunk_id"] == CHUNK.citation.chunk_id
        and rt.served == ["MA"]
    )
    _, missing = call(server, "get_chunk", {"input": {"chunk_id": "44444444-4444-4444-8444-444444444444"}})
    assert missing.is_error and "not_found" in missing.content[0].text and "Traceback" not in missing.content[0].text
    _, verify = call(server, "verify_citation", {"input": {"citation": CHUNK.citation.model_dump(mode="json")}})
    assert verify.structured_content == {"exists": True, "status": "active", "fields_match": True}


def test_http_transport_requires_a_valid_bearer_token():
    server = build_server(FakeRuntime(with_auth=True), issuer_url=ISSUER, resource_url="http://testserver/mcp")
    app = server.streamable_http_app()
    with TestClient(app) as client:
        anonymous = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert anonymous.status_code == 401
        forged = TestIssuer(kid="k1").token()
        bad = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + forged},
        )
        assert bad.status_code == 401
        good = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Accept": "application/json, text/event-stream", "Authorization": "Bearer " + ISSUER_OBJ.token()},
        )
        assert good.status_code != 401  # authenticated; the protocol may still reject the bare request (no session)


def test_no_identity_at_all_is_refused():
    server = build_server(FakeRuntime(with_auth=False, dev_identity=None))
    _, result = call(server, "list_active_versions", {"input": {"family_id": "33333333-3333-4333-8333-333333333333"}})
    assert result.is_error and "unauthenticated" in result.content[0].text


def test_tool_calls_are_traced_with_the_tool_name_and_department():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from medops.core import telemetry

    exp = InMemorySpanExporter()
    telemetry.install_exporter(exp, batch=False)
    try:
        server = build_server(FakeRuntime(with_auth=False, dev_identity=user(Dept.MA)))
        call(server, "verify_citation", {"input": {"citation": CHUNK.citation.model_dump(mode="json")}})
        tools = [s for s in exp.get_finished_spans() if s.name == "mcp.tool"]
        assert tools and tools[-1].attributes["tool"] == "verify_citation" and tools[-1].attributes["dept"] == "MA"
        call(server, "get_chunk", {"input": {"chunk_id": "44444444-4444-4444-8444-444444444444"}})
        failed = [s for s in exp.get_finished_spans() if s.name == "mcp.tool"][-1]
        assert failed.attributes["error_code"] == "not_found"
    finally:
        telemetry.set_tracer_provider(None)


def test_every_tool_call_writes_an_mcp_trace_and_audit_failure_fails_closed():
    """M3-07 follow-up (record 73): one trace per call with the tool, the principal pseudonym and the chunk ids
    handed out; an error path is audited with its code; when the audit store is down no data leaves."""
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    chunk_id = CHUNK.citation.chunk_id
    _, ok = call(server, "get_chunk", {"input": {"chunk_id": chunk_id}})
    assert not ok.is_error
    trace = runtime.audited[-1]
    assert trace.kind == "mcp" and trace.query.startswith("get_chunk ") and trace.outcome == "answered"
    assert chunk_id in trace.evidence_chunk_ids and trace.model_calls == 0 and trace.cost_usd == 0.0
    assert len(trace.principal) == 64  # a dev identity is hashed into the pseudonym shape
    _, missing = call(server, "get_chunk", {"input": {"chunk_id": "00000000-0000-4000-8000-00000000dead"}})
    assert missing.is_error and runtime.audited[-1].outcome == "escalated"
    assert runtime.audited[-1].reason_codes == ("not_found",)
    runtime.fail_audit = True
    _, closed = call(server, "get_chunk", {"input": {"chunk_id": chunk_id}})
    assert closed.is_error and "audit unavailable" in closed.content[0].text and closed.structured_content is None


def test_search_audit_includes_translation_usage_and_routed_versions():
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    _, result = call(server, "search_documents", {"input": {"query": "剂量", "k": 8}})
    assert not result.is_error
    trace = runtime.audited[-1]
    assert (trace.model_calls, trace.tokens, trace.cost_usd) == (1, 17, 0.002)
    assert trace.versions["retrieval_version"] == "retrieval-canary"
    assert trace.versions["policy_version"] == "policy-canary"


def test_failed_search_audit_keeps_model_usage_before_the_failure():
    runtime = FakeRuntime(with_auth=False, dev_identity=user(Dept.MA))
    server = build_server(runtime)
    _, result = call(server, "search_documents", {"input": {"query": "fail-after-model", "k": 8}})
    assert result.is_error
    trace = runtime.audited[-1]
    assert trace.outcome == "escalated" and (trace.model_calls, trace.tokens, trace.cost_usd) == (1, 17, 0.002)
    assert trace.versions["policy_version"] == "policy-canary"
