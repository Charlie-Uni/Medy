"""`python -m medops.mcp.serve --transport streamable-http|stdio`. Streamable HTTP requires the OIDC settings and
the read-only DSN; stdio is refused in prod and runs under a fixed synthetic identity (`--dev-dept`)."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

from medops.api.runtime import authenticator_from_settings
from medops.application.policy_loader import ReleaseState, load_release_state
from medops.core.config import AppEnv, Settings, safe_config_errors
from medops.core.logging import configure_logging, get_logger
from medops.core.telemetry import configure_telemetry
from medops.core.telemetry import shutdown as shutdown_telemetry
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.mcp.server import McpProductionRuntime, build_server


def _searcher_factory(device: str, settings: Settings):
    """Search over the same production stack as the API, under the same released policy: the release state
    (pointers + canary shares) is re-read every `policy_reload_ttl_s` seconds on the read-only connection and
    split per principal exactly as the API does (M4-03 / M4-09)."""
    import time

    from medops.harness.retrieval_port import ProductionRetrieval, RetrievalRequest
    from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
    from medops.retrieval.production import (
        RERANK_OUTPUT,
        production_hybrid_config,
        production_lexical_retriever,
        production_lexical_versions,
        production_vector_retriever,
    )
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    pinned = PinnedThread(120.0)
    embedding = PinnedEmbedding(pinned.call(lambda: BgeM3EmbeddingProvider(device=device)), pinned)
    rerankers: dict[int, Any] = {}
    cache: dict[str, Any] = {}
    ttl = float(settings.policy_reload_ttl_s)

    def reranker_for(output: int):
        if output not in rerankers:
            rerankers[output] = PinnedReranker(
                pinned.call(lambda: BgeRerankerV2M3(device=device, output=output)), pinned
            )
        return rerankers[output]

    glossaries: dict[str, Any] = {}

    def glossary_for(version: str):
        from medops.retrieval.glossary_store import load_versioned_glossary

        if version not in glossaries:
            glossaries[version] = load_versioned_glossary(settings.glossary_dir, version)
        return glossaries[version]

    def state_for(conn) -> ReleaseState:
        now = time.monotonic()
        if "state" not in cache or now - cache["at"] >= ttl:
            cache["state"], cache["at"] = load_release_state(conn), now
        return cache["state"]

    def factory(conn, user: UserContext):
        from contextlib import contextmanager

        routed = state_for(conn).for_principal(user.user_id).policies
        hybrid = routed.hybrid_config(production_hybrid_config())
        reranker = reranker_for(routed.rerank_output(RERANK_OUTPUT))
        glossary = glossary_for(routed.glossary_version())

        @contextmanager
        def conn_for_user(_u):
            yield conn

        def search(query: str, k: int, *, as_of: date | None, allow_historical: bool):
            retrieval = ProductionRetrieval(
                conn_for_user=conn_for_user,
                lexical_factory=lambda c: production_lexical_retriever(c, as_of=as_of),
                vector_factory=lambda c: production_vector_retriever(c, embedding, as_of=as_of),
                reranker=reranker,
                config=hybrid,
                lexical_versions=production_lexical_versions(),
                glossary=glossary,
                multi_query=routed.multi_query(),
                doc_focus=routed.doc_focus(),
            )
            outcome = retrieval.retrieve(
                RetrievalRequest(query=query, user=user, as_of=as_of, historical_requested=allow_historical)
            )
            return outcome.evidence

        return search

    return factory


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
    # stdio: stdout is the JSON-RPC channel, so structured logs must go to stderr or they corrupt the protocol stream
    configure_logging(settings.log_level, stream=sys.stderr if args.transport == "stdio" else None)
    configure_telemetry(
        endpoint=settings.otel_exporter_otlp_endpoint,
        service_name=settings.otel_service_name,
        headers=settings.otel_exporter_otlp_headers.get_secret_value() if settings.otel_exporter_otlp_headers else None,
    )
    log = get_logger(__name__)
    if settings.database_readonly_url is None:
        print(
            "DATABASE_READONLY_URL is required: the MCP server must run under the read-only role (INV-AUTH-04)",
            file=sys.stderr,
        )
        return 2
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
        runtime = McpProductionRuntime(
            authenticator=None,
            dev_identity=dev,
            readonly_dsn=settings.database_readonly_url.get_secret_value(),
            app_dsn_for_directory=settings.database_url.get_secret_value(),
            searcher_factory=_searcher_factory(args.device, settings),
        )
        log.info("mcp stdio (dev) starting", extra={"dept": args.dev_dept})
        build_server(runtime).run("stdio")
        shutdown_telemetry()
        return 0
    runtime = McpProductionRuntime(
        authenticator=authenticator_from_settings(settings),
        dev_identity=None,
        readonly_dsn=settings.database_readonly_url.get_secret_value(),
        app_dsn_for_directory=settings.database_url.get_secret_value(),
        searcher_factory=_searcher_factory(args.device, settings),
    )
    server = build_server(runtime, issuer_url=settings.oidc_issuer, resource_url=f"http://{args.host}:{args.port}/mcp")
    log.info("mcp streamable-http starting", extra={"host": args.host, "port": args.port})
    import functools

    import anyio

    anyio.run(functools.partial(server.run_streamable_http_async, host=args.host, port=args.port))
    shutdown_telemetry()
    return 0


if __name__ == "__main__":
    sys.exit(main())
