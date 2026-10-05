"""Released policies as production reads them (M4-03, record 80; INV-HAR-06).

Production never reads the repository's latest prompt or parameters as *the* policy: at process start the runtime
loads the `released_policies` pointers (switched atomically by release / rollback, record 75) and applies the
structured diffs it knows how to apply. The repository constants are the bootstrap ("released v0") and stay in force
for every target without a released pointer. Whatever is applied shows up in the trace versions: `policy_version`
gains the released policy ids, a prompt override changes `model_config_version`, a retrieval override changes the
composite `retrieval_version` (baseline 3.6: only the composite enters cache keys).

Targets this build can apply (a release of anything else is refused with `policy_target_unsupported`):

| kind             | name            | diff                                                                  |
| ---------------- | --------------- | --------------------------------------------------------------------- |
| retrieval_params | hybrid          | `{k_lexical|k_vector|rrf_k|limit|rerank_output: {"from": x, "to": y}}` plus the
|                  |                 | rewrite-side keys `glossary` (version), `multi_query` / `doc_focus` (bool),      |
|                  |                 | `query_translation` (`off` or an allowed model id) — records 93–95              |
|                  |                 | and the answer-context key `evidence_focus` (`off`, `compact-v1`,                |
|                  |                 | `sentfocus-v1`) — record 113                                                     |
| prompt           | answer_system   | `{"text": "...", "text_sha256": "..."}` — the answer node's system prompt |
| model_route      | answer          | `{"<intent>": {"from": "<model>", "to": "<model>"}}` — the answer model per      |
|                  |                 | intent type (record 122); the judge model is never routed                        |
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from medops.domain.state import MAX_EVIDENCE, VersionSet
from medops.harness.evidence_focus import ALLOWED_EVIDENCE_FOCUS, EVIDENCE_FOCUS_OFF
from medops.harness.production import ALLOWED_ANSWER_MODELS, ROUTABLE_INTENTS
from medops.retrieval.glossary_store import valid_glossary_version
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.query_translation import ALLOWED_TRANSLATION_MODELS, QUERY_TRANSLATION_OFF
from medops.retrieval.rewrite import GLOSSARY_NONE

SUPPORTED_RELEASE_TARGETS: frozenset[tuple[str, str]] = frozenset(
    {("retrieval_params", "hybrid"), ("prompt", "answer_system"), ("model_route", "answer")}
)
RETRIEVAL_PARAM_KEYS = (
    "k_lexical",
    "k_vector",
    "rrf_k",
    "limit",
    "rerank_output",
    "glossary",
    "multi_query",
    "doc_focus",
    "query_translation",
    "evidence_focus",
)


class PolicyDiffError(ValueError):
    """A released or proposed diff that this build cannot apply."""


@dataclass(frozen=True)
class ReleasedPolicy:
    policy_id: str
    kind: str
    name: str
    version: str
    diff: Mapping[str, Any]


@dataclass(frozen=True)
class ReleasedPolicySet:
    policies: tuple[ReleasedPolicy, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls) -> ReleasedPolicySet:
        return cls(())

    def get(self, kind: str, name: str) -> ReleasedPolicy | None:
        for p in self.policies:
            if p.kind == kind and p.name == name:
                return p
        return None

    # -- retrieval
    def hybrid_config(self, base: HybridConfig) -> HybridConfig:
        p = self.get("retrieval_params", "hybrid")
        return apply_retrieval_diff(base, p.diff) if p else base

    def rerank_output(self, base: int) -> int:
        p = self.get("retrieval_params", "hybrid")
        if p is None or "rerank_output" not in p.diff:
            return base
        value = int(_to(p.diff["rerank_output"]))
        if not 1 <= value <= MAX_EVIDENCE:
            raise PolicyDiffError(f"rerank_output must be within 1..{MAX_EVIDENCE}")
        return value

    def glossary_version(self, base: str = GLOSSARY_NONE) -> str:
        """The released glossary version (record 93); `glossary-none` means the rewriter runs without a glossary."""
        p = self.get("retrieval_params", "hybrid")
        if p is None or "glossary" not in p.diff:
            return base
        value = str(_to(p.diff["glossary"]))
        if not valid_glossary_version(value):
            raise PolicyDiffError("glossary must be 'glossary-none' or 'glossary-<YYYYMMDD>-<sha12>'")
        return value

    def multi_query(self, base: bool = False) -> bool:
        """Whether every rewritten query is searched and fused (record 93); the repository default is off."""
        p = self.get("retrieval_params", "hybrid")
        if p is None or "multi_query" not in p.diff:
            return base
        value = _to(p.diff["multi_query"])
        if not isinstance(value, bool):
            raise PolicyDiffError("multi_query must be true or false")
        return value

    def doc_focus(self, base: bool = False) -> bool:
        """Whether a named corpus document is searched on its own and fused (record 94); default off."""
        p = self.get("retrieval_params", "hybrid")
        if p is None or "doc_focus" not in p.diff:
            return base
        value = _to(p.diff["doc_focus"])
        if not isinstance(value, bool):
            raise PolicyDiffError("doc_focus must be true or false")
        return value

    def query_translation(self, base: str = QUERY_TRANSLATION_OFF) -> str:
        """`off` or the model id that renders Chinese questions into English for retrieval (record 95)."""
        p = self.get("retrieval_params", "hybrid")
        if p is None or "query_translation" not in p.diff:
            return base
        value = str(_to(p.diff["query_translation"]))
        if value != QUERY_TRANSLATION_OFF and value not in ALLOWED_TRANSLATION_MODELS:
            raise PolicyDiffError(f"query_translation must be 'off' or one of {sorted(ALLOWED_TRANSLATION_MODELS)}")
        return value

    def evidence_focus(self, base: str = EVIDENCE_FOCUS_OFF) -> str:
        """How evidence is laid out in the answer prompt (record 113): `off`, `compact-v1` or `sentfocus-v1`.
        It changes what the model reads, not what is retrieved, so it enters the model configuration version."""
        p = self.get("retrieval_params", "hybrid")
        if p is None or "evidence_focus" not in p.diff:
            return base
        value = str(_to(p.diff["evidence_focus"]))
        if value not in ALLOWED_EVIDENCE_FOCUS:
            raise PolicyDiffError(f"evidence_focus must be one of {sorted(ALLOWED_EVIDENCE_FOCUS)}")
        return value

    def retrieval_overridden(self) -> bool:
        return self.get("retrieval_params", "hybrid") is not None

    # -- prompt
    def answer_system(self, base: str) -> str:
        p = self.get("prompt", "answer_system")
        if p is None:
            return base
        text = p.diff.get("text")
        if not isinstance(text, str) or not text.strip():
            raise PolicyDiffError("prompt/answer_system diff needs a non-empty `text`")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if p.diff.get("text_sha256") not in (None, digest):
            raise PolicyDiffError("prompt/answer_system text does not match its recorded sha256")
        return text

    # -- model route
    def answer_models(self) -> dict[str, str]:
        """intent type -> answer model, for the intents a released `model_route/answer` policy names (record 122).
        An intent it does not name keeps the pinned production answer model."""
        p = self.get("model_route", "answer")
        if p is None:
            return {}
        routes: dict[str, str] = {}
        for intent, entry in p.diff.items():
            if intent not in ROUTABLE_INTENTS:
                raise PolicyDiffError(f"model_route/answer: {intent!r} is not a routable intent")
            model = str(_to(entry))
            if model not in ALLOWED_ANSWER_MODELS:
                raise PolicyDiffError(f"model_route/answer: model must be one of {sorted(ALLOWED_ANSWER_MODELS)}")
            routes[intent] = model
        return routes

    # -- versions
    def policy_version(self, base: str) -> str:
        if not self.policies:
            return base
        return base + "+rel:" + ",".join(sorted(p.policy_id.replace("-", "")[:8] for p in self.policies))

    def model_config_suffix(self) -> str:
        suffix = ""
        p = self.get("prompt", "answer_system")
        if p is not None:
            text = str(p.diff.get("text", ""))
            suffix += ";prompt=" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        qt = self.query_translation()
        if qt != QUERY_TRANSLATION_OFF:
            suffix += f";qt={qt}"  # a translation model is part of the model configuration (record 95)
        focus = self.evidence_focus()
        if focus != EVIDENCE_FOCUS_OFF:
            suffix += f";ctx={focus}"  # the prompt layout is part of the model configuration (record 113)
        routes = self.answer_models()
        if routes:  # which model answers which intent is the model configuration itself (record 122)
            suffix += ";route=" + ",".join(f"{intent}:{model}" for intent, model in sorted(routes.items()))
        return suffix


def _to(entry: Any) -> Any:
    if isinstance(entry, Mapping) and "to" in entry:
        return entry["to"]
    raise PolicyDiffError("each retrieval parameter entry is {'from': x, 'to': y}")


def apply_retrieval_diff(base: HybridConfig, diff: Mapping[str, Any]) -> HybridConfig:
    unknown = set(diff) - set(RETRIEVAL_PARAM_KEYS)
    if unknown:
        raise PolicyDiffError(f"unknown retrieval parameters: {sorted(unknown)}")
    k_lexical = int(_to(diff["k_lexical"])) if "k_lexical" in diff else base.k_lexical
    k_vector = int(_to(diff["k_vector"])) if "k_vector" in diff else base.k_vector
    limit = int(_to(diff["limit"])) if "limit" in diff else base.limit
    rrf_k = float(_to(diff["rrf_k"])) if "rrf_k" in diff else base.rrf_k
    try:  # HybridConfig enforces the baseline caps (channel k and limit within 1..20)
        return HybridConfig(k_lexical=k_lexical, k_vector=k_vector, rrf_k=rrf_k, limit=limit)
    except ValueError as exc:
        raise PolicyDiffError(str(exc)) from exc


def validate_diff(kind: str, name: str, diff: Mapping[str, Any], *, base: HybridConfig | None = None) -> None:
    """Shape check shared by Adapt (before a candidate is written) and the loader (before a release is applied)."""
    if (kind, name) == ("retrieval_params", "hybrid"):
        cfg = apply_retrieval_diff(base or HybridConfig(), diff)
        probe = ReleasedPolicySet((ReleasedPolicy("x", kind, name, "v", diff),))
        if "rerank_output" in diff:
            probe.rerank_output(MAX_EVIDENCE)
        if "glossary" in diff:
            probe.glossary_version()
        if "multi_query" in diff:
            probe.multi_query()
        if "doc_focus" in diff:
            probe.doc_focus()
        if "query_translation" in diff:
            probe.query_translation()
        if "evidence_focus" in diff:
            probe.evidence_focus()
        extras = {"rerank_output", "glossary", "multi_query", "doc_focus", "query_translation", "evidence_focus"}
        if cfg == (base or HybridConfig()) and not (extras & set(diff)):
            raise PolicyDiffError("the diff changes nothing")
        return
    if (kind, name) == ("model_route", "answer"):
        routes = ReleasedPolicySet((ReleasedPolicy("x", kind, name, "v", diff),)).answer_models()
        if not routes:
            raise PolicyDiffError("model_route/answer needs at least one intent")
        if all(isinstance(e, Mapping) and e.get("from") == e.get("to") for e in diff.values()):
            raise PolicyDiffError("the diff changes nothing")
        return
    if (kind, name) == ("prompt", "answer_system"):
        ReleasedPolicySet((ReleasedPolicy("x", kind, name, "v", diff),)).answer_system("")
        if len(str(diff.get("text"))) > 6000:
            raise PolicyDiffError("prompt text longer than 6000 characters")
        return
    if kind == "rule":
        add = diff.get("add")
        if (
            not isinstance(add, list)
            or not add
            or len(add) > 20
            or not all(isinstance(x, str) and 0 < len(x) <= 300 for x in add)
        ):
            raise PolicyDiffError(
                "rule diffs are additive: {'add': [pattern, ...]} (1..20 patterns, each <= 300 chars)"
            )
        import re

        for pattern in add:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise PolicyDiffError(f"pattern does not compile: {exc}") from exc
        return
    if kind == "skill":
        if not isinstance(diff.get("params"), Mapping) or not diff["params"]:
            raise PolicyDiffError("skill diffs carry {'params': {...}}")
        return
    raise PolicyDiffError(f"unknown policy target {kind}/{name}")


def check_restates_release(current: ReleasedPolicySet, kind: str, name: str, diff: Mapping[str, Any]) -> None:
    """One policy per target: the released policy's diff is applied to the repository constants, so a new candidate
    for the same target REPLACES the released diff instead of adding to it. A candidate that omits a released key
    would silently revert it (2026-10-01: a rerank-only candidate was evaluated without the released retrieval
    bundle, record 107). Every released key must therefore be restated — `from == to` keeps a value — and each
    `from` must be the value in force."""
    released = current.get(kind, name)
    if released is None:
        return
    missing = sorted(k for k in released.diff if k not in diff)
    if missing:
        raise PolicyDiffError(
            f"candidate would silently revert released keys {missing}: restate them (from == to keeps the value)"
        )
    for key, entry in diff.items():
        if key not in released.diff or not isinstance(entry, Mapping) or "from" not in entry:
            continue
        in_force = _to(released.diff[key])
        if entry["from"] != in_force:
            raise PolicyDiffError(f"{key}: `from` {entry['from']!r} is not the released value {in_force!r}")


def load_released(conn: Any) -> ReleasedPolicySet:
    rows = conn.execute(
        "select p.policy_id::text, p.kind, p.name, p.version, p.diff from released_policies r "
        "join policies p on p.policy_id = r.policy_id order by p.kind, p.name"
    ).fetchall()
    policies = tuple(
        ReleasedPolicy(policy_id=r[0], kind=r[1], name=r[2], version=r[3], diff=dict(r[4] or {})) for r in rows
    )
    for p in policies:
        if (p.kind, p.name) in SUPPORTED_RELEASE_TARGETS:
            validate_diff(p.kind, p.name, p.diff)
    return ReleasedPolicySet(policies)


# ------------------------------------------------------------------------------------------ canary routing (M4-09)


@dataclass(frozen=True)
class ReleaseTarget:
    """One (kind, name) pointer with its canary state: `current` is the released policy, `previous` the policy the
    canary's remaining traffic still uses (None = the repository constants), `canary_percent` the share on `current`."""

    kind: str
    name: str
    current: ReleasedPolicy
    canary_percent: int
    previous: ReleasedPolicy | None
    since: datetime | None


