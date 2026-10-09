"""Source identity is scored separately from factual evidence coverage."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from medops.evals.answer_review import save_snapshot
from medops.evals.source_semantics import (
    SourceContract,
    SourceIdentity,
    load_source_contracts,
    required_sources_satisfied,
    source_contract_passes,
    summarize_source_compliance,
    validate_source_contracts,
)

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "evals/main_set/main-v5-provisional"
CONTRACTS = REPO / "evals/source_semantics/main-v5-provisional.json"


def source(key: str, digest: str) -> SourceIdentity:
    return SourceIdentity(document_key=key, source_hash=digest * 64, version_label="v1")


def contract(*groups: tuple[SourceIdentity, ...], availability: str = "available") -> SourceContract:
    return SourceContract(
        sample_id="ms-0001",
        query_sha256="0" * 64,
        requirement="named_document",
        required_source_groups=groups,
        availability=availability,
        rationale="The named document is the requested source.",
        decision_basis="reviewed fixture",
    )


def test_current_contracts_bind_to_frozen_queries_corpus_and_gold_sources():
    manifest = json.loads((DATASET / "manifest.json").read_text())
    samples = [json.loads(line) for line in (DATASET / "samples.jsonl").read_text().splitlines() if line.strip()]
    corpus = json.loads((DATASET / "corpus.json").read_text())
    result = validate_source_contracts(load_source_contracts(CONTRACTS), manifest, samples, corpus)
    assert result["contracts"] == 34 and not result["formal_gate"]
    assert result["by_requirement"] == {
        "embedded_original_text": 4,
        "equivalent_carrier": 2,
        "host_document_with_reference": 12,
        "named_document": 3,
        "named_document_version": 5,
        "named_product": 6,
        "relationship_statement": 2,
    }


def test_source_groups_are_and_across_or_within():
    a, a_copy, b = source("a", "a"), source("a-copy", "c"), source("b", "b")
    groups = ((a, a_copy), (b,))
    assert required_sources_satisfied(groups, ["c" * 64, "b" * 64])
    assert not required_sources_satisfied(groups, ["a" * 64, "c" * 64])
    assert not required_sources_satisfied((), ["a" * 64])


def test_available_source_requires_an_answer_and_every_group():
    a, b = source("a", "a"), source("b", "b")
    item = contract((a,), (b,))
    assert source_contract_passes(item, outcome="answered", cited_source_hashes=["a" * 64, "b" * 64], reason_codes=[])
    assert not source_contract_passes(item, outcome="answered", cited_source_hashes=["a" * 64], reason_codes=[])
    assert not source_contract_passes(
        item,
        outcome="escalated",
        cited_source_hashes=[],
        reason_codes=["insufficient_evidence"],
    )


def test_unavailable_named_source_passes_only_the_bound_abstention():
    item = contract((source("a", "a"),), availability="unavailable_to_requester")
    assert source_contract_passes(
        item,
        outcome="escalated",
        cited_source_hashes=[],
        reason_codes=["insufficient_evidence"],
    )
    assert not source_contract_passes(item, outcome="answered", cited_source_hashes=["a" * 64])
    assert not source_contract_passes(
        item,
        outcome="escalated",
        cited_source_hashes=[],
        reason_codes=["system_failure"],
    )


def test_query_or_source_identity_drift_is_rejected():
    manifest = json.loads((DATASET / "manifest.json").read_text())
    samples = [json.loads(line) for line in (DATASET / "samples.jsonl").read_text().splitlines() if line.strip()]
    corpus = json.loads((DATASET / "corpus.json").read_text())
    raw = json.loads(CONTRACTS.read_text())
    raw["items"][0]["query_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="query hash differs"):
        validate_source_contracts(type(load_source_contracts(CONTRACTS)).model_validate(raw), manifest, samples, corpus)
    raw = json.loads(CONTRACTS.read_text())
    raw["items"][0]["required_source_groups"][0][0]["version_label"] = "wrong"
    with pytest.raises(ValueError, match="metadata differs"):
        validate_source_contracts(type(load_source_contracts(CONTRACTS)).model_validate(raw), manifest, samples, corpus)


def test_pending_results_never_produce_a_success_rate():
    report = summarize_source_compliance(
        [
            {"sample_id": "a", "requirement": "named_document", "passed": True},
            {"sample_id": "b", "requirement": "named_document", "passed": None},
        ]
    )
    assert report["numerator"] == 1 and report["denominator"] == 2 and report["pending"] == 1
    assert report["rate"] is None and report["by_requirement"]["named_document"]["rate"] is None


def test_source_check_binds_the_run_and_keeps_missing_cases_pending(tmp_path):
    manifest = json.loads((DATASET / "manifest.json").read_text())
    sample = next(
        row
        for row in map(json.loads, (DATASET / "samples.jsonl").read_text().splitlines())
        if row["sample_id"] == "ms-0056"
    )
    binding = {key: manifest[key] for key in ("dataset_id", "dataset_version", "dataset_hash")}
    (tmp_path / "dataset_binding.json").write_text(json.dumps(binding) + "\n")
    case = {
        "format": "answer-review-input-v1",
        "sample_id": sample["sample_id"],
        "sample_input_sha256": "0" * 64,
        "query": sample["query"],
        "dept": sample["dept"],
        "answerable": True,
        "outcome": "escalated",
        "answer": None,
        "evidence": [],
        "documents": {},
        "required_gold_evidence": sample["required_gold_evidence"],
        "versions": {
            "policy_version": "p",
            "retrieval_version": "r",
            "skill_version_set": [],
            "model_config_version": "m",
        },
    }
    reference = save_snapshot(tmp_path, case)
    (tmp_path / "rows.jsonl").write_text(
        json.dumps(
            {
                "sample_id": sample["sample_id"],
                "outcome": "escalated",
                "reason_codes": ["insufficient_evidence"],
                "answer_review_input": reference,
            }
        )
        + "\n"
    )
    evaluate = runpy.run_path(str(REPO / "evals/harness/tools/source_check.py"))["evaluate"]
    report = evaluate(tmp_path, DATASET, CONTRACTS)
    assert report["metrics"]["denominator"] == 34
    assert report["metrics"]["pending"] == 33 and report["metrics"]["rate"] is None
    decided = next(case for case in report["cases"] if case["sample_id"] == "ms-0056")
    assert decided["passed"] is False and decided["pending_reason"] is None

    (tmp_path / "dataset_binding.json").write_text(json.dumps({**binding, "dataset_hash": "f" * 64}) + "\n")
    with pytest.raises(ValueError, match="another dataset"):
        evaluate(tmp_path, DATASET, CONTRACTS)
