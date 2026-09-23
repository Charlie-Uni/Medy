"""The delivered Skills (M2-12 low-risk pair, M2-13 the three medium/high-risk ones). Adding a Skill here is a
policy release: its version tag enters every run's `skill_version_set`."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from medops.skills import ae_extraction, citation_verification, label_query, off_label_check, protocol_deviation
from medops.skills.registry import SkillRegistry

SKILL_CATALOG_VERSION = "skills-v2"


def default_registry(
    *, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], datetime] | None = None, max_parallel: int = 4
) -> SkillRegistry:
    registry = SkillRegistry(sleep=sleep, clock=clock, max_parallel=max_parallel)
    registry.register(label_query.ENTRY)
    registry.register(citation_verification.ENTRY)
    registry.register(ae_extraction.ENTRY)
    registry.register(protocol_deviation.ENTRY)
    registry.register(off_label_check.ENTRY)
    return registry
