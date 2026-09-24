"""Read-only MCP server (M3-06) on the official SDK 2.x: exactly the four tools of `MCP_TOOLS`, all flagged
read-only, identity from the verified bearer token (Streamable HTTP) or a fixed synthetic identity in stdio
mode (dev/test only). Each call opens the read-only database connection, injects the caller's department and
runs `McpService`; the database role proves the tools cannot write."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from medops.api.auth import Authenticator, PrincipalDirectory
from medops.core.errors import BusinessError, ErrorCode, MedOpsError
from medops.core.telemetry import annotate, span
from medops.domain.identity import UserContext
from medops.mcp.contracts import (
    MCP_TOOLS,
    GetChunkInput,
    ListActiveVersionsInput,
    SearchDocumentsInput,
    VerifyCitationInput,
)
from medops.mcp.service import McpService

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


class ServiceLike(Protocol):
    def search_documents(self, inp: SearchDocumentsInput) -> Any: ...

    def get_chunk(self, inp: GetChunkInput) -> Any: ...

    def verify_citation(self, inp: VerifyCitationInput) -> Any: ...

    def list_active_versions(self, inp: ListActiveVersionsInput) -> Any: ...


class McpRuntime(Protocol):
    authenticator: Authenticator | None  # None only for stdio dev mode
    dev_identity: UserContext | None  # stdio dev/test identity; never used when a token is present

    def directory(self) -> AbstractContextManager[PrincipalDirectory]: ...

    def service(self, user: UserContext) -> AbstractContextManager[ServiceLike]: ...


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

    specs = {t.name: t for t in MCP_TOOLS}

    def run(name: str, method: str, inp: Any) -> dict[str, Any]:
        with span("mcp.tool", tool=name) as current:
            try:
                user = _current_user(runtime)
                annotate(current, dept=user.dept.value)
                with runtime.service(user) as svc:
                    return getattr(svc, method)(inp).model_dump(mode="json")
            except MedOpsError as exc:
                annotate(current, error_code=exc.code.value)
                # ToolError text is returned verbatim as isError; anything else would be wrapped as an unexpected error
                raise ToolError(f"{exc.code.value}: {exc.message}") from None

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

    @contextmanager
    def directory(self) -> Iterator[PrincipalDirectory]:
        import psycopg

        from medops.api.auth import PgDirectory

        with psycopg.connect(self.app_dsn_for_directory) as conn, conn.transaction():
            yield PgDirectory(conn)

    @contextmanager
    def service(self, user: UserContext) -> Iterator[ServiceLike]:
        import psycopg

        with psycopg.connect(self.readonly_dsn) as conn, conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
            searcher = self.searcher_factory(conn, user) if self.searcher_factory is not None else None
            yield McpService(conn, user, searcher)
