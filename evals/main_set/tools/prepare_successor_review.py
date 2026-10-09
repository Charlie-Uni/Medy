"""Prepare review inputs whose bytes change in a main-set successor.

This is a deterministic preflight.  It applies the confirmed annotation revision
to the frozen base, rebuilds every local (``ms-*``) reviewer record, and compares
its canonical hash with the hash recorded by the base review runs.  By default it
writes only the dependency closure caused by corpus metadata edits; samples that
are themselves present in ``proposals.json`` are reported but left to the normal
revision review packages.

No model is called.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pack_review import pack

from medops.core.canonical import canonical_json
from medops.evals.annotation_revision import check_confirmation, check_revision
from medops.evals.probe.review_provenance import batch_of

REPO = Path(__file__).resolve().parents[3]
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def prepare(
    revision: Path,
    confirmation: Path,
    out: Path,
    prompt: Path,
) -> dict[str, Any]:
    revision, confirmation, out, prompt = (path.resolve() for path in (revision, confirmation, out, prompt))
    check_revision(REPO, revision, with_pages=True)
    confirmed = check_confirmation(revision, confirmation)
    manifest = json.loads((revision / "manifest.json").read_text(encoding="utf-8"))
    base = (REPO / manifest["base_dataset"]["path"]).resolve()
    require(base.is_dir(), "revision base dataset is missing")

    base_samples = {row["sample_id"]: row for row in read_jsonl(base / "samples.jsonl")}
    proposals = json.loads((revision / "proposals.json").read_text(encoding="utf-8"))
    proposal_ids = {row["sample_id"] for row in proposals if row["sample_id"].startswith("ms-")}
    projected = copy.deepcopy(base_samples)
    for proposal in proposals:
        if proposal["sample_id"].startswith("ms-"):
            projected[proposal["sample_id"]] = copy.deepcopy(proposal["after"])

    corpus = copy.deepcopy(json.loads((base / "corpus.json").read_text(encoding="utf-8")))
    documents = {row["document_key"]: row for row in corpus["documents"]}
    edited_document_keys: set[str] = set()
    for edit in json.loads((revision / "corpus_edits.json").read_text(encoding="utf-8")):
        document = documents[edit["document_key"]]
        require(document[edit["field"]] == edit["before"], f"stale corpus edit: {edit['document_key']}")
        document[edit["field"]] = edit["after"]
        edited_document_keys.add(edit["document_key"])

    local_samples = [sample for sid, sample in sorted(projected.items()) if sid.startswith("ms-")]
    current_records = {record["sample_id"]: record for record in pack(local_samples, documents, projected)}
    old_hashes: dict[str, str] = {}
    for batch in BATCHES:
        run = json.loads((base / f"review_evidence/run_{batch}.json").read_text(encoding="utf-8"))
        overlap = old_hashes.keys() & run["sample_input_sha256"].keys()
        require(not overlap, f"duplicate base review coverage: {sorted(overlap)[:3]}")
        old_hashes.update(run["sample_input_sha256"])

    current_hashes = {sid: sha(canonical_json(record).encode("utf-8")) for sid, record in current_records.items()}
    changed_ids = {sid for sid, digest in current_hashes.items() if old_hashes.get(sid) != digest}
    dependency_ids = changed_ids - proposal_ids
    require(dependency_ids, "no corpus-edit-dependent review inputs changed")
    require(
        all(current_records[sid]["document"]["document_key"] in edited_document_keys for sid in dependency_ids),
        "an unproposed input changed outside the edited document closure",
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sid in sorted(dependency_ids):
        grouped[batch_of(projected[sid])].append(current_records[sid])
    require(set(grouped) <= set(BATCHES), "unknown review batch")

    out.mkdir(parents=True, exist_ok=True)
    prompt_raw = prompt.read_bytes()
    (out / "review_prompt.md").write_bytes(prompt_raw)
    batches = []
    for batch, records in sorted(grouped.items()):
        raw = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records).encode("utf-8")
        path = out / f"input_{batch}.jsonl"
        path.write_bytes(raw)
        batches.append(
            {
                "batch": batch,
                "count": len(records),
                "sample_ids": [record["sample_id"] for record in records],
                "input_file": path.name,
                "input_sha256": sha(raw),
                "input_chars": len(raw.decode("utf-8")),
                "prompt_sha256": sha(prompt_raw),
                "recommended_chunk_size": 1,
            }
        )

    result = {
        "format": "main-successor-dependent-review-preparation-v1",
        "status": "inputs_prepared",
        "revision": revision.relative_to(REPO).as_posix(),
        "revision_manifest_sha256": sha((revision / "manifest.json").read_bytes()),
        "confirmation": confirmation.relative_to(REPO).as_posix(),
        "confirmation_sha256": sha(confirmation.read_bytes()),
        "human_confirmation": confirmed,
        "base_dataset": manifest["base_dataset"],
        "edited_document_keys": sorted(edited_document_keys),
        "all_changed_review_input_ids": sorted(changed_ids),
        "proposal_review_input_ids": sorted(changed_ids & proposal_ids),
        "dependent_review_input_ids": sorted(dependency_ids),
        "batches": batches,
        "model_calls_by_preparation": 0,
        "note": (
            "These inputs changed only because corpus metadata is part of the reviewer record. "
            "One item per call prevents an unrelated verdict cascade."
        ),
    }
    (out / "preparation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", type=Path)
    parser.add_argument("--confirmation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.revision, args.confirmation, args.out, args.prompt), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
