"""End-to-end harness: summary/gate view over synthetic outcomes (recall on the rechecked top 5, ablations,
invalid-version rate, reproducibility) and the report rendering; no database or model."""

from __future__ import annotations

import json

from medops.evals.experiments import e2e_run as e
from medops.evals.experiments.dec001_run import CROSS_LINGUAL, LANGUAGE_MATCHED, Query

QUERIES = [
    Query("pc-0001", "MA", "q1", ("dose_unit",), ("g1",), "zh-Hant", language="zh"),
    Query("pc-0002", "PV", "q2", ("negation",), ("g2",), "en", language="zh"),  # cross-lingual
    Query("pc-0003", "CO", "q3", ("protocol_id",), ("g3a", "g3b"), "en", language="en"),
]
MAPPING = {"g1": ["c1"], "g2": ["c2"], "g3a": ["c3"], "g3b": []}  # g3b unmappable -> forced miss


def outcome(sid, dept, accepted, fused=None, lex=None, vec=None, passes=2, non_current=0):
    o = e.E2EOutcome(sid, dept)
    o.fused = [list(fused or accepted)] * passes
    o.accepted = [list(accepted)] * passes
    o.lexical_top = list(lex or [])
    o.vector_top = list(vec or [])
    o.dropped = {"status_not_active": 1}
    o.non_current_in_top5 = non_current
    o.latencies_ns = [50_000_000, 70_000_000]
    return o


def test_summary_scores_rechecked_top5_and_ablations():
    outcomes = {
        "pc-0001": outcome("pc-0001", "MA", ["x", "c1"], lex=["c1"], vec=["x"]),
        "pc-0002": outcome(
            "pc-0002", "PV", ["y1", "y2", "y3", "y4", "y5", "c2"], lex=[], vec=["c2"]
        ),  # rank 6 -> miss@5
        "pc-0003": outcome("pc-0003", "CO", ["c3"], lex=["c3"], vec=["c3"]),
    }
    s = e.summarize("A2+V", QUERIES, outcomes, MAPPING)
    per = s.pop("_per_query_recall_at_5")
    assert per == {"pc-0001": 1.0, "pc-0002": 0.0, "pc-0003": 0.5}
    assert round(s["all"]["recall_at_5"], 4) == 0.5 and round(s["all"]["hit_at_5"], 4) == round(2 / 3, 4)
    assert s["all"]["fused_recall_at_20"] > s["all"]["recall_at_5"]  # c2 counted at rank 6 in the fused list
    assert s["all"]["lexical_only_recall_at_5"] == 0.5 and round(s["all"]["vector_only_recall_at_5"], 4) == 0.5
    assert s["scopes"][LANGUAGE_MATCHED]["queries"] == 2 and s["scopes"][CROSS_LINGUAL]["queries"] == 1
    assert s["invalid_version_citation_rate"] == 0.0 and s["dropped_by_recheck_total"] == {"status_not_active": 3}
    assert s["not_reproducible_queries"] == [] and s["latency_ms"]["p95"] == 70.0
    gate = e.gate_view({**s, "leak_violations": []})
    assert gate["passes_probe_scale_gate"] is False and gate["checks"]["invalid_version_citation_rate_zero"] is True


def test_non_reproducible_and_non_current_are_reported():
    o = outcome("pc-0001", "MA", ["c1"], non_current=1)
    o.accepted = [["c1"], ["c1", "z"]]
    outcomes = {"pc-0001": o, "pc-0002": outcome("pc-0002", "PV", ["c2"]), "pc-0003": outcome("pc-0003", "CO", ["c3"])}
    s = e.summarize("B2+V", QUERIES, outcomes, MAPPING)
    assert s["not_reproducible_queries"] == ["pc-0001"] and s["invalid_version_citation_rate"] > 0
    gate = e.gate_view({**s, "leak_violations": []})
    assert gate["checks"]["reproducible"] is False and gate["checks"]["invalid_version_citation_rate_zero"] is False


