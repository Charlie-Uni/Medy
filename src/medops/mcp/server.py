"""Read-only MCP server (M3-06) on the official SDK 2.x: exactly the four tools of `MCP_TOOLS`, all flagged
read-only, identity from the verified bearer token (Streamable HTTP) or a fixed synthetic identity in stdio
mode (dev/test only). Each call opens the read-only database connection, injects the caller's department and
runs `McpService`; the database role proves the tools cannot write."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

import psycopg
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from medops.application.audit import TraceRecord
from medops.application.search import SearchExecution
from medops.bootstrap.connections import open_connection
from medops.core.config import Settings
from medops.core.deadline import deadline_scope
from medops.core.errors import BusinessError, ErrorCode, MedOpsError
from medops.core.telemetry import annotate, span
from medops.core.tracing import bind_trace_id
from medops.domain.identity import UserContext
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.db.final_output import acquire_output_fence, directory_user, require_same_user
from medops.infrastructure.identity import Authenticator, PgDirectory, PrincipalDirectory
from medops.infrastructure.llm.accounting import call_scope
from medops.mcp.contracts import (
    MCP_TOOLS,
    GetChunkInput,
    ListActiveVersionsInput,
    SearchDocumentsInput,
    VerifyCitationInput,
)
from medops.mcp.service import McpService
from medops.retrieval.integrity import database_identity
from medops.retrieval.production import PRODUCTION_RETRIEVAL_VERSION

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


class ServiceLike(Protocol):
    audit_stats: SearchExecution

    def search_documents(self, inp: SearchDocumentsInput) -> Any: ...

    def get_chunk(self, inp: GetChunkInput) -> Any: ...

    def verify_citation(self, inp: VerifyCitationInput) -> Any: ...

    def list_active_versions(self, inp: ListActiveVersionsInput) -> Any: ...

    def validate_final_output(self, inp: Any, result: dict[str, Any]) -> None: ...


class McpRuntime(Protocol):
    authenticator: Authenticator | None  # None only for stdio dev mode
    dev_identity: UserContext | None  # stdio dev/test identity; never used when a token is present

    def directory(self) -> AbstractContextManager[PrincipalDirectory]: ...

    def service(self, user: UserContext) -> AbstractContextManager[ServiceLike]: ...

    def final_output(
        self, user: UserContext, service: ServiceLike, inp: Any, result: dict[str, Any], *, authorization: str | None
    ) -> AbstractContextManager[None]: ...

    def audit(self, trace: TraceRecord) -> None:
        """Persist the per-call trace (kind='mcp'); raising here fails the call closed (INV-OBS-01)."""
        ...


class BearerVerifier:
    """SDK `TokenVerifier`: reuses the API's authenticator (issuer, audience, expiry, signature, principal directory)."""

    def __init__(self, runtime: McpRuntime) -> None:
        self._runtime = runtime

    async def verify_token(self, token: str) -> AccessToken | None:
        if self._runtime.authenticator is None:
            return None
        try:
            with self._runtime.directory() as directory:
                user = self._runtime.authenticator.authenticate("Bearer " + token, directory)
        except MedOpsError:
            return None  # unauthenticated, unprovisioned or key source down: the SDK answers 401
        return AccessToken(
            token=token,
            client_id=user.user_id,
            scopes=sorted(user.acl_scopes),
            expires_at=None,
            claims={"user": user.model_dump(mode="json")},
        )


def _current_user(runtime: McpRuntime) -> UserContext:
    token = get_access_token()
    if token is not None:
        claims = token.claims or {}
        return UserContext.model_validate(claims["user"])
    if runtime.dev_identity is not None:
        return runtime.dev_identity
    raise BusinessError(ErrorCode.unauthenticated, "no verified identity for this call")


_REFUSAL_CODES = {ErrorCode.forbidden, ErrorCode.unauthenticated}
_HEX = re.compile(r"^[0-9a-f]{32,64}$")
SERVER_VERSION = "0.0.1"


def _chunk_ids(payload: Any) -> tuple[str, ...]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "chunk_id" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return tuple(dict.fromkeys(found))


