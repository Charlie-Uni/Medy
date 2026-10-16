"""Production retrieval resources and request assembly, independent of HTTP/MCP."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from medops.application.policy_loader import RequestPolicies, policy_snapshot
from medops.core.config import Settings
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.harness.assembly import build_retrieval
from medops.harness.retrieval_port import ProductionRetrieval
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.glossary_store import load_versioned_glossary
from medops.retrieval.production import RERANK_OUTPUT, production_hybrid_config
from medops.retrieval.query_translation import QUERY_TRANSLATION_OFF, QueryTranslator
from medops.retrieval.rerank import RerankerView
from medops.retrieval.rewrite import GLOSSARY_NONE


@dataclass
class RetrievalServices:
    """One owner of process resources. Does not open transactions or select user identities."""

    settings: Settings
    embedding: Any
    reranker: Any
    pinned: Any = None
    cache: Any = None
    _rerankers: dict[int, Any] = field(default_factory=dict, repr=False)
    _glossaries: dict[str, Any] = field(default_factory=dict, repr=False)
    _lock: Any = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        output = getattr(getattr(self.reranker, "spec", None), "output", None)
        if isinstance(output, int):
            self._rerankers.setdefault(output, self.reranker)

    def reranker_for(self, output: int) -> Any:
        if type(output) is not int or not 1 <= output <= self.reranker.spec.max_input:
            raise ValueError("invalid reranker output")
        with self._lock:
            if output not in self._rerankers:
                self._rerankers[output] = RerankerView(self.reranker, output=output)
            return self._rerankers[output]

    def glossary_for(self, version: str) -> Any:
        if version == GLOSSARY_NONE:
            return None
        with self._lock:
            if version not in self._glossaries:
                self._glossaries[version] = load_versioned_glossary(self.settings.glossary_dir, version)
            return self._glossaries[version]

    def build(
        self,
        conn: Any,
        user: UserContext,
        context: QueryContext,
        routed: RequestPolicies,
        meter: MeteredGateway | None,
    ) -> ProductionRetrieval:
        """Use the caller's department-bound transaction and one pinned calendar context."""
        conn = DeadlineConnection(conn)

        @contextmanager
        def conn_for_user(request_user: UserContext) -> Iterator[Any]:
            if request_user != user:
                raise BusinessError(ErrorCode.forbidden, "retrieval identity differs from the bound transaction")
            yield conn

        policies = routed.policies
        translation_model = policies.query_translation()
        if translation_model != QUERY_TRANSLATION_OFF and meter is None:
            raise ValueError("query translation requires the execution's metered gateway")
        translator = (
            QueryTranslator(meter, translation_model)
            if translation_model != QUERY_TRANSLATION_OFF and meter is not None
            else None
        )
        return build_retrieval(
            conn_for_user=conn_for_user,
            as_of=context.as_of,
            provider=self.embedding,
            reranker=self.reranker_for(policies.rerank_output(RERANK_OUTPUT)),
            config=policies.hybrid_config(production_hybrid_config()),
            glossary=self.glossary_for(policies.glossary_version()),
            multi_query=policies.multi_query(),
            doc_focus=policies.doc_focus(),
            source_constraint=policies.source_constraint(),
            translator=translator.translate if translator is not None else None,
            translation_request=translator.request if translator is not None else None,
            cache=self.cache,
            cache_versions=(routed.versions.retrieval_version, routed.versions.policy_version) if self.cache else None,
        )


def execution_binding(routed: RequestPolicies) -> dict[str, Any]:
    """Actual configuration bound to this selection, shared with the execution recorder."""
    policies = routed.policies
    return {
        "policy_snapshot": policy_snapshot(policies),
        "canary_ids": list(routed.canary_ids),
        "retrieval": asdict(policies.hybrid_config(production_hybrid_config())),
        "rerank_output": policies.rerank_output(RERANK_OUTPUT),
        "glossary_version": policies.glossary_version(),
        "multi_query": policies.multi_query(),
        "doc_focus": policies.doc_focus(),
        "source_constraint": policies.source_constraint(),
        "query_translation_model": policies.query_translation(),
    }