def test_report_renders_systems_groups_and_paired_lines(tmp_path):
    outcomes = {q.sample_id: outcome(q.sample_id, q.dept, [MAPPING[q.gold_ids[0]][0]]) for q in QUERIES}
    s = e.summarize("A2+V", QUERIES, outcomes, MAPPING)
    s.pop("_per_query_recall_at_5")
    s["leak_violations"] = []
    results = {
        "run_manifest_sha256": "0" * 64,
        "systems": {"A2+V": s},
        "gates": {"A2+V": e.gate_view(s)},
        "paired": {
            "B2+V minus A2+V": {
                "point": 1.5,
                "ci_low": -0.5,
                "ci_high": 3.5,
                "resamples": 2000,
                "seed": 1,
                "level": 0.95,
            }
        },
    }
    manifest = {
        "run_id": "unit",
        "dataset": {
            "version": "v2",
            "dataset_hash": "1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321",
        },
        "measurement": {"as_of": "2026-09-20", "rrf_k": 60.0, "k_lexical": 20, "k_vector": 20, "fused_limit": 20},
    }
    e.write_report(tmp_path, manifest, results)
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert (
        "| A2+V | 0.833 (3) |" in md
        and "B2+V minus A2+V: +1.50 pp" in md
        and "| MA | 1 | 1.000 (diagnostic: n < 8) |" in md
    )
    json.dumps(results)  # serialisable as written


def test_main_set_flags_split_no_answer_conflict_and_probe_subsets():
    queries = QUERIES + [
        Query("ms-0001", "PV", "conflict q", ("negation", "version_conflict"), ("g4",), "en", language="en"),
        Query("ms-0002", "MA", "no answer q", ("no_answer",), (), "", language="zh"),
        Query("ms-0003", "CO", "no answer q2", ("no_answer",), (), "", language="zh"),
    ]
    mapping = {**MAPPING, "g4": ["c4"]}
    outcomes = {
        "pc-0001": outcome("pc-0001", "MA", ["c1"]),
        "pc-0002": outcome("pc-0002", "PV", ["c2"]),
        "pc-0003": outcome("pc-0003", "CO", ["c3"]),
        "ms-0001": outcome("ms-0001", "PV", ["c4"], non_current=1),  # cited, but a historical version leaked too
        "ms-0002": outcome("ms-0002", "MA", []),  # nothing survives the re-check -> abstains at any threshold
        "ms-0003": outcome("ms-0003", "CO", ["z1"]),
    }
    outcomes["ms-0003"].reranked = [["z1"]] * 2
    outcomes["ms-0003"].top_score = 0.25
    flags = {
        "ms-0001": e.SampleFlags(answerable=True, conflict=True, imported=False),
        "ms-0002": e.SampleFlags(answerable=False),
        "ms-0003": e.SampleFlags(answerable=False),
        **{q.sample_id: e.SampleFlags(imported=True) for q in QUERIES},
    }
    s = e.summarize("A2+V", queries, outcomes, mapping, flags=flags, abstain_threshold=0.3)
    s.pop("_per_query_recall_at_5")
    assert s["all"]["queries"] == 4  # no-answer samples never enter the Recall@5 denominator
    assert s["subsets"]["probe_imported"]["queries"] == 3 and s["subsets"]["main_new"]["queries"] == 1
    assert s["subsets"]["conflict"]["queries"] == 1
    labels = [g["label"] for g in s["all"]["by_slice"]]
    assert labels[-1] == "version_conflict" and "long_context" not in labels  # only slices present in the set
    cf = s["conflict"]
    assert cf["current_cited_rate"] == 1.0 and cf["historical_not_cited_rate"] == 0.0
    assert cf["current_cited_and_historical_not_cited_rate"] == 0.0
    na = s["no_answer"]
    assert na["queries"] == 2 and na["abstention_accuracy"] == 1.0  # empty list, and 0.25 < 0.3
    sweep = {r["threshold"]: r["no_answer_accuracy"] for r in na["threshold_sweep"]}
    assert sweep[0.0] == 0.5 and sweep[0.3] == 1.0 and sweep[0.5] == 1.0
    assert na["false_abstention_rate_answerable"] == 0.0  # answerable outcomes carry no reranker score here
    gate = e.gate_view({**s, "leak_violations": []})
    assert gate["checks"]["abstention_accuracy_ge_0.9"] is True
    assert gate["checks"]["conflict_current_cited_and_historical_not_cited_rate_is_1"] is False
    assert gate["scale"] == "probe" and gate["passes_gate"] is False


def test_load_sample_flags_reads_answerable_conflict_and_imported(tmp_path):
    lines = [
        {"sample_id": "pc-0001", "slices": ["dose_unit"]},
        {"sample_id": "ms-0001", "slices": ["negation", "version_conflict"]},
        {"sample_id": "ms-0002", "slices": ["no_answer"], "answerable": False},
    ]
    (tmp_path / "samples.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    flags = e.load_sample_flags(tmp_path)
    assert flags["pc-0001"] == e.SampleFlags(answerable=True, conflict=False, imported=True)
    assert flags["ms-0001"] == e.SampleFlags(answerable=True, conflict=True, imported=False)
    assert flags["ms-0002"] == e.SampleFlags(answerable=False, conflict=False, imported=False)