def _audit(
    runtime: McpRuntime,
    user: UserContext,
    trace_id: str,
    tool: str,
    inp: Any,
    outcome: str,
    reason_codes: tuple[str, ...],
    result: dict[str, Any] | None,
    started: float,
    stats: SearchExecution | None = None,
) -> None:
    """One trace per tool call (M3-07): principal pseudonym, tool + input summary, outcome, chunk ids handed out.
    An audit failure is surfaced as a tool error and the data is withheld, like /v1/ask (record 60)."""
    principal = user.user_id if _HEX.match(user.user_id) else hashlib.sha256(user.user_id.encode()).hexdigest()
    summary = json.dumps(inp.model_dump(mode="json"), ensure_ascii=False)[:500]
    stats = stats or SearchExecution(())
    versions = {"mcp_server": SERVER_VERSION, "retrieval_version": PRODUCTION_RETRIEVAL_VERSION}
    if stats.versions is not None:
        versions.update(stats.versions.model_dump(mode="json"))
    if stats.retrieval_version:
        versions["retrieval_version"] = stats.retrieval_version
    if stats.policy_version:
        versions["policy_version"] = stats.policy_version
    trace = TraceRecord(
        trace_id=trace_id,
        run_id=trace_id,
        kind="mcp",
        principal=principal,
        dept=user.dept,
        query=f"{tool} {summary}",
        outcome=outcome,
        reason_codes=reason_codes,
        versions=versions,
        evidence_chunk_ids=_chunk_ids(result),
        cited_chunk_ids=(),
        flagged_chunk_ids=(),
        model_calls=stats.model_calls,
        tokens=stats.tokens,
        cost_usd=stats.cost_usd,
        duration_ms=(perf_counter() - started) * 1000.0,
        spans=(),
    )
    try:
        runtime.audit(trace)
    except Exception as exc:  # noqa: BLE001 - any audit failure fails the call closed
        raise ToolError("internal_error: audit unavailable, call refused (fail closed)") from exc


def build_server(runtime: McpRuntime, *, issuer_url: str | None = None, resource_url: str | None = None) -> MCPServer:
    auth = None
    verifier = None
    if runtime.authenticator is not None:
        verifier = BearerVerifier(runtime)
        auth = AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url or "https://issuer.invalid"),
            resource_server_url=AnyHttpUrl(resource_url or "http://localhost:8001/mcp"),
            validate_token_resource=False,  # audience is checked by our JWT verifier
        )
    server = MCPServer(name="medops-copilot", version="0.0.1", token_verifier=verifier, auth=auth)
    specs = {t.name: t for t in MCP_TOOLS}

    def run(name: str, method: str, inp: Any) -> dict[str, Any]:
        started = perf_counter()
        trace_id = uuid.uuid4().hex
        with (
            bind_trace_id(trace_id),
            call_scope(run_id=trace_id, attempt_id=f"mcp:{name}:1"),
            span("mcp.tool", tool=name) as current,
        ):
            user = None
            svc = None
            stats = None
            try:
                user = _current_user(runtime)
                annotate(current, dept=user.dept.value)
                # Keep the short app-role fence/audit transaction alive across
                # the read-only service commit. Both DSNs must be the same DB.
                with ExitStack() as final:
                    with runtime.service(user) as svc:
                        result = getattr(svc, method)(inp).model_dump(mode="json")
                        stats = getattr(svc, "audit_stats", None)
                        token = get_access_token()
                        final.enter_context(
                            runtime.final_output(
                                user, svc, inp, result, authorization="Bearer " + token.token if token else None
                            )
                        )
                    if stats is not None:
                        annotate(
                            current,
                            model_calls=stats.model_calls,
                            cache_hit=stats.cache_hit,
                            retrieval_version=stats.retrieval_version or PRODUCTION_RETRIEVAL_VERSION,
                            policy_version=stats.policy_version or "",
                        )
                    _audit(runtime, user, trace_id, name, inp, "answered", (), result, started, stats)
            except MedOpsError as exc:
                annotate(current, error_code=exc.code.value)
                if user is not None:
                    stats = getattr(svc, "audit_stats", None)
                    _audit(
                        runtime,
                        user,
                        trace_id,
                        name,
                        inp,
                        "refused" if exc.code in _REFUSAL_CODES else "escalated",
                        (exc.code.value,),
                        None,
                        started,
                        stats,
                    )
                # ToolError text is returned verbatim as isError; anything else would be wrapped as an unexpected error
                raise ToolError(f"{exc.code.value}: {exc.message}") from None
            return result

    @server.tool(name="search_documents", description=specs["search_documents"].description, annotations=READ_ONLY)
    def search_documents(input: SearchDocumentsInput) -> dict[str, Any]:
        return run("search_documents", "search_documents", input)

    @server.tool(name="get_chunk", description=specs["get_chunk"].description, annotations=READ_ONLY)
    def get_chunk(input: GetChunkInput) -> dict[str, Any]:
        return run("get_chunk", "get_chunk", input)

    @server.tool(name="verify_citation", description=specs["verify_citation"].description, annotations=READ_ONLY)
    def verify_citation(input: VerifyCitationInput) -> dict[str, Any]:
        return run("verify_citation", "verify_citation", input)

    @server.tool(
        name="list_active_versions", description=specs["list_active_versions"].description, annotations=READ_ONLY
    )
    def list_active_versions(input: ListActiveVersionsInput) -> dict[str, Any]:
        return run("list_active_versions", "list_active_versions", input)

    return server


