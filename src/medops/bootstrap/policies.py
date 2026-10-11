"""One production policy/version rule, shared by all entry points."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from medops.application.policy_loader import (
    ReleaseState,
    RequestPolicies,
    RoutedPolicies,
    load_release_state,
)
from medops.core.config import Settings
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.production import production_model_config_version
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_retrieval_inputs,
)
from medops.retrieval.versioning import compute_retrieval_version

POLICY_VERSION = "policy-m3-api-1"  # Preserve the published bootstrap label.


def request_policies(routed: RoutedPolicies, skill_version_set: tuple[str, ...]) -> RequestPolicies:
    """Pin versions to the selected policy contents, never to a later release-state read."""
    pol = routed.policies
    retrieval_version = (
        compute_retrieval_version(
            production_retrieval_inputs(
                pol.hybrid_config(production_hybrid_config()),
                rerank_output=pol.rerank_output(RERANK_OUTPUT),
                glossary_version=pol.glossary_version(),
                multi_query=pol.multi_query(),
                doc_focus=pol.doc_focus(),
                source_constraint=pol.source_constraint(),
                query_translation=pol.query_translation(),
            )
        )
        if pol.retrieval_overridden()
        else PRODUCTION_RETRIEVAL_VERSION
    )
    return RequestPolicies(
        policies=pol,
        versions=VersionSet(
            policy_version=routed.policy_version(POLICY_VERSION),
            retrieval_version=retrieval_version,
            skill_version_set=skill_version_set,
            model_config_version=production_model_config_version() + pol.model_config_suffix(),
        ),
        canary_ids=routed.canary_ids,
    )


@dataclass
class PolicyRouter:
    """Process-local bounded release cache; routing is always per authenticated principal."""

    settings: Settings
    skill_version_set: tuple[str, ...]
    _state: tuple[float, ReleaseState] | None = field(default=None, repr=False)
    _lock: Any = field(default_factory=threading.Lock, repr=False)

    def state(self, conn: Any) -> ReleaseState:
        with self._lock:
            now = time.monotonic()
            if self._state and now - self._state[0] < float(self.settings.policy_reload_ttl_s):
                return self._state[1]
            state = load_release_state(conn)
            self._state = (time.monotonic(), state)
            return state

    def route(self, conn: Any, user: UserContext) -> RequestPolicies:
        return request_policies(self.state(conn).for_principal(user.user_id), self.skill_version_set)
