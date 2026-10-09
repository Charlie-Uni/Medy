"""Versioned source requirements for evaluation cases.

Evidence coverage and source compliance answer different questions:

* evidence groups say which facts must be cited (AND across groups, OR within one group);
* source groups say which document identities may satisfy the question's explicit source constraint.

The contracts are a sidecar bound to a frozen dataset.  They do not rewrite the frozen samples and they do not
infer that every identifier in a query is the requested source: a document may be the host, a cited reference, or
an embedded earlier text.  Only reviewed cases enter the source-compliance denominator.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from medops.core.canonical import sha256_hex
from medops.domain.common import DomainModel, NonEmptyStr

SOURCE_CONTRACT_FORMAT = "source-contracts-v1"
SOURCE_SCORER_VERSION = "source-compliance-v1-provisional"


class SourceIdentity(DomainModel):
    document_key: NonEmptyStr
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    version_label: NonEmptyStr


class SourceContract(DomainModel):
    sample_id: str = Field(pattern=r"^(pc|ms)-[0-9]{4}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirement: Literal[
        "named_product",
        "named_document",
        "named_document_version",
        "equivalent_carrier",
        "host_document_with_reference",
        "embedded_original_text",
        "relationship_statement",
    ]
    required_source_groups: tuple[tuple[SourceIdentity, ...], ...] = Field(min_length=1)
    referenced_mentions: tuple[NonEmptyStr, ...] = ()
    availability: Literal["available", "unavailable_to_requester"] = "available"
    unavailable_behavior: Literal["insufficient_evidence", "clarify"] = "insufficient_evidence"
    rationale: NonEmptyStr
    decision_basis: NonEmptyStr

    @model_validator(mode="after")
    def _groups_are_nonempty_and_unique(self) -> SourceContract:
        if any(not group for group in self.required_source_groups):
            raise ValueError("source groups cannot be empty")
        identities = [identity.source_hash for group in self.required_source_groups for identity in group]
        if len(identities) != len(set(identities)):
            raise ValueError("a source identity may occur in only one source group")
        if (
            self.requirement
            in {
                "equivalent_carrier",
                "host_document_with_reference",
                "embedded_original_text",
                "relationship_statement",
            }
            and not self.referenced_mentions
        ):
            raise ValueError(f"{self.requirement} needs the non-target document mentions recorded")
        return self


class SourceContractSet(DomainModel):
    format: Literal["source-contracts-v1"]
    scorer_version: Literal["source-compliance-v1-provisional"]
    dataset_id: NonEmptyStr
    dataset_version: NonEmptyStr
    dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["provisional"]
    reviewed_scope: NonEmptyStr
    items: tuple[SourceContract, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sample_ids_are_unique(self) -> SourceContractSet:
        ids = [item.sample_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("source contracts contain duplicate sample ids")
        return self


def load_source_contracts(path: Path) -> SourceContractSet:
    return SourceContractSet.model_validate_json(path.read_text(encoding="utf-8"))


def validate_source_contracts(
    contracts: SourceContractSet,
    manifest: dict[str, Any],
    samples: Sequence[dict[str, Any]],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """Bind every reviewed contract to the exact frozen query, corpus identity and gold source.

    A source contract may contain alternatives, but each identity has to exist in this frozen corpus.  Every gold
    source used by the sample must be admitted by a group; otherwise the sidecar and the sample disagree.
    """
    if contracts.format != SOURCE_CONTRACT_FORMAT or contracts.scorer_version != SOURCE_SCORER_VERSION:
        raise ValueError("unsupported source-contract format or scorer")
    for field in ("dataset_id", "dataset_version", "dataset_hash"):
        if getattr(contracts, field) != manifest[field]:
            raise ValueError(f"source contracts {field} differs from dataset")
    by_sample = {sample["sample_id"]: sample for sample in samples}
    if len(by_sample) != len(samples):
        raise ValueError("dataset contains duplicate sample ids")
    documents = corpus.get("documents")
    if not isinstance(documents, list):
        raise ValueError("corpus documents are missing")
    by_hash = {document["source_hash"]: document for document in documents}
    if len(by_hash) != len(documents):
        raise ValueError("corpus contains duplicate source hashes")
    counts: dict[str, int] = {}
    for contract in contracts.items:
        sample = by_sample.get(contract.sample_id)
        if sample is None:
            raise ValueError(f"{contract.sample_id}: source contract references a missing sample")
        if sha256_hex(sample["query"]) != contract.query_sha256:
            raise ValueError(f"{contract.sample_id}: source contract query hash differs")
        allowed_hashes: set[str] = set()
        for group in contract.required_source_groups:
            for identity in group:
                document = by_hash.get(identity.source_hash)
                if document is None:
                    raise ValueError(f"{contract.sample_id}: source identity is absent from the frozen corpus")
                if (
                    document["document_key"] != identity.document_key
                    or document["version_label"] != identity.version_label
                ):
                    raise ValueError(f"{contract.sample_id}: source identity metadata differs from the frozen corpus")
                allowed_hashes.add(identity.source_hash)
        gold_hashes = {gold["source_hash"] for gold in sample.get("required_gold_evidence", [])}
        if gold_hashes and not gold_hashes <= allowed_hashes:
            raise ValueError(f"{contract.sample_id}: gold source is not admitted by the source contract")
        counts[contract.requirement] = counts.get(contract.requirement, 0) + 1
    return {
        "contracts": len(contracts.items),
        "by_requirement": dict(sorted(counts.items())),
        "formal_gate": False,
    }


def required_sources_satisfied(groups: Sequence[Sequence[SourceIdentity]], cited_source_hashes: Iterable[str]) -> bool:
    """AND across source groups, OR within one group.  Empty groups cannot pass."""
    cited = set(cited_source_hashes)
    return bool(groups) and all(bool({source.source_hash for source in group} & cited) for group in groups)


def source_contract_passes(
    contract: SourceContract,
    *,
    outcome: str,
    cited_source_hashes: Iterable[str],
    reason_codes: Sequence[str] = (),
) -> bool:
    if contract.availability == "unavailable_to_requester":
        expected = {contract.unavailable_behavior}
        return outcome == "escalated" and set(reason_codes) == expected
    return (
        outcome == "answered"
        and not reason_codes
        and required_sources_satisfied(contract.required_source_groups, cited_source_hashes)
    )


def summarize_source_compliance(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Summarize already-bound structural results.  Pending cases keep the rate unknown."""
    if len({case["sample_id"] for case in cases}) != len(cases):
        raise ValueError("duplicate source-compliance cases")
    decided = [case for case in cases if case.get("passed") is not None]
    pending = len(cases) - len(decided)
    passed = sum(case["passed"] is True for case in decided)
    by_requirement: dict[str, dict[str, int | float | None]] = {}
    for requirement in sorted({str(case["requirement"]) for case in cases}):
        subset = [case for case in cases if case["requirement"] == requirement]
        known = [case for case in subset if case.get("passed") is not None]
        n = sum(case["passed"] is True for case in known)
        by_requirement[requirement] = {
            "numerator": n,
            "denominator": len(subset),
            "pending": len(subset) - len(known),
            "rate": n / len(subset) if len(known) == len(subset) and subset else None,
        }
    return {
        "scorer_version": SOURCE_SCORER_VERSION,
        "formal_gate": False,
        "numerator": passed,
        "denominator": len(cases),
        "pending": pending,
        "rate": passed / len(cases) if cases and not pending else None,
        "by_requirement": by_requirement,
    }
