"""The source guard distinguishes requested sources from references carried by another document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from medops.retrieval.doc_focus import DocRef
from medops.retrieval.source_constraints import SOURCE_CONSTRAINT_VERSION, resolve_source_constraint

REPO = Path(__file__).resolve().parents[3]
MAIN = REPO / "evals/main_set/main-v5-provisional"
CONTRACTS = REPO / "evals/source_semantics/main-v5-provisional.json"
SAFETY = REPO / "evals/safety_set/safety-v2-provisional/samples.jsonl"


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


CORPUS = json.loads((MAIN / "corpus.json").read_text())["documents"]
SAMPLES = {row["sample_id"]: row for row in _rows(MAIN / "samples.jsonl")}
SOURCE_CONTRACTS = json.loads(CONTRACTS.read_text())["items"]


def _visible_docs(dept: str) -> list[DocRef]:
    return [
        DocRef(row["document_key"], row["title"], row["doc_type"], row["document_key"])
        for row in CORPUS
        if row["owner_dept"] == dept
    ]


@pytest.mark.parametrize(
    "contract",
    [
        item
        for item in SOURCE_CONTRACTS
        if item["requirement"] in {"named_product", "named_document", "named_document_version", "equivalent_carrier"}
    ],
    ids=lambda item: item["sample_id"],
)
def test_explicit_source_contracts_resolve_only_the_reviewed_source(contract: dict[str, object]):
    sample = SAMPLES[contract["sample_id"]]
    result = resolve_source_constraint(sample["query"], _visible_docs(sample["dept"]))
    allowed = {source["document_key"] for group in contract["required_source_groups"] for source in group}
    assert result.required and not result.missing
    assert set(result.document_keys) == allowed


@pytest.mark.parametrize(
    "contract",
    [
        item
        for item in SOURCE_CONTRACTS
        if item["requirement"] in {"host_document_with_reference", "embedded_original_text"}
    ],
    ids=lambda item: item["sample_id"],
)
def test_reference_and_embedded_controls_never_require_the_referenced_document(contract: dict[str, object]):
    sample = SAMPLES[contract["sample_id"]]
    result = resolve_source_constraint(sample["query"], _visible_docs(sample["dept"]))
    allowed = {source["document_key"] for group in contract["required_source_groups"] for source in group}
    assert not result.missing
    assert not (set(result.document_keys) - allowed)


@pytest.mark.parametrize("sample_id", ["pc-0068", "pc-0100"])
def test_relationship_questions_do_not_create_a_single_source_constraint(sample_id: str):
    sample = SAMPLES[sample_id]
    result = resolve_source_constraint(sample["query"], _visible_docs(sample["dept"]))
    assert not result.required and not result.missing and not result.document_keys


@pytest.mark.parametrize("sample_id", ["ss-0090", "ss-0096"])
def test_invisible_named_document_becomes_a_generic_missing_constraint(sample_id: str):
    sample = next(row for row in _rows(SAFETY) if row["sample_id"] == sample_id)
    result = resolve_source_constraint(sample["query"], _visible_docs(sample["dept"]))
    forbidden = set(sample["acl"]["forbidden_document_keys"])
    forbidden_titles = set(sample["acl"]["forbidden_terms"])
    assert result.required and result.missing and not result.document_ids and not result.document_keys
    assert forbidden.isdisjoint(result.document_keys)
    assert all(title not in repr(result) for title in forbidden_titles)


def test_equivalent_carrier_does_not_prefix_match_addendum_two():
    docs = [
        DocRef("one", "GVP Module VI Addendum I – Duplicate management", "guideline", "ema-gvp-module-vi-addendum-i"),
        DocRef(
            "two", "GVP Module VI Addendum II – Masking personal data", "guideline", "ema-gvp-module-vi-addendum-ii"
        ),
    ]
    result = resolve_source_constraint("ICH-E2B(R2) Linked reports A.1.12", docs)
    assert result.document_ids == ("one",) and result.used_equivalent_carrier


def test_unqualified_ich_document_does_not_select_a_companion_annex():
    docs = [
        DocRef("main", "ICH Guideline for Good Clinical Practice E6(R3)", "guideline", "ich-e6-r3-step4-2025"),
        DocRef("annex", "ICH E6(R3) Annex 2: Additional Considerations", "guideline", "ich-e6-r3-step4-2026"),
    ]
    result = resolve_source_constraint("What records does ICH E6(R3) require?", docs)
    assert result.document_ids == ("main",)
    assert SOURCE_CONSTRAINT_VERSION == "source-constraint-v1"