@dataclass(frozen=True)
class ReleaseState:
    targets: tuple[ReleaseTarget, ...] = ()

    def all_current(self) -> ReleasedPolicySet:
        return ReleasedPolicySet(tuple(t.current for t in self.targets))

    def for_principal(self, principal: str) -> RoutedPolicies:
        """Stable split: the same principal always lands on the same side of every canary (sha256 of the principal
        pseudonym and the target, mod 100, below the canary percentage -> the new policy)."""
        chosen: list[ReleasedPolicy] = []
        canary: list[str] = []
        for t in self.targets:
            if t.canary_percent >= 100:
                chosen.append(t.current)
                continue
            bucket = int(hashlib.sha256(f"{principal}|{t.kind}/{t.name}".encode()).hexdigest(), 16) % 100
            if bucket < t.canary_percent:
                chosen.append(t.current)
                canary.append(t.current.policy_id)
            elif t.previous is not None:
                chosen.append(t.previous)
        return RoutedPolicies(ReleasedPolicySet(tuple(chosen)), tuple(canary))


@dataclass(frozen=True)
class RoutedPolicies:
    policies: ReleasedPolicySet
    canary_ids: tuple[str, ...] = ()

    def policy_version(self, base: str) -> str:
        """`base+rel:<ids>` for fully released policies, `+canary:<ids>` for the ones this request got as a canary."""
        full = sorted(
            p.policy_id.replace("-", "")[:8] for p in self.policies.policies if p.policy_id not in self.canary_ids
        )
        canary = sorted(pid.replace("-", "")[:8] for pid in self.canary_ids)
        out = base
        if full:
            out += "+rel:" + ",".join(full)
        if canary:
            out += "+canary:" + ",".join(canary)
        return out


