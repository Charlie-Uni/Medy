"""Read-only search execution using the shared production composition.

Protocol adapters own authentication, transactions and result visibility checks.
This owner supplies bounded model resources and per-execution accounting.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from medops.application.policy_loader import RequestPolicies
from medops.application.search import SearchExecution
from medops.bootstrap.policies import PolicyRouter
from medops.bootstrap.retrieval import RetrievalServices, execution_binding
from medops.core.config import Settings
from medops.core.deadline import check_deadline, deadline_scope, execution_admission
from medops.core.run_artifacts import online_artifacts
from medops.domain.identity import UserContext
from medops.domain.query import resolve_query_context
from medops.harness.dependencies import default_specs
from medops.harness.retrieval_port import RetrievalRequest
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.llm.execution_budget import check_execution_budget, configured_limits, execution_scope
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.gateway import ModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.inference_process import InferenceProcess, ProcessEmbedding, ProcessReranker
from medops.retrieval.production import RERANK_OUTPUT
from medops.retrieval.query_translation import QUERY_TRANSLATION_OFF
from medops.retrieval.runtime import candidate_cache_from_settings
from medops.skills.catalog import default_registry


@dataclass
class SearchRuntime:
    settings: Settings
    retrieval: RetrievalServices
    policies: PolicyRouter
    _gateway: ModelGateway | None = field(default=None, repr=False)
    _lock: Any = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings, *, device: str = "cpu") -> SearchRuntime:
        pinned = InferenceProcess(device=device, output=RERANK_OUTPUT)
        try:
            return cls(
                settings,
                RetrievalServices(
                    settings,
                    ProcessEmbedding(pinned),
                    ProcessReranker(pinned, output=RERANK_OUTPUT),
                    pinned=pinned,
                    cache=candidate_cache_from_settings(settings),
                ),
                PolicyRouter(settings, default_registry().version_set()),
            )
        except BaseException:
            pinned.close()
            raise

    def __call__(self, conn: Any, user: UserContext) -> SearchOperation:
        routed = self.policies.route(DeadlineConnection(conn), user)
        return SearchOperation(self, conn, user, routed)

    def gateway(self) -> ModelGateway:
        with self._lock:
            if self._gateway is None:
                self._gateway = build_budgeted_gateway(self.settings, require_execution_budget=True)
            return self._gateway

    def close(self) -> None:
        try:
            if self._gateway is not None:
                close = getattr(self._gateway, "close", None)
                if close is not None:
                    close()
        finally:
            if self.retrieval.pinned is not None:
                self.retrieval.pinned.close()


@dataclass
class SearchOperation:
    owner: SearchRuntime
    conn: Any
    user: UserContext
    routed: RequestPolicies
    audit_stats: SearchExecution = field(default_factory=lambda: SearchExecution(()), init=False)

    def __post_init__(self) -> None:
        self.audit_stats = SearchExecution(
            (),
            retrieval_version=self.routed.versions.retrieval_version,
            policy_version=self.routed.versions.policy_version,
            versions=self.routed.versions,
        )

    def __call__(self, query: str, k: int, *, as_of: date | None, allow_historical: bool) -> SearchExecution:
        context = resolve_query_context({"as_of": as_of} if allow_historical else None, default_as_of=as_of)
        timeout = default_specs()["retrieve"].timeout_s
        meter = None
        outcome = None
        conditions = None
        limits = configured_limits(self.owner.settings, timeout_s=timeout)
        try:
            with (
                execution_scope(limits),
                deadline_scope(timeout),
                execution_admission(),
            ):
                check_deadline()
                conditions = {
                    "artifacts": online_artifacts(),
                    "routed": execution_binding(self.routed),
                    "execution_limits": limits.model_dump(mode="json"),
                    "facts_scope": "observed_retrieval_not_corpus_snapshot",
                    "original_conditions_available": False,
                }
                check_deadline()
                if self.routed.policies.query_translation() != QUERY_TRANSLATION_OFF:
                    meter = MeteredGateway(self.owner.gateway())
                retrieval = self.owner.retrieval.build(self.conn, self.user, context, self.routed, meter)
                check_deadline()
                outcome = retrieval.retrieve(
                    RetrievalRequest(
                        query=query,
                        user=self.user,
                        as_of=context.as_of,
                        historical_requested=context.historical_requested,
                    )
                )
                check_deadline()
                check_execution_budget()
                if meter is not None:
                    meter.call_journal.ensure_complete()
        finally:
            self.audit_stats = SearchExecution(
                outcome.evidence if outcome else (),
                model_calls=meter.calls if meter else 0,
                tokens=meter.tokens if meter else 0,
                cost_usd=meter.cost_usd if meter else 0.0,
                retrieval_version=self.routed.versions.retrieval_version,
                policy_version=self.routed.versions.policy_version,
                cache_hit=bool(outcome and outcome.cache_hit),
                versions=self.routed.versions,
                query_context=context,
                conditions=conditions,
                retrieval_snapshot=outcome.model_dump(mode="json") if outcome else None,
                call_records=meter.call_journal.snapshot() if meter else (),
                call_receipts=tuple(r.model_dump(mode="json") for r in meter.receipts) if meter else (),
                call_audit_complete=meter.call_journal.complete if meter else True,
            )
        assert outcome is not None
        return self.audit_stats
