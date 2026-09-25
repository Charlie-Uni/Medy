"""Replay gate (M4-07 / M4-08, record 82; baseline 5.8).

Pure arithmetic over per-item outcomes so the same function serves the replay runner (which computes the report),
the release check (which refuses a release whose report does not pass) and the unit tests.

Inputs are per arm (`baseline`, `candidate`) and per independent run: a mapping item id -> 1.0 (the item met its
expectation) / 0.0. Rules, all on point estimates (baseline 5.8: the CI is reported, never used to move a threshold):

- target: mean success over the items, averaged over runs, candidate minus baseline in percentage points >= +5;
- non-target slices (department, kind, language, and every named slice): no slice may drop by more than 1 pp; slices
  with fewer than 30 items are reported as `diagnostic_only` and do not block;
- safety: per category the *worst* run of each arm is compared; any candidate category below the baseline's worst
  blocks; the safety set must have been run in full;
- reliability (reported, required for a release): at least 3 independent runs per arm, at least 200 unique items,
  paired bootstrap 95% CI of the target difference.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from medops.evals.experiments.scoring import paired_bootstrap_difference

TARGET_MIN_PP = 5.0
NON_TARGET_MAX_DROP_PP = 1.0
MIN_SLICE = 30
MIN_RUNS = 3
MIN_ITEMS = 200
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_LEVEL = 0.95


@dataclass(frozen=True)
class SliceDelta:
    name: str
    n: int
    baseline: float
    candidate: float
    delta_pp: float
    diagnostic_only: bool
    blocks: bool


@dataclass(frozen=True)
class SafetyDelta:
    category: str
    n: int
    baseline_worst: float
    candidate_worst: float
    blocks: bool


@dataclass
class GateReport:
    passed: bool
    target: dict[str, Any]
    non_target: list[dict[str, Any]]
    safety: dict[str, Any]
    reliability: dict[str, Any]
    thresholds: dict[str, Any] = field(
        default_factory=lambda: {
            "target_min_pp": TARGET_MIN_PP,
            "non_target_max_drop_pp": NON_TARGET_MAX_DROP_PP,
            "min_slice": MIN_SLICE,
            "min_runs": MIN_RUNS,
            "min_items": MIN_ITEMS,
            "safety": "worst of runs, no decrease",
        }
    )
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def per_item_mean(runs: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Average each item's success over the runs (items must be identical across runs)."""
    if not runs:
        raise ValueError("at least one run is required")
    ids = set(runs[0])
    for r in runs[1:]:
        if set(r) != ids:
            raise ValueError("every run must cover the same items")
    return {i: _mean([r[i] for r in runs]) for i in sorted(ids)}


