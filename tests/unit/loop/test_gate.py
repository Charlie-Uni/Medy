"""Replay gate (M4-08): +5 pp target on point estimates, no non-target slice down more than 1 pp (slices under 30 are
diagnostic only), safety judged on the worst run and never below baseline, reliability floor reported and required,
and the release check accepts only a full passing report."""

from __future__ import annotations

import pytest

from medops.loop.gate import compute_gate, gate_report_valid, passing_gate_report, per_item_mean

N = 200
ITEMS = [f"i{i:03d}" for i in range(N)]
SLICES = {
    i: {"dept": "MA" if k % 2 else "PV", "kind": "answerable" if k < 180 else "no_answer"} for k, i in enumerate(ITEMS)
}


def runs(success_ids: set[str], *, count: int = 3) -> list[dict[str, float]]:
    return [{i: 1.0 if i in success_ids else 0.0 for i in ITEMS} for _ in range(count)]


def safety(
    rate: float, *, count: int = 3, category: str = "high_risk", n: int = 30
) -> list[dict[str, dict[str, float]]]:
    ids = [f"s{i}" for i in range(n)]
    good = set(ids[: int(round(rate * n))])
    return [{category: {i: 1.0 if i in good else 0.0 for i in ids}} for _ in range(count)]


def test_per_item_mean_requires_identical_items():
    assert per_item_mean([{"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 0.0}]) == {"a": 0.5, "b": 0.0}
    with pytest.raises(ValueError):
        per_item_mean([{"a": 1.0}, {"b": 1.0}])


def test_passes_with_six_points_and_flat_slices():
    base = set(ITEMS[:140])  # 70%
    cand = set(ITEMS[:152])  # 76%: +6 pp, spread across both departments
    report = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(cand),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
    )
    assert report.passed and report.blockers == [] and report.target["delta_pp"] == 6.0
    lo, hi = report.target["ci95_pp"]
    assert lo <= 6.0 <= hi and report.reliability == {
        "runs_baseline": 3,
        "runs_candidate": 3,
        "unique_items": 200,
        "runs_ok": True,
        "items_ok": True,
    }
    assert gate_report_valid({**report.as_dict(), "replay_set": {"dataset_hash": "a" * 64}, "arms": {}})


def test_four_points_fail_the_target_threshold_and_the_ci_is_reported_not_used():
    report = compute_gate(
        baseline_runs=runs(set(ITEMS[:140])),
        candidate_runs=runs(set(ITEMS[:148])),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
    )
    assert not report.passed and report.target["delta_pp"] == 4.0 and any("target" in b for b in report.blockers)


def test_a_non_target_slice_dropping_more_than_one_point_blocks_but_small_slices_are_diagnostic():
    base = set(ITEMS[:140])
    # candidate: +26 on PV items but loses 3 MA items (MA has 100 items: -3 pp) -> blocked
    cand = (base | set(i for i in ITEMS[140:] if SLICES[i]["dept"] == "PV")) - set(
        i for i in ITEMS[:6] if SLICES[i]["dept"] == "MA"
    )
    report = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(cand),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
    )
    assert report.target["passes"] and not report.passed
    ma = next(s for s in report.non_target if s["name"] == "dept=MA")
    assert ma["blocks"] and ma["delta_pp"] == -3.0 and not ma["diagnostic_only"]
    small = next(s for s in report.non_target if s["name"] == "kind=no_answer")
    assert small["n"] == 20 and small["diagnostic_only"] and not small["blocks"]


def test_safety_is_judged_on_the_worst_run_and_may_not_decrease():
    base = set(ITEMS[:140])
    cand = set(ITEMS[:160])
    worse_once = safety(0.97)[:2] + safety(0.93)[:1]  # one bad run out of three
    report = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(cand),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=worse_once,
        safety_complete=True,
    )
    cat = report.safety["categories"][0]
    assert cat["candidate_worst"] < cat["baseline_worst"] and cat["blocks"] and not report.passed
    incomplete = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(cand),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=False,
    )
    assert not incomplete.passed and "not run in full" in " ".join(incomplete.blockers)


def test_reliability_floor_is_required():
    report = compute_gate(
        baseline_runs=runs(set(ITEMS[:140]), count=2),
        candidate_runs=runs(set(ITEMS[:160]), count=2),
        slices=SLICES,
        safety_baseline_runs=safety(0.97, count=2),
        safety_candidate_runs=safety(0.97, count=2),
        safety_complete=True,
    )
    assert not report.passed and not report.reliability["runs_ok"]


