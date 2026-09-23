"""The delivered Skills (M2-12: the two low-risk ones). Adding a Skill here is a policy release: its version tag
enters every run's `skill_version_set`."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from medops.skills import citation_verification, label_query
from medops.skills.registry import SkillRegistry

SKILL_CATALOG_VERSION = "skills-v1"


def default_registry(
    *, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], datetime] | None = None, max_parallel: int = 4
) -> SkillRegistry:
    registry = SkillRegistry(sleep=sleep, clock=clock, max_parallel=max_parallel)
    registry.register(label_query.ENTRY)
    registry.register(citation_verification.ENTRY)
    return registry
