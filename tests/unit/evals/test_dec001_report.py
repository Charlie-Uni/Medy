from __future__ import annotations

from medops.evals.experiments import dec001_report as rep


def _candidate(macro, slice_recall, *, leaks=0, nonrepro=(), p95=2.0, support=9):
    return {
        "strict_macro_recall": macro,
        "by_slice": [
            {"label": s, "support": support, "recall": slice_recall, "diagnostic_only": support < 8} for s in rep.SLICES
        ],
        "by_department": [],
        "by_gold_script": [],
        "drug_name_zh_by_script": [],
        "leak_violations": [{"sample_id": "x"}] * leaks,
        "not_reproducible_queries": list(nonrepro),
        "latency_ms": {"p95": p95, "mean": 1.0, "max": 3.0, "measured_executions": 10},
        "candidate_exhausted_queries": 0,
        "zero_result_queries": 0,
        "per_query": [],
    }


def test_hard_gates_and_selection_rules_follow_the_adr_thresholds():
    results = {
        "candidates": {
            "A": _candidate(0.92, 0.90),
            "B": _candidate(0.98, 0.95, p95=2.4),
            "C": _candidate(0.99, 0.97, p95=2.0),
        },
        "paired_against_A": {
            "B": {"point": 6.0, "ci_low": 1.0, "ci_high": 11.0},
            "C": {"point": 7.0, "ci_low": 2.0, "ci_high": 12.0},
        },
    }
    ev = rep.evaluate(results)
    assert all(ev["candidates"][c]["passes_hard_gates"] for c in "ABC")
    assert ev["selection"]["B"]["could_replace_A_on_lexical_evidence"] is True
    assert ev["selection"]["C"]["licence_blocks_selection"] is True
    assert ev["selection"]["C"]["could_replace_A_on_lexical_evidence"] is False
    assert "complexity baseline" in ev["lexical_conclusion"]


def test_failing_macro_slice_leak_or_reproducibility_fails_the_hard_gates():
    base = {"paired_against_A": {}}
    assert (
        rep.evaluate({**base, "candidates": {"A": _candidate(0.89, 0.95)}})["candidates"]["A"]["passes_hard_gates"]
        is False
    )
    assert (
        rep.evaluate({**base, "candidates": {"A": _candidate(0.95, 0.84)}})["candidates"]["A"]["passes_hard_gates"]
        is False
    )
    assert (
        rep.evaluate({**base, "candidates": {"A": _candidate(0.95, 0.95, leaks=1)}})["candidates"]["A"][
            "passes_hard_gates"
        ]
        is False
    )
    assert (
        rep.evaluate({**base, "candidates": {"A": _candidate(0.95, 0.95, nonrepro=("pc-0001",))}})["candidates"]["A"][
            "passes_hard_gates"
        ]
        is False
    )
    low = rep.evaluate({**base, "candidates": {"A": _candidate(0.95, 0.95, support=7)}})
    assert (
        low["candidates"]["A"]["passes_hard_gates"] is False
        and "support below 8" in low["candidates"]["A"]["slices"]["negation"]["note"]
    )
    assert "stay blocked" in low["lexical_conclusion"]


def test_replacement_needs_gain_ci_and_latency():
    results = {
        "candidates": {"A": _candidate(0.92, 0.90, p95=2.0), "B": _candidate(0.95, 0.92, p95=2.6)},
        "paired_against_A": {"B": {"point": 4.0, "ci_low": -1.0, "ci_high": 9.0}},
    }
    sel = rep.evaluate(results)["selection"]["B"]
    assert sel["gain_criterion_met"] is False and sel["lexical_p95_within_125pct_of_A"] is False
    assert sel["could_replace_A_on_lexical_evidence"] is False
    assert "end_to_end_recall_at_5_drop_le_1pp" in sel["not_evaluated_here"]


def test_gates_use_the_language_matched_scope_when_scopes_are_recorded():
    def scoped(macro_all, macro_matched, slice_matched):
        c = _candidate(macro_all, 0.5)
        c["scopes"] = {
            "language_matched": {
                "queries": 40,
                "strict_macro_recall": macro_matched,
                "by_slice": [
                    {"label": s, "support": 9, "recall": slice_matched, "diagnostic_only": False} for s in rep.SLICES
                ],
                "by_department": [],
                "by_gold_script": [],
                "sample_ids": [],
            },
            "cross_lingual": {
                "queries": 32,
                "strict_macro_recall": 0.1,
                "by_slice": [],
                "by_department": [],
                "by_gold_script": [],
                "sample_ids": [],
            },
            "provisional_twins": {
                "queries": 0,
                "strict_macro_recall": None,
                "by_slice": [],
                "by_department": [],
                "by_gold_script": [],
                "sample_ids": [],
            },
            "language_matched_plus_provisional_twins": {
                "queries": 40,
                "strict_macro_recall": macro_matched,
                "by_slice": [],
                "by_department": [],
                "by_gold_script": [],
                "sample_ids": [],
            },
        }
        return c

    results = {"candidates": {"A": scoped(0.6, 0.95, 0.9)}, "paired_against_A": {}}
    ev = rep.evaluate(results)
    assert ev["gate_scope"] == "language_matched"
    assert ev["candidates"]["A"]["macro"] == 0.95 and ev["candidates"]["A"]["gate_queries"] == 40
    assert ev["candidates"]["A"]["passes_hard_gates"] is True
    # run-1 format (no scopes) still evaluates on the whole set
    legacy = rep.evaluate({"candidates": {"A": _candidate(0.6, 0.9)}, "paired_against_A": {}})
    assert legacy["gate_scope"] == "all_samples" and legacy["candidates"]["A"]["passes_hard_gates"] is False
