"""Shared fact planes for safety, replay and recall diagnostics; no CLI or model loading at import time."""

from __future__ import annotations

from datetime import date
from functools import partial

import psycopg

from medops.domain.identity import UserContext
from medops.evals.fact_lookups import FactLookups
from medops.evals.safety_data import admin_dsn, with_database
from medops.evals.transactions import dept_connection
from medops.harness.assembly import build_retrieval
from medops.harness.dependencies import HarnessDeps
from medops.harness.production import (
    PRODUCTION_ANSWER_MODEL,
    PRODUCTION_JUDGE_MODEL,
)
from medops.retrieval.production import (
    production_hybrid_config,
)


class CountingRetrieval:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def retrieve(self, request):
        self.calls += 1
        return self._inner.retrieve(request)


class Plane(FactLookups):
    """One fact plane: app connection (RLS), admin connection (judge lookups), retrieval and harness deps."""

    def __init__(
        self,
        name: str,
        app_url: str,
        provider,
        reranker,
        gateway,
        as_of: date,
        *,
        config=None,
        answer_system=None,
        glossary=None,
        multi_query=False,
        doc_focus=False,
        source_constraint=False,
        query_translation="off",
        evidence_focus="off",
        answer_models=None,
        lexical_factory=None,
        admin_url=None,
        execution_limits=None,
    ):
        # `config` / `answer_system`: an arm of the replay runner (M4-07) evaluates a candidate policy overlay; the
        # safety runner itself keeps the production values
        self.name = name
        self._config = config or production_hybrid_config()
        self._answer_system = answer_system
        self._glossary = glossary  # a released glossary version resolved by the caller (record 93)
        self._multi_query = multi_query
        self._doc_focus = doc_focus
        self._source_constraint = source_constraint
        from medops.retrieval.query_translation import QueryTranslator

        self._translator = QueryTranslator(gateway, query_translation).translate if query_translation != "off" else None
        # ADR-0002 revision 5: an experiment server (candidate D) is reached through explicit DSNs and its own
        # lexical channel; everything else (vector channel, re-check, rerank) is the production code
        self._lexical_factory = lexical_factory
        self.conn = psycopg.connect(with_database(app_url, name), connect_timeout=5)
        self._fact_dsn = admin_url or admin_dsn(name)
        try:
            self.admin = psycopg.connect(self._fact_dsn, connect_timeout=5)
            self.admin.read_only = True
            self.admin.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            from medops.retrieval.integrity import require_retrieval_integrity

            self.admin.execute("set local statement_timeout=5000")
            self.index_preflight = require_retrieval_integrity(
                self.admin, plane=name, embedding=provider.spec, request_conn=self.conn
            )
            from medops.evals.run_conditions import fact_snapshot

            self.fact_snapshot = fact_snapshot(self.admin)
            self.admin.rollback()
            self.admin.isolation_level = None  # later judge lookups keep their original READ COMMITTED behavior
            self.conn.rollback()
        except Exception:
            self.conn.close()
            if hasattr(self, "admin"):
                self.admin.close()
            raise

        conn_for_user = partial(dept_connection, self.conn)

        self.conn_for_user = conn_for_user
        self._provider, self._reranker = provider, reranker
        self.retrieval = self.retrieval_for(as_of)
        extra = {"answer_system": answer_system} if answer_system else {}
        self.deps = HarnessDeps(
            retrieval=self.retrieval,
            gateway=gateway,
            answer_model_id=PRODUCTION_ANSWER_MODEL,
            judge_model_id=PRODUCTION_JUDGE_MODEL,
            as_of=as_of,
            evidence_focus=evidence_focus,
            sentence_scorer=reranker.score,
            doc_titles=self._doc_titles,
            answer_model_by_intent=dict(answer_models or {}),
            execution_limits=execution_limits,
            **extra,
        )
        self.as_of = as_of

    def _doc_titles(self, user: UserContext, doc_ids) -> dict[str, str]:
        from medops.retrieval.doc_focus import load_titles

        with self.conn_for_user(user) as conn:  # the reader's own department scope
            return load_titles(conn, doc_ids)

    def current_fact_snapshot(self) -> dict:
        """A fresh global snapshot used by long-running evaluation drift guards."""
        from medops.evals.run_conditions import fact_snapshot_from_dsn

        return fact_snapshot_from_dsn(self._fact_dsn)

    def retrieval_for(self, as_of: date) -> CountingRetrieval:
        """Retrieval whose channels filter the effective window at `as_of` (explicit historical requests)."""
        return CountingRetrieval(
            build_retrieval(
                conn_for_user=self.conn_for_user,
                provider=self._provider,
                reranker=self._reranker,
                as_of=as_of,
                lexical_factory=self._lexical_factory,
                config=self._config,
                glossary=self._glossary,
                multi_query=self._multi_query,
                doc_focus=self._doc_focus,
                source_constraint=self._source_constraint,
                translator=self._translator,
            )
        )


EXIT_STALLED = 75  # supervisor resumes the evaluation after a pinned model call times out
