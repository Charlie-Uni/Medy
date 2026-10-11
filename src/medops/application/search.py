"""Transport-independent search execution result and port."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from medops.domain.evidence import Evidence
from medops.domain.state import VersionSet


@dataclass(frozen=True)
class SearchExecution:
    evidence: Sequence[Evidence]
    model_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    retrieval_version: str | None = None
    policy_version: str | None = None
    cache_hit: bool = False
    versions: VersionSet | None = None


class Searcher(Protocol):
    def __call__(
        self, query: str, k: int, *, as_of: date | None, allow_historical: bool
    ) -> Sequence[Evidence] | SearchExecution: ...
