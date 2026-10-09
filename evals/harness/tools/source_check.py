#!/usr/bin/env python3
"""Report explicit source compliance from a completed ask run; makes no model or database calls.

The run must contain record-136 answer-review snapshots.  Cases without a row or snapshot stay pending and keep the
aggregate rate null.  This report supplements the frozen main score; it never rewrites historical success labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from medops.core.canonical import sha256_hex
from medops.evals.answer_review import load_snapshot
from medops.evals.datasets import load_frozen_dataset, read_rows, sha256_file
from medops.evals.source_semantics import (
    load_source_contracts,
    source_contract_passes,
    summarize_source_compliance,
    validate_source_contracts,
)

REPO = Path(__file__).resolve().parents[3]


def evaluate(run: Path, dataset: Path, contracts_path: Path) -> dict:
    manifest = load_frozen_dataset(dataset, expected_id="precise_clause_main")
    binding = json.loads((run / "dataset_binding.json").read_text(encoding="utf-8"))
    expected_binding = {key: manifest[key] for key in ("dataset_id", "dataset_version", "dataset_hash")}
    if binding != expected_binding:
        raise ValueError("run is bound to another dataset")
    samples = read_rows(dataset / "samples.jsonl")
    corpus = json.loads((dataset / "corpus.json").read_text(encoding="utf-8"))
    contracts = load_source_contracts(contracts_path)
    contract_summary = validate_source_contracts(contracts, manifest, samples, corpus)
    latest = {row["sample_id"]: row for row in read_rows(run / "rows.jsonl")}
    cases = []
    for contract in contracts.items:
        row = latest.get(contract.sample_id)
        result = {
            "sample_id": contract.sample_id,
            "requirement": contract.requirement,
            "passed": None,
            "outcome": row.get("outcome") if row else None,
            "cited_document_keys": [],
            "pending_reason": "run has no row for this reviewed case" if row is None else None,
        }
        if row is not None:
            reference = row.get("answer_review_input")
            if not reference:
                result["pending_reason"] = "row has no answer-review snapshot"
            else:
                case = load_snapshot(run, reference)
                if case["sample_id"] != contract.sample_id or sha256_hex(case["query"]) != contract.query_sha256:
                    raise ValueError(f"{contract.sample_id}: run snapshot differs from the source contract")
                answer = case["answer"] or {"citations": []}
                by_chunk = {e["citation"]["chunk_id"]: e["citation"]["doc_id"] for e in case["evidence"]}
                cited_doc_ids = {by_chunk[c["chunk_id"]] for c in answer["citations"]}
                cited_documents = [case["documents"][doc_id] for doc_id in sorted(cited_doc_ids)]
                result["cited_document_keys"] = sorted(document["document_key"] for document in cited_documents)
                result["passed"] = source_contract_passes(
                    contract,
                    outcome=row["outcome"],
                    cited_source_hashes=[document["source_hash"] for document in cited_documents],
                    reason_codes=row.get("reason_codes", []),
                )
                result["pending_reason"] = None
        cases.append(result)
    return {
        "format": "source-compliance-report-v1",
        "dataset": {
            "dataset_version": manifest["dataset_version"],
            "dataset_hash": manifest["dataset_hash"],
        },
        "inputs": {
            "contracts_path": str(contracts_path),
            "contracts_sha256": sha256_file(contracts_path),
            "dataset_binding_sha256": sha256_file(run / "dataset_binding.json"),
            "rows_sha256": sha256_file(run / "rows.jsonl"),
        },
        "contract_summary": contract_summary,
        "metrics": summarize_source_compliance(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = evaluate(args.run, args.dataset, args.contracts)
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as handle:
            handle.write(raw)
    else:
        print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
