"""Dependency and policy contract of the fixed Harness, shared by nodes and callers."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from medops.domain.identity import UserContext
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.contracts import NodeSpec
from medops.harness.evidence_focus import SentenceScorer, needs_titles
from medops.harness.executions import ExecutionStore
from medops.harness.focus_profiles import ALLOWED_EVIDENCE_FOCUS, EVIDENCE_FOCUS_OFF, FOCUS_PARAMS
from medops.harness.retrieval_port import RetrievalPort
from medops.infrastructure.llm.gateway import (
    ModelGateway,
)


def default_specs() -> dict[str, NodeSpec]:
    return {
        "intent": NodeSpec(name="intent", timeout_s=5),
        "retrieve": NodeSpec(name="retrieve", timeout_s=20),
        "verify": NodeSpec(name="verify", timeout_s=30),
        "safety": NodeSpec(name="safety", timeout_s=5),
        "answer": NodeSpec(name="answer", timeout_s=60),
        "escalate": NodeSpec(name="escalate", timeout_s=5, max_retries=0),
    }


@dataclass(frozen=True)
class HarnessDeps:
    retrieval: RetrievalPort
    gateway: ModelGateway
    answer_model_id: str
    judge_model_id: str | None = None  # None: rules + containment only (DEC-003 pending)
    specs: Mapping[str, NodeSpec] = field(default_factory=default_specs)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    as_of: date | None = None
    answer_max_output_tokens: int = 800
    executions: ExecutionStore | None = None  # M2-03 operation-key ledger; None = no persistence (unit tests)
    answer_system: str = ANSWER_SYSTEM  # released prompt policy may override (M4-03); the trace's model config says so
    # released `model_route/answer` (record 122): intent type -> answer model; other intents use answer_model_id
    answer_model_by_intent: Mapping[str, str] = field(default_factory=dict)
    evidence_focus: str = EVIDENCE_FOCUS_OFF  # released layout of the evidence in the answer prompt (M5-04)
    sentence_scorer: SentenceScorer | None = None  # the reranker's scorer; required by the sentfocus versions
    # titles of evidence documents as the reader's own connection sees them; required by `sentfocus-v7`
    doc_titles: Callable[[UserContext, Sequence[str]], Mapping[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.evidence_focus not in ALLOWED_EVIDENCE_FOCUS:
            raise ValueError(f"unknown evidence focus mode {self.evidence_focus!r}")
        if self.evidence_focus in FOCUS_PARAMS and self.sentence_scorer is None:
            raise ValueError(f"evidence focus {self.evidence_focus} needs a sentence scorer")
        if needs_titles(self.evidence_focus) and self.doc_titles is None:
            raise ValueError(f"evidence focus {self.evidence_focus} needs a document-title lookup")
