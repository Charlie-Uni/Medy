"""Required evidence groups: OR within a group, AND across groups."""

from collections.abc import Iterable, Sequence
from typing import Any


def all_required_evidence(groups: Sequence[Sequence[str]], cited: Iterable[str]) -> bool:
    """Empty/unmappable groups remain misses; no gold is not a successful citation."""
    available = set(cited)
    return bool(groups) and all(bool(set(group) & available) for group in groups)


def replay_gold_cited(item: dict[str, Any], cited: list[str]) -> bool:
    """New exports preserve groups; historical flat exports keep their original any-hit rule."""
    if "required_gold_groups" in item:
        return all_required_evidence(item["required_gold_groups"], cited)
    return bool(set(item["gold_chunks"]) & set(cited))
