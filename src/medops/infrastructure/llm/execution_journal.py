"""Opt-in durable execution journal, inherited by nested calls and copied contexts.

Admission must commit before operation() can run. Settlement is recorded even if
the caller has lost its lease; that does not authorize an output or another call.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Protocol

from medops.infrastructure.llm.gateway import ModelCallReceipt, ModelRequest, ModelResponse

if TYPE_CHECKING:
    from medops.infrastructure.llm.execution_budget import ExecutionBudget


class ExecutionJournal(Protocol):
    def admitted(self, request: ModelRequest, budget: ExecutionBudget) -> None: ...
    def settled(
        self,
        request: ModelRequest,
        receipt: ModelCallReceipt,
        response: ModelResponse | None,
        budget: ExecutionBudget,
    ) -> None: ...


_JOURNAL: ContextVar[ExecutionJournal | None] = ContextVar("execution_durable_journal", default=None)


def current_execution_journal() -> ExecutionJournal | None:
    return _JOURNAL.get()


@contextmanager
def execution_journal_scope(journal: ExecutionJournal) -> Iterator[None]:
    parent = _JOURNAL.get()
    if parent is not None and parent is not journal:
        raise ValueError("nested_execution_cannot_replace_journal")
    token = _JOURNAL.set(journal)
    try:
        yield
    finally:
        _JOURNAL.reset(token)