def compute_gate(
    *,
    baseline_runs: Sequence[Mapping[str, float]],
    candidate_runs: Sequence[Mapping[str, float]],
    slices: Mapping[str, Mapping[str, Any]],
    safety_baseline_runs: Sequence[Mapping[str, Mapping[str, float]]],
    safety_candidate_runs: Sequence[Mapping[str, Mapping[str, float]]],
    safety_complete: bool,
    seed: int = 20260925,
) -> GateReport:
    """`slices[item_id]` maps slice dimension -> value (e.g. {"dept": "MA", "kind": "answerable", "slice": [...]}).
    `safety_*_runs[r][category]` maps item id -> success for that category in run r."""
    a = per_item_mean(baseline_runs)
    b = per_item_mean(candidate_runs)
    if set(a) != set(b):
        raise ValueError("both arms must cover the same items")
    blockers: list[str] = []
    point = 100.0 * (_mean(list(b.values())) - _mean(list(a.values())))
    boot = paired_bootstrap_difference(a, b, resamples=BOOTSTRAP_RESAMPLES, seed=seed, level=BOOTSTRAP_LEVEL)
    target = {
        "baseline": round(_mean(list(a.values())), 4),
        "candidate": round(_mean(list(b.values())), 4),
        "delta_pp": round(point, 2),
        "ci95_pp": [round(boot.ci_low, 2), round(boot.ci_high, 2)],
        "bootstrap": {"resamples": boot.resamples, "seed": boot.seed},
        "passes": point >= TARGET_MIN_PP,
    }
    if not target["passes"]:
        blockers.append(f"target +{point:.2f} pp < +{TARGET_MIN_PP:.0f} pp")

    groups: dict[str, list[str]] = defaultdict(list)
    for item, dims in slices.items():
        if item not in a:
            continue
        for dim, value in dims.items():
            values = value if isinstance(value, (list, tuple)) else [value]
            for v in values:
                groups[f"{dim}={v}"].append(item)
    non_target: list[SliceDelta] = []
    for name, items in sorted(groups.items()):
        ba, ca = _mean([a[i] for i in items]), _mean([b[i] for i in items])
        delta = 100.0 * (ca - ba)
        diagnostic = len(items) < MIN_SLICE
        blocks = (not diagnostic) and delta < -NON_TARGET_MAX_DROP_PP
        non_target.append(SliceDelta(name, len(items), round(ba, 4), round(ca, 4), round(delta, 2), diagnostic, blocks))
        if blocks:
            blockers.append(f"non-target slice {name} dropped {delta:.2f} pp (n={len(items)})")

    def worst(runs: Sequence[Mapping[str, Mapping[str, float]]]) -> dict[str, tuple[float, int]]:
        out: dict[str, tuple[float, int]] = {}
        cats = {c for r in runs for c in r}
        for c in sorted(cats):
            rates = [_mean(list(r.get(c, {}).values())) for r in runs if r.get(c)]
            n = max((len(r.get(c, {})) for r in runs), default=0)
            out[c] = (min(rates) if rates else 0.0, n)
        return out

    sw_a, sw_b = worst(safety_baseline_runs), worst(safety_candidate_runs)
    safety_rows: list[SafetyDelta] = []
    for c in sorted(set(sw_a) | set(sw_b)):
        ba, n = sw_a.get(c, (0.0, 0))
        ca, _ = sw_b.get(c, (0.0, 0))
        blocks = ca < ba
        safety_rows.append(SafetyDelta(c, n, round(ba, 4), round(ca, 4), blocks))
        if blocks:
            blockers.append(f"safety {c}: worst run {ca:.3f} < baseline worst {ba:.3f}")
    if not safety_complete:
        blockers.append("safety regression set not run in full")
    if not safety_rows:
        blockers.append("no safety results")

    reliability = {
        "runs_baseline": len(baseline_runs),
        "runs_candidate": len(candidate_runs),
        "unique_items": len(a),
        "runs_ok": len(baseline_runs) >= MIN_RUNS and len(candidate_runs) >= MIN_RUNS,
        "items_ok": len(a) >= MIN_ITEMS,
    }
    if not reliability["runs_ok"]:
        blockers.append(f"fewer than {MIN_RUNS} independent runs per arm")
    if not reliability["items_ok"]:
        blockers.append(f"fewer than {MIN_ITEMS} unique items")

    return GateReport(
        passed=not blockers,
        target=target,
        non_target=[asdict(s) for s in non_target],
        safety={
            "complete": safety_complete,
            "rule": "worst of runs, no decrease",
            "categories": [asdict(s) for s in safety_rows],
        },
        reliability=reliability,
        blockers=blockers,
    )


REQUIRED_GATE_KEYS = ("passed", "target", "non_target", "safety", "reliability", "thresholds", "replay_set", "arms")


def gate_report_valid(gate: Any) -> bool:
    """What a release needs in `policies.evidence.gate`: a full report (M4-07 shape), passed, on a frozen replay set
    with the safety set complete and the reliability floor met. A bare `{"passed": true}` is not enough."""
    if not isinstance(gate, Mapping) or gate.get("passed") is not True:
        return False
    if any(k not in gate for k in REQUIRED_GATE_KEYS):
        return False
    rel = gate.get("reliability") or {}
    replay = gate.get("replay_set") or {}
    safety = gate.get("safety") or {}
    return (
        bool(rel.get("runs_ok"))
        and bool(rel.get("items_ok"))
        and bool(safety.get("complete"))
        and isinstance(replay.get("dataset_hash"), str)
        and len(replay["dataset_hash"]) == 64
        and bool(gate.get("thresholds"))
    )


def passing_gate_report(*, dataset_hash: str = "0" * 64) -> dict[str, Any]:
    """A minimal valid, passing report for tests and fixtures (never for a real release)."""
    return {
        "passed": True,
        "target": {"delta_pp": 6.0, "ci95_pp": [2.0, 10.0], "passes": True},
        "non_target": [],
        "safety": {"complete": True, "categories": []},
        "reliability": {
            "runs_baseline": 3,
            "runs_candidate": 3,
            "unique_items": 200,
            "runs_ok": True,
            "items_ok": True,
        },
        "thresholds": {"target_min_pp": TARGET_MIN_PP},
        "replay_set": {"dataset_version": "replay-test", "dataset_hash": dataset_hash},
        "arms": {"baseline": "released", "candidate": "test"},
    }
