"""Canary routing (M4-09): a stable per-principal split across released targets, `+rel:` / `+canary:` in the policy
version, the previous policy (or the constants) for the rest of the traffic, and the drill mode of the release gate."""

from __future__ import annotations

from collections import Counter

from medops.application.policy_loader import (
    ReleasedPolicy,
    ReleaseState,
    ReleaseTarget,
    RoutedPolicies,
)
from medops.loop.gate import gate_report_valid, passing_gate_report
from medops.retrieval.hybrid import HybridConfig

NEW = ReleasedPolicy(
    "aaaaaaaa-0000-0000-0000-000000000001", "retrieval_params", "hybrid", "hybrid@v2", {"rrf_k": {"from": 60, "to": 40}}
)
OLD = ReleasedPolicy(
    "bbbbbbbb-0000-0000-0000-000000000002", "retrieval_params", "hybrid", "hybrid@v1", {"rrf_k": {"from": 60, "to": 50}}
)
PROMPT = ReleasedPolicy(
    "cccccccc-0000-0000-0000-000000000003", "prompt", "answer_system", "p@v1", {"text": "只依据证据作答。"}
)


def test_full_release_reaches_everyone_and_names_itself_rel():
    state = ReleaseState((ReleaseTarget("retrieval_params", "hybrid", NEW, 100, OLD, None),))
    routed = state.for_principal("user-1")
    assert routed.policies.policies == (NEW,) and routed.canary_ids == ()
    assert routed.policy_version("base") == "base+rel:aaaaaaaa"
    assert routed.policies.hybrid_config(HybridConfig()).rrf_k == 40.0


def test_canary_split_is_stable_per_principal_and_near_the_percentage():
    state = ReleaseState((ReleaseTarget("retrieval_params", "hybrid", NEW, 10, OLD, None),))
    principals = [f"user-{i}" for i in range(2000)]
    sides = Counter("new" if state.for_principal(p).canary_ids else "old" for p in principals)
    assert 150 <= sides["new"] <= 250  # ~10% of 2000, hash-stable
    for p in principals[:50]:
        assert state.for_principal(p) == state.for_principal(p)  # same principal, same side, every time
    on_new = next(p for p in principals if state.for_principal(p).canary_ids)
    on_old = next(p for p in principals if not state.for_principal(p).canary_ids)
    assert state.for_principal(on_new).policy_version("b") == "b+canary:aaaaaaaa"
    old_side = state.for_principal(on_old)
    assert old_side.policies.policies == (OLD,) and old_side.policy_version("b") == "b+rel:bbbbbbbb"


def test_first_release_without_a_previous_policy_falls_back_to_the_constants():
    state = ReleaseState((ReleaseTarget("retrieval_params", "hybrid", NEW, 10, None, None),))
    off = next(p for p in (f"u{i}" for i in range(500)) if not state.for_principal(p).canary_ids)
    routed = state.for_principal(off)
    assert routed.policies.policies == () and routed.policy_version("b") == "b"
    assert routed.policies.hybrid_config(HybridConfig()) == HybridConfig()


def test_targets_split_independently_and_versions_list_both_kinds():
    state = ReleaseState(
        (
            ReleaseTarget("prompt", "answer_system", PROMPT, 100, None, None),
            ReleaseTarget("retrieval_params", "hybrid", NEW, 50, OLD, None),
        )
    )
    versions = {state.for_principal(f"p{i}").policy_version("b") for i in range(200)}
    assert versions == {"b+rel:cccccccc+canary:aaaaaaaa", "b+rel:bbbbbbbb,cccccccc"}
    assert RoutedPolicies(state.all_current()).policy_version("b") == "b+rel:aaaaaaaa,cccccccc"


def test_drill_reports_are_accepted_only_when_the_service_allows_them():
    drill = {"passed": True, "drill": True, "replay_set": {"dataset_hash": "d" * 64}, "arms": {"note": "release drill"}}
    assert not gate_report_valid(drill)
    assert gate_report_valid(drill, allow_drill=True)
    assert not gate_report_valid({**drill, "passed": False}, allow_drill=True)
    assert not gate_report_valid({"passed": True, "drill": True}, allow_drill=True)  # no replay set, no arms
    assert gate_report_valid(passing_gate_report(), allow_drill=True)  # a real report is always fine
