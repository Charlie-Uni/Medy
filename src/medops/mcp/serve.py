"""`python -m medops.mcp.serve --transport streamable-http|stdio`. Streamable HTTP requires the OIDC settings and
the read-only DSN; stdio is refused in prod and runs under a fixed synthetic identity (`--dev-dept`)."""

from __future__ import annotations

import argparse
import sys

from medops.bootstrap.identity import authenticator_from_settings
from medops.bootstrap.search import SearchRuntime
from medops.core.config import AppEnv, Settings, safe_config_errors
from medops.core.logging import configure_logging, get_logger
from medops.core.telemetry import configure_telemetry, telemetry_options
from medops.core.telemetry import shutdown as shutdown_telemetry
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.mcp.server import McpProductionRuntime, build_server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", choices=("streamable-http", "stdio"), default="streamable-http")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--dev-dept", choices=[d.value for d in Dept], help="stdio only: synthetic identity's department")
    args = ap.parse_args(argv)
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001
        from pydantic import ValidationError

        print(
            f"configuration invalid: {safe_config_errors(exc) if isinstance(exc, ValidationError) else type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    if settings.database_readonly_url is None:
        print(
            "DATABASE_READONLY_URL is required: the MCP server must run under the read-only role (INV-AUTH-04)",
            file=sys.stderr,
        )
        return 2
    dev = None
    if args.transport == "stdio":
        if settings.app_env is AppEnv.prod:
            print("stdio transport is refused in prod (ADR-0001 §5)", file=sys.stderr)
            return 2
        if not args.dev_dept:
            print("stdio needs --dev-dept for the synthetic identity", file=sys.stderr)
            return 2
        dev = UserContext(
            user_id="stdio-dev-" + args.dev_dept.lower(),
            dept=Dept(args.dev_dept),
            roles=("dev",),
            acl_scopes=frozenset({f"{args.dev_dept}:read"}),
        )
    # stdout is the stdio JSON-RPC channel; logs must remain on stderr.
    configure_logging(settings.log_level, stream=sys.stderr if args.transport == "stdio" else None)
    configure_telemetry(**telemetry_options(settings))
    log = get_logger(__name__)
    factory = None
    try:
        authenticator = None if dev is not None else authenticator_from_settings(settings)
        factory = SearchRuntime.from_settings(settings, device=args.device)
        runtime = McpProductionRuntime(
            authenticator=authenticator,
            dev_identity=dev,
            readonly_dsn=settings.database_readonly_url.get_secret_value(),
            app_dsn_for_directory=settings.database_url.get_secret_value(),
            searcher_factory=factory,
            settings=settings,
        )
        if dev is not None:
            log.info("mcp stdio (dev) starting", extra={"dept": args.dev_dept})
            build_server(runtime).run("stdio")
            return 0
        server = build_server(
            runtime, issuer_url=settings.oidc_issuer, resource_url=f"http://{args.host}:{args.port}/mcp"
        )
        log.info("mcp streamable-http starting", extra={"host": args.host, "port": args.port})
        import functools

        import anyio

        anyio.run(functools.partial(server.run_streamable_http_async, host=args.host, port=args.port))
        return 0
    finally:
        try:
            close = getattr(factory, "close", None)
            if close is not None:
                close()
        finally:
            shutdown_telemetry()


if __name__ == "__main__":
    sys.exit(main())