_STATE_SQL = """
select r.kind, r.name, p.policy_id::text, p.version, p.diff,
       coalesce(l.canary_percent, 100), l.previous_policy::text, l.occurred_at,
       prev.version, prev.diff
  from released_policies r
  join policies p on p.policy_id = r.policy_id
  left join lateral (
        select canary_percent, previous_policy, occurred_at from policy_releases
         where policy_id = r.policy_id and action in ('release', 'promote')
         order by occurred_at desc limit 1) l on true
  left join policies prev on prev.policy_id = l.previous_policy
 order by r.kind, r.name
"""


def load_release_state(conn: Any) -> ReleaseState:
    targets = []
    for kind, name, pid, version, diff, percent, prev_id, since, prev_version, prev_diff in conn.execute(
        _STATE_SQL
    ).fetchall():
        current = ReleasedPolicy(pid, kind, name, version, dict(diff or {}))
        if (kind, name) in SUPPORTED_RELEASE_TARGETS:
            validate_diff(kind, name, current.diff)
        previous = ReleasedPolicy(prev_id, kind, name, prev_version, dict(prev_diff or {})) if prev_id else None
        targets.append(ReleaseTarget(kind, name, current, int(percent), previous, since))
    return ReleaseState(tuple(targets))


@dataclass(frozen=True)
class RequestPolicies:
    """What one request runs under: the routed policy set, the version set that names it, and which of the policies
    reached this request as a canary."""

    policies: ReleasedPolicySet
    versions: VersionSet
    canary_ids: tuple[str, ...] = ()
