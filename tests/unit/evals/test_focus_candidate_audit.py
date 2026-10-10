"""Evidence lost by compression must not be hidden by an any-hit or changed-query denominator."""

import pytest
from scripts.audit_focus_candidate import RecordingScorer, audit_case, inspect_gold, summarize

from tests.unit.harness._fixtures import evidence


def gold(gid, key, span=None):
    return {"gold_id": gid, "key_text": key, "evidence_span": {"text": span or key}}


def entry(*chunks, status="mapped"):
    return {"status": status, "chunk_ids": list(chunks)}


def test_gold_alternatives_are_or_but_separate_gold_groups_are_and():
    checked = inspect_gold(
        [gold("g1", "7 calendar days"), gold("g2", "8 additional days")],
        {"g1": entry("a", "b"), "g2": entry("c")},
        {"a": "7 calendar days", "b": "7 calendar days", "c": "8 additional days"},
        {"a": "[…]", "b": "7 calendar days", "c": "[…]"},
    )
    assert checked["all_keys_before"] and not checked["all_keys_after"]
    assert checked["gold"][0]["kept_chunks"] == ["b"]
    assert checked["gold"][1]["status"] == "hidden_by_focus"


def test_unmappable_absent_and_unlocatable_gold_remain_distinct_misses():
    checked = inspect_gold(
        [gold("u", "one"), gold("a", "two"), gold("x", "three")],
        {"u": entry(status="unmappable"), "a": entry("absent"), "x": entry("visible")},
        {"visible": "different text"},
        {"visible": "different text"},
    )
    assert [g["status"] for g in checked["gold"]] == ["unmappable", "not_in_context", "key_unlocatable"]
    assert checked["required_groups"] == 3 and not checked["all_keys_before"]


def test_key_retention_does_not_mean_its_numeric_negation_and_condition_span_survived():
    checked = inspect_gold(
        [gold("g", "report within 7 days", "If fatal, report within 7 days; not for non-serious events.")],
        {"g": entry("a")},
        {"a": "If fatal, report within 7 days; not for non-serious events."},
        {"a": "[…] report within 7 days […]"},
    )
    assert checked["all_keys_after"] and checked["all_spans_before"] and not checked["all_spans_after"]
    assert checked["gold"][0]["risk_markers"] == ["numeric", "negation", "condition"]


def test_elision_is_not_removed_to_construct_a_key_across_an_omitted_condition():
    checked = inspect_gold([gold("g", "dose 10 mg")], {"g": entry("a")}, {"a": "dose 10 mg"}, {"a": "dose […] 10 mg"})
    assert checked["gold"][0]["status"] == "hidden_by_focus"


def test_normalized_matching_retains_decimals_width_and_spacing_without_dropping_negation():
    checked = inspect_gold(
        [gold("g", "Do not exceed ０.０５ mg/kg")],
        {"g": entry("a")},
        {"a": "Do not exceed 0.05 mg/kg."},
        {"a": "Do not exceed\n0.05 mg / kg."},
    )
    assert checked["all_keys_after"]
    assert "negation" in checked["gold"][0]["risk_markers"]


def test_legend_titles_cannot_rescue_a_key_that_was_removed_from_evidence_body():
    key = "Patients under 18 are not eligible"
    text = "First background sentence is the preferred discussion with abundant descriptive information. "
    text += " ".join(
        f"Background topic {i} provides unrelated general information about this document." for i in range(8)
    )
    text += f" {key}."
    items = [evidence("a", "Short introductory material.", doc_id="d1"), evidence("b", text, doc_id="d2")]
    case = {
        "sample_id": "test",
        "dept": "MA",
        "language": "en",
        "slices": ["negation"],
        "query_changed": False,
        "query": "background",
        "rewritten": (),
        "titles": {"d1": "Intro", "d2": key},
        "evidence": [e.model_dump(mode="json") for e in items],
        "gold": [gold("g", key)],
        "mapping": {"g": entry("b")},
    }
    row = audit_case(case, lambda q, ts: [100 if "First background" in t else 0 if key in t else 1 for t in ts])
    assert row["all_keys_before"] and not row["all_keys_after"]
    assert row["gold"][0]["status"] == "hidden_by_focus"
    assert len(row["scorer_calls"]) == 1 and row["evidence"][1]["sha256"] == items[1].evidence_text_hash


@pytest.mark.parametrize("scores", [[0], [0, float("nan")], [0, float("inf")]])
def test_non_finite_or_misbound_sentence_scores_are_rejected(scores):
    with pytest.raises(ValueError, match="invalid sentence score"):
        RecordingScorer(lambda q, t: scores)("q", ["one", "two"])


def test_changed_queries_are_separate_and_group_losses_have_their_own_denominator():
    checked = inspect_gold([gold("g", "one")], {"g": entry("a")}, {"a": "one"}, {"a": "[…]"})
    rows = [
        {"sample_id": sid, "query_changed": changed, **checked} for sid, changed in [("same", False), ("new", True)]
    ]
    summary = summarize(rows)
    assert summary["unchanged_query"]["key_complete_to_incomplete"] == ["same"]
    assert summary["changed_query_stale_context"]["key_complete_to_incomplete"] == ["new"]
    assert summary["all_archived_context_diagnostics"]["required_gold_units"] == 2
    assert not summary["formal_gate"] and summary["hosted_model_calls"] == 0
