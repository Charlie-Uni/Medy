"""Revised gold must stay traceable, complete, paired, and explicitly unreviewed."""

import copy
import json
from pathlib import Path

import pytest

from medops.evals.annotation_revision import (
    check_annotations,
    check_confirmation,
    check_revision,
    projected_distribution,
)
from medops.evals.datasets import load_frozen_dataset, read_rows
from medops.evals.evidence import all_required_evidence

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / "evals/main_set/drafts/revision-2026-10-08"
BASE = ROOT / "evals/main_set/main-v3-provisional"
DRAFT_V2 = ROOT / "evals/main_set/drafts/revision-2026-10-08-v2"


@pytest.fixture
def inputs():
    manifest = json.loads((DRAFT / "manifest.json").read_text())
    return {
        "proposals": json.loads((DRAFT / "proposals.json").read_text()),
        "baseline": {s["sample_id"]: s for s in read_rows(BASE / "samples.jsonl")},
        "required_ids": set(manifest["target_sample_ids"]),
        "docs": {d["source_hash"]: d for d in json.loads((BASE / "corpus.json").read_text())["documents"]},
        "schema": json.loads((ROOT / "evals/main_set/schema/probe_sample.schema.json").read_text()),
        "snapshot": json.loads((DRAFT / "chunks.snapshot.json").read_text()),
        "mapping": json.loads((DRAFT / "chunk_mapping.preview.json").read_text()),
    }


def test_checked_in_revision_is_complete_but_not_ready_for_freezing():
    result = check_revision(ROOT, DRAFT)
    assert result["checks_passed"] and not result["freeze_ready"]
    assert (result["target_samples"], result["linked_twins"], result["gold_units"]) == (13, 5, 37)
    assert result["mapping"] == {"mapped": 37}
    assert result["projected_long_context"] == 19  # retain the real quota gap, never inflate labels
    assert len(result["changed_probe_imports"]) == 3
    with pytest.raises(ValueError, match="frozen dataset manifest"):
        load_frozen_dataset(DRAFT)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("carry_review", "old review"),
        ("missing_twin", "linked English twins"),
        ("wrong_before", "baseline annotation changed"),
        ("wrong_version", "source version mismatch"),
        ("bad_offset", "key offset mismatch"),
        ("flatten", "lost or flattened"),
        ("stale_long_context", "stale long_context label"),
        ("twin_slices", "twin slices differ"),
    ],
)
def test_revision_regressions_are_rejected(inputs, mutation, message):
    record = next(p for p in inputs["proposals"] if p["sample_id"] == "ms-0124")
    gold = record["after"]["required_gold_evidence"][0]
    if mutation == "carry_review":
        record["after"]["review"] = copy.deepcopy(inputs["baseline"]["ms-0124"]["review"])
    elif mutation == "missing_twin":
        inputs["proposals"] = [p for p in inputs["proposals"] if p["sample_id"] != "ms-0125"]
    elif mutation == "wrong_before":
        record["before_sha256"] = "0" * 64
    elif mutation == "wrong_version":
        gold["version_label"] = "another revision"
    elif mutation == "bad_offset":
        entry = next(e for e in inputs["mapping"]["entries"] if e["gold_id"] == gold["gold_id"])
        entry["key_start"] += 1
        entry["key_end"] += 1
    elif mutation == "flatten":
        record["required_gold_groups"] = [[cid for group in record["required_gold_groups"] for cid in group]]
    elif mutation == "stale_long_context":
        record["after"]["slices"].append("long_context")
    else:
        twin = next(p for p in inputs["proposals"] if p["sample_id"] == "ms-0206")
        twin["after"]["slices"].remove("protocol_id")
    with pytest.raises(ValueError, match=message):
        check_annotations(**inputs)


@pytest.mark.parametrize("sid", ["ms-0124", "ms-0205", "ms-0241", "ms-0243", "ms-0298"])
def test_partial_citation_cannot_pass_revised_joint_evidence(inputs, sid):
    groups = next(p["required_gold_groups"] for p in inputs["proposals"] if p["sample_id"] == sid)
    assert not all_required_evidence(groups, groups[0])
    assert all_required_evidence(groups, [group[0] for group in groups])


def test_replenished_revision_meets_counts_without_claiming_review():
    result = check_revision(ROOT, DRAFT_V2)
    assert result["checks_passed"] and not result["freeze_ready"]
    assert result["new_samples"] == 1 and result["gold_units"] == 39
    assert result["projected_long_context"] == 20
    assert result["projected_distribution"]["samples"] == 615
    assert result["projected_distribution"]["quota_shortfalls"] == {}


@pytest.mark.parametrize("mutation", ["duplicate_query", "pii", "id_reuse"])
def test_global_annotation_constraints_are_checked(inputs, mutation):
    sample = inputs["proposals"][0]["after"]
    if mutation == "duplicate_query":
        sample["query"] = inputs["baseline"]["ms-0001"]["query"]
        message = "not unique"
    elif mutation == "pii":
        sample["notes"] = "患者姓名：测试病人"
        message = "PII review"
    else:
        inputs["new_ids"] = {sample["sample_id"]}
        message = "must not reuse"
    with pytest.raises(ValueError, match=message):
        check_annotations(**inputs)


def test_new_gold_units_do_not_inflate_document_sample_counts(inputs):
    minimums = json.loads((BASE / "manifest.json").read_text())["minimums"]
    rows = copy.deepcopy(inputs["baseline"])
    sample = rows["ms-0124"]
    source = sample["required_gold_evidence"][0]["source_hash"]
    for i in range(10):
        rows[f"new-{i}"] = {**sample, "sample_id": f"new-{i}"}
    with pytest.raises(ValueError, match="document sample cap exceeded"):
        projected_distribution(rows, inputs["docs"], minimums)
    assert source in inputs["docs"]


def test_human_confirmation_binds_all_19_items_without_claiming_second_human():
    result = check_confirmation(DRAFT_V2, DRAFT_V2 / "human_confirmation_2026-10-08.json")
    assert result == {"status": "confirmed", "count": 19, "independent_second_human": False}


@pytest.mark.parametrize(
    "mutation", ["input_changed", "missing_item", "changed_group", "model_as_human", "second_human"]
)
def test_confirmation_cannot_be_reused_for_other_inputs_or_review_roles(tmp_path, mutation):
    record = json.loads((DRAFT_V2 / "human_confirmation_2026-10-08.json").read_text())
    if mutation == "input_changed":
        record["inputs"]["proposals_sha256"] = "0" * 64
    elif mutation == "missing_item":
        record["items"].pop()
    elif mutation == "changed_group":
        record["items"][0]["required_gold_groups_sha256"] = "0" * 64
    elif mutation == "model_as_human":
        record["actor"]["kind"] = "llm"
    else:
        record["scope"]["independent_second_human"] = True
    path = tmp_path / "confirmation.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        check_confirmation(DRAFT_V2, path)