def test_release_check_needs_a_full_report():
    assert gate_report_valid(passing_gate_report(dataset_hash="b" * 64))
    assert not gate_report_valid({"passed": True})
    assert not gate_report_valid({**passing_gate_report(), "passed": False})
    broken = passing_gate_report()
    broken["reliability"]["runs_ok"] = False
    assert not gate_report_valid(broken)
    assert not gate_report_valid({**passing_gate_report(), "replay_set": {"dataset_hash": "short"}})


def tokens(per_item: float, *, count: int = 3) -> list[dict[str, float]]:
    return [{i: per_item for i in ITEMS} for _ in range(count)]


def test_cost_profile_needs_a_quarter_fewer_tokens_and_quality_within_one_point():
    base = set(ITEMS[:140])
    cand = set(ITEMS[:139])  # −0.5 pp: inside the tolerance the slices already get
    report = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(cand),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
        profile="cost",
        baseline_tokens=tokens(3200.0),
        candidate_tokens=tokens(2200.0),  # −31%
    )
    assert report.passed and report.blockers == []
    assert report.target["profile"] == "cost" and report.target["token_reduction"] == 0.3125
    assert report.target["quality_ok"] and report.target["tokens_ok"] and report.target["passes"]
    assert report.thresholds["profile"] == "cost" and report.thresholds["token_reduction_min"] == 0.25
    assert "target_min_pp" not in report.thresholds
    assert gate_report_valid({**report.as_dict(), "replay_set": {"dataset_hash": "a" * 64}, "arms": {}})


def test_cost_profile_blocks_small_savings_or_a_quality_drop():
    base = set(ITEMS[:140])
    common = dict(
        slices=SLICES, safety_baseline_runs=safety(0.97), safety_candidate_runs=safety(0.97), safety_complete=True
    )
    small = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(base),
        profile="cost",
        baseline_tokens=tokens(3200.0),
        candidate_tokens=tokens(2900.0),
        **common,
    )
    assert not small.passed and small.blockers == ["token reduction 9.4% < 25%"]
    worse = compute_gate(
        baseline_runs=runs(base),
        candidate_runs=runs(set(ITEMS[:136])),
        profile="cost",
        baseline_tokens=tokens(3200.0),
        candidate_tokens=tokens(1600.0),
        **common,
    )
    assert not worse.passed and any(b.startswith("quality -2.00 pp") for b in worse.blockers)
    with pytest.raises(ValueError, match="token maps"):
        compute_gate(baseline_runs=runs(base), candidate_runs=runs(base), profile="cost", **common)
    with pytest.raises(ValueError, match="unknown gate profile"):
        compute_gate(baseline_runs=runs(base), candidate_runs=runs(base), profile="speed", **common)


def test_quality_profile_report_is_unchanged_in_shape():
    report = compute_gate(
        baseline_runs=runs(set(ITEMS[:140])),
        candidate_runs=runs(set(ITEMS[:152])),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
    )
    assert report.target["profile"] == "quality" and report.thresholds["target_min_pp"] == 5.0
    assert "token_reduction" not in report.target


def test_spend_profile_needs_a_quarter_less_money_and_quality_within_one_point():
    """Record 122: model routing is judged on USD per item — a cheaper model spends the same tokens."""
    base = set(ITEMS[:140])
    usd = lambda v: [{i: v for i in ITEMS} for _ in range(3)]  # noqa: E731
    common = dict(
        baseline_runs=runs(base),
        slices=SLICES,
        safety_baseline_runs=safety(0.97),
        safety_candidate_runs=safety(0.97),
        safety_complete=True,
        profile="spend",
        baseline_spend=usd(0.0110),
    )
    ok = compute_gate(candidate_runs=runs(set(ITEMS[:139])), candidate_spend=usd(0.0044), **common)
    assert ok.passed and ok.target["profile"] == "spend" and ok.target["spend_reduction"] == 0.6
    assert ok.target["usd_baseline"] == 0.011 and ok.thresholds["spend_reduction_min"] == 0.25
    small = compute_gate(candidate_runs=runs(base), candidate_spend=usd(0.0099), **common)  # −10%
    assert not small.passed and any("spend reduction 10.0% < 25%" in b for b in small.blockers)
    worse = compute_gate(candidate_runs=runs(set(ITEMS[:136])), candidate_spend=usd(0.0044), **common)  # −2 pp
    assert not worse.passed and any("quality" in b for b in worse.blockers)
    with pytest.raises(ValueError, match="spend profile needs"):
        compute_gate(candidate_runs=runs(base), **{**common, "baseline_spend": None})
