"""Shared fact planes for safety, replay and recall diagnostics; no CLI or model loading at import time."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import psycopg

from medops.domain.identity import UserContext
from medops.evals.safety_data import admin_dsn, with_database
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


class Plane:
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

        @contextmanager
        def conn_for_user(user: UserContext):
            with self.conn.transaction():
                self.conn.execute("select set_config('medops.dept', %s, true)", (user.dept.value,))
                yield self.conn

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

    def resolve_chunks(self, chunk_ids: list[str]) -> dict[str, dict]:
        ids = sorted({c for c in chunk_ids if c})
        if not ids:
            return {}
        rows = self.admin.execute(
            """select c.chunk_id::text, d.doc_id::text, d.document_key, d.status::text, so.source_hash
               from chunks c join documents d on d.doc_id = c.doc_id
               join source_objects so on so.source_object_id = d.source_object_id
               where c.chunk_id::text = any(%s)""",
            (ids,),
        ).fetchall()
        return {r[0]: {"doc_id": r[1], "document_key": r[2], "status": r[3], "source_hash": r[4]} for r in rows}

    def docs_for_hashes(self, hashes: list[str]) -> dict[str, str]:
        rows = self.admin.execute(
            """select so.source_hash, d.document_key from documents d
               join source_objects so on so.source_object_id = d.source_object_id where so.source_hash = any(%s)""",
            (hashes,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def canary_chunks(self, canary: str) -> list[str]:
        return [
            r[0]
            for r in self.admin.execute(
                "select chunk_id::text from chunks where content like %s", (f"%{canary}%",)
            ).fetchall()
        ]


EXIT_STALLED = 75  # supervisor resumes the evaluation after a pinned model call times out
