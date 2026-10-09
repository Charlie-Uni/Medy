"""Query translation for cross-lingual retrieval (record 95, released retrieval parameter `query_translation`).

Most corpus documents are English while most questions are Chinese; the lexical channel cannot bridge that and the
dense channel alone misses long-tail concepts (职业暴露, 安全公告). With `query_translation` set to a model id, the
question is rendered into English by one bounded model call and the rendering becomes one more *search query* that
joins the reciprocal-rank fusion next to the user's own query (see `multi_query`). The translation is never shown,
cited or given to the answer node: it only shapes which chunks are retrieved, and every chunk is still re-checked
and re-ranked against the user's question.

Bounds: skipped when the question has no CJK text; one call, small output, short timeout; any provider fault,
budget stop or malformed reply means "no translation" and the corpus-wide search proceeds unchanged (fail open,
recorded on the span). The call is metered like every other model call, so its tokens and cost sit on the trace.
The model id and this rule version enter `retrieval_version` through `rewrite_params` and the model id enters
`model_config_version`, so a released translation is as visible and as rollbackable as any other retrieval policy.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from typing import Any

from medops.core.errors import ErrorCode, InfrastructureError
from medops.core.telemetry import annotate, span
from medops.infrastructure.llm.budget import BudgetExceeded
from medops.infrastructure.llm.gateway import Message, ModelGateway, ModelOutputInvalid, ModelRequest

QUERY_TRANSLATION_VERSION = "qt-v1"
QUERY_TRANSLATION_OFF = "off"
ALLOWED_TRANSLATION_MODELS: frozenset[str] = frozenset({"gpt-6-luna", "gpt-6-sol"})  # ADR-0010 provider policy
MAX_TRANSLATION_CHARS = 400
_CJK = re.compile(r"[一-鿿]")

# Record 111 measured the throughput knee between four and eight concurrent requests. Translation is remote I/O,
# while original retrieval uses PostgreSQL and the pinned local model thread, so four translation workers can overlap
# those independent paths. Capacity includes four running and four queued calls; further callers receive backpressure.
TRANSLATION_WORKERS = 4
TRANSLATION_CAPACITY = 8
TRANSLATION_QUEUE_WAIT_S = 0.25

SYSTEM = (
    "You translate a regulatory / pharmacovigilance / clinical question into English so it can be matched against "
    "English guidance documents. Rules: translate faithfully and completely; keep drug names, product names, document "
    "codes (ICH E6(R3), GVP Module IX, 21 CFR 312.32), numbers, units, dates and negations exactly as they are; use the "
    "standard regulatory English terms (marketing authorisation holder, periodic safety update report, adverse "
    "reaction, informed consent); do not answer the question, do not add or drop conditions, do not explain. "
    "Output JSON only."
)
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}


class TranslationPool:
    """A process-wide bounded translation executor.

    Capacity includes running and queued calls. A caller waits briefly for a slot and then fails closed with a
    retryable dependency timeout: it never starts an unbounded caller thread and never silently drops a released
    retrieval step. ContextVars are copied so translation/model spans remain children of the request trace.
    """

    def __init__(
        self,
        *,
        workers: int = TRANSLATION_WORKERS,
        capacity: int = TRANSLATION_CAPACITY,
        queue_wait_s: float = TRANSLATION_QUEUE_WAIT_S,
    ) -> None:
        if workers < 1 or capacity < workers or queue_wait_s <= 0:
            raise ValueError("translation capacity must cover positive workers and queue wait must be positive")
        self._slots = threading.BoundedSemaphore(capacity)
        self._queue_wait_s = queue_wait_s
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="query-translation")

    def submit(self, translate: Callable[[str], str | None], query: str) -> Future[str | None]:
        if not self._slots.acquire(timeout=self._queue_wait_s):
            raise InfrastructureError(
                ErrorCode.dependency_timeout,
                detail="query translation queue remained saturated",
                retryable=True,
            )
        context = copy_context()
        try:
            future = self._executor.submit(context.run, translate, query)
        except BaseException:  # executor shutdown/race: release the capacity before preserving the original error
            self._slots.release()
            raise
        future.add_done_callback(lambda _future: self._slots.release())
        return future

    def shutdown(self) -> None:
        """Tests and explicit process teardown may wait for accepted work; production uses interpreter shutdown."""
        self._executor.shutdown(wait=True)


DEFAULT_TRANSLATION_POOL = TranslationPool()


class QueryTranslator:
    """One bounded translation per call; returns None whenever the search should proceed without a translation."""

    def __init__(self, gateway: ModelGateway, model_id: str, *, timeout_s: float = 8.0, max_output_tokens: int = 240):
        if model_id not in ALLOWED_TRANSLATION_MODELS:
            raise ValueError(f"query translation model {model_id!r} is not in the allowed set")
        self._gateway = gateway
        self.model_id = model_id
        self._timeout_s = timeout_s
        self._max_output_tokens = max_output_tokens

    @property
    def version(self) -> str:
        return f"{QUERY_TRANSLATION_VERSION}:{self.model_id}"

    def translate(self, query: str) -> str | None:
        if not _CJK.search(query):
            return None  # already in the documents' language
        with span("retrieval.translate", model_id=self.model_id) as current:
            try:
                response = self._gateway.complete(
                    ModelRequest(
                        purpose="query_translation",
                        model_id=self.model_id,
                        messages=(Message(role="system", content=SYSTEM), Message(role="user", content=query)),
                        max_output_tokens=self._max_output_tokens,
                        json_schema=SCHEMA,
                        timeout_s=self._timeout_s,
                    )
                )
                parsed = response.parsed if response.parsed is not None else json.loads(response.text)
                text = str(parsed.get("translation", "")).strip() if isinstance(parsed, dict) else ""
            except (InfrastructureError, BudgetExceeded, ModelOutputInvalid, ValueError, TypeError) as exc:
                annotate(current, outcome="skipped", reason=type(exc).__name__)
                return None
            if response.truncated or not text or len(text) > MAX_TRANSLATION_CHARS or _CJK.search(text):
                annotate(current, outcome="rejected")
                return None  # incomplete, empty, overlong or not actually English: search without it
            annotate(current, outcome="ok", chars=len(text))
            return text