# ------------------------------------------------------------------------------------ production runtime


@dataclass
class McpProductionRuntime:
    """Read-only DSN (medops_readonly LOGIN user); identity from the API's authenticator; search over the same
    production retrieval stack as the harness, built per call inside the read-only transaction."""

    authenticator: Authenticator | None
    dev_identity: UserContext | None
    readonly_dsn: str
    app_dsn_for_directory: str
    searcher_factory: Any = None  # Callable[[conn, user], Searcher] | None
    settings: Settings | None = None
    _final_audit_conn: ContextVar[Any] = field(
        default_factory=lambda: ContextVar("mcp_final_audit_conn", default=None), repr=False
    )

    @contextmanager
    def directory(self) -> Iterator[PrincipalDirectory]:
        from medops.infrastructure.identity import PgDirectory

        with open_connection(self.app_dsn_for_directory, self.settings) as conn, conn.transaction():
            yield PgDirectory(conn)

    def audit(self, trace: TraceRecord) -> None:
        from medops.infrastructure.db.audit import PgTraceStore

        held = self._final_audit_conn.get()
        if held is not None:
            PgTraceStore(held).record(trace, None)
        else:
            with open_connection(self.app_dsn_for_directory, self.settings) as conn, conn.transaction():
                PgTraceStore(conn).record(trace, None)

    @contextmanager
    def final_output(
        self, user: UserContext, service: ServiceLike, inp: Any, result: dict[str, Any], *, authorization: str | None
    ) -> Iterator[None]:
        if not isinstance(service, McpService):
            raise BusinessError(ErrorCode.forbidden, "unbound MCP service")
        try:
            with (
                deadline_scope(5.0),
                open_connection(self.app_dsn_for_directory, self.settings) as raw,
                raw.transaction(),
            ):
                conn = DeadlineConnection(raw)
                acquire_output_fence(conn)
                if database_identity(conn) != database_identity(DeadlineConnection(service._conn)):
                    raise BusinessError(ErrorCode.forbidden, "MCP facts and identity must use the same database")
                current = (
                    self.authenticator.authenticate(
                        authorization,
                        PgDirectory(conn),
                    )
                    if authorization and self.authenticator
                    else directory_user(conn, user)
                )
                # Fixed stdio development identities may deliberately have no
                # directory row. Existing/inactive rows never use this fallback.
                if current is None and self.authenticator is None and self.dev_identity == user:
                    row = conn.execute("select 1 from principals where sub_pseudonym=%s", (user.user_id,)).fetchone()
                    if row is None:
                        current = user
                require_same_user(user, current)
                service.validate_final_output(inp, result)
                token = self._final_audit_conn.set(conn)
                try:
                    yield
                finally:
                    self._final_audit_conn.reset(token)
        except psycopg.Error as exc:
            from medops.core.errors import InfrastructureError

            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail=type(exc).__name__, retryable=False
            ) from None

    @contextmanager
    def service(self, user: UserContext) -> Iterator[ServiceLike]:
        with open_connection(self.readonly_dsn, self.settings) as conn, conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
            searcher = self.searcher_factory(conn, user) if self.searcher_factory is not None else None
            yield McpService(conn, user, searcher)
