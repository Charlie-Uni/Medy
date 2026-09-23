"""Production wiring for the API (M3-01/05/12): PostgreSQL under the application role with one transaction per
request, the principal directory, the production retrieval stack pinned to one model thread, the OpenAI gateway
behind the monthly budget, the operation-key ledger, and the pinned production model configuration."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import psycopg

from medops.api.app import ApiRuntime
from medops.api.auth import Authenticator, JwtVerifier, PgDirectory
from medops.api.contracts import AskRequest
from medops.core.config import Settings
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.executions import PgExecutionStore
from medops.harness.nodes import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL, production_model_config_version
from medops.harness.retrieval_port import ProductionRetrieval
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.gateway import OPENAI_PRICES, ModelGateway, PriceTable
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway
from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_lexical_retriever,
    production_lexical_versions,
    production_vector_retriever,
)
from medops.skills.catalog import default_registry

POLICY_VERSION = "policy-m3-api-1"  # released policy records arrive with M4; until then one pinned constant


def authenticator_from_settings(settings: Settings) -> Authenticator:
    missing = [
        k
        for k in ("oidc_issuer", "oidc_audience", "oidc_jwks_json", "identity_pseudonym_key")
        if getattr(settings, k) is None
    ]
    if missing:
        raise ValueError(f"API identity boundary needs {', '.join(missing)} (ADR-0001)")
    assert (
        settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_json and settings.identity_pseudonym_key
    )
    groups = json.loads(settings.oidc_group_scopes_json) if settings.oidc_group_scopes_json else {}
    return Authenticator(
        verifier=JwtVerifier(
            issuer=settings.oidc_issuer, audience=settings.oidc_audience, jwks=json.loads(settings.oidc_jwks_json)
        ),
        pseudonym_key=settings.identity_pseudonym_key.get_secret_value().encode("utf-8"),
        group_scopes={str(k): [str(s) for s in v] for k, v in groups.items()},
    )


@dataclass
class ProductionRuntime:
    """Built once per process; `connection()` opens a fresh application-role connection per request."""

    settings: Settings
    authenticator: Authenticator
    gateway: ModelGateway
    embedding: Any
    reranker: Any
    versions: VersionSet
    as_of: date | None = None
    _dsn: str = field(default="", repr=False)

    @classmethod
    def from_settings(
        cls, settings: Settings, *, device: str = "cpu", pinned_timeout_s: float = 120.0
    ) -> ProductionRuntime:
        from medops.retrieval.rerank import BgeRerankerV2M3
        from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

        pinned = PinnedThread(pinned_timeout_s)
        embedding = PinnedEmbedding(pinned.call(lambda: BgeM3EmbeddingProvider(device=device)), pinned)
        reranker = PinnedReranker(pinned.call(lambda: BgeRerankerV2M3(device=device, output=RERANK_OUTPUT)), pinned)
        gateway = BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
        versions = VersionSet(
            policy_version=POLICY_VERSION,
            retrieval_version=PRODUCTION_RETRIEVAL_VERSION,
            skill_version_set=default_registry().version_set(),
            model_config_version=production_model_config_version(),
        )
        runtime = cls(
            settings=settings,
            authenticator=authenticator_from_settings(settings),
            gateway=gateway,
            embedding=embedding,
            reranker=reranker,
            versions=versions,
        )
        runtime._dsn = settings.database_url.get_secret_value()
        return runtime

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        with psycopg.connect(self._dsn) as conn:
            with conn.transaction():
                yield conn

    def directory(self, conn: Any) -> PgDirectory:
        return PgDirectory(conn)

    def bind_identity(self, conn: Any, user: UserContext) -> None:
        conn.execute(
            "select set_config('medops.dept', %s, true)", (user.dept.value,)
        )  # transaction-local (baseline 3.7)

    def build_deps(self, conn: Any, user: UserContext, request: AskRequest) -> HarnessDeps:
        as_of = request.historical.as_of if request.historical is not None else self.as_of

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn  # already inside the request transaction with the department injected

        retrieval = ProductionRetrieval(
            conn_for_user=conn_for_user,
            lexical_factory=lambda c: production_lexical_retriever(c, as_of=as_of),
            vector_factory=lambda c: production_vector_retriever(c, self.embedding, as_of=as_of),
            reranker=self.reranker,
            config=production_hybrid_config(),
            lexical_versions=production_lexical_versions(),
        )
        return HarnessDeps(
            retrieval=retrieval,
            gateway=self.gateway,
            answer_model_id=PRODUCTION_ANSWER_MODEL,
            judge_model_id=PRODUCTION_JUDGE_MODEL,
            as_of=as_of,
            executions=PgExecutionStore(conn),
        )

    def ready(self) -> bool:
        try:
            with psycopg.connect(self._dsn, connect_timeout=2) as conn:
                conn.execute("select 1").fetchone()
            return True
        except psycopg.Error:
            return False


def _check_protocol(runtime: ProductionRuntime) -> ApiRuntime:  # structural conformance, checked by mypy
    return runtime
