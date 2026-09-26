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
from typing import Any

from medops.core.errors import InfrastructureError
from medops.core.telemetry import annotate, span
from medops.infrastructure.llm.budget import BudgetExceeded
from medops.infrastructure.llm.gateway import Message, ModelGateway, ModelOutputInvalid, ModelRequest

QUERY_TRANSLATION_VERSION = "qt-v1"
QUERY_TRANSLATION_OFF = "off"
ALLOWED_TRANSLATION_MODELS: frozenset[str] = frozenset({"gpt-6-luna", "gpt-6-sol"})  # ADR-0010 provider policy
MAX_TRANSLATION_CHARS = 400
_CJK = re.compile(r"[一-鿿]")

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
