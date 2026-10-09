"""Prepare exact, first-human-confirmed inputs for independent LLM review; makes no model calls.

python evals/main_set/tools/prepare_revision_review.py REVISION --confirmation CONFIRMATION
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pack_review import pack  # noqa: E402

from medops.evals.annotation_revision import check_confirmation, check_revision  # noqa: E402
from medops.evals.datasets import read_rows, sha256_file  # noqa: E402
from medops.evals.probe.review_provenance import batch_of  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]


def prepare(revision: pathlib.Path, confirmation: pathlib.Path) -> dict:
    check_revision(REPO, revision, with_pages=True)
    human = check_confirmation(revision, confirmation)
    manifest = json.loads((revision / "manifest.json").read_text())
    base = REPO / manifest["base_dataset"]["path"]
    proposals = json.loads((revision / "proposals.json").read_text())
    samples = [p["after"] for p in proposals]
    parents = {s["sample_id"]: s for s in read_rows(base / "samples.jsonl")}
    parents.update({s["sample_id"]: s for s in samples})
    corpus = copy.deepcopy(json.loads((base / "corpus.json").read_text()))
    docs = {d["document_key"]: d for d in corpus["documents"]}
    for edit in json.loads((revision / "corpus_edits.json").read_text()):
        docs[edit["document_key"]][edit["field"]] = edit["after"]
    records = pack(samples, docs, parents)
    sample_by_id = {s["sample_id"]: s for s in samples}
    grouped = defaultdict(list)
    for record in records:
        scope = "probe" if record["sample_id"].startswith("pc-") else "main"
        grouped[(scope, batch_of(sample_by_id[record["sample_id"]]))].append(record)
    out = revision / "review"
    files, batches = {}, []
    for (scope, batch), rows in sorted(grouped.items()):
        rows.sort(key=lambda r: r["sample_id"])
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        name = f"{scope}/input_{batch}.jsonl"
        files[name] = text
        prompt = out / scope / "review_prompt.md"
        if not prompt.is_file():
            raise ValueError(f"review prompt must be prepared first: {prompt}")
        batches.append(
            {
                "scope": scope,
                "batch": batch,
                "count": len(rows),
                "sample_ids": [r["sample_id"] for r in rows],
                "input_file": name,
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "prompt_file": str(prompt.relative_to(out)),
                "prompt_sha256": sha256_file(prompt),
                "input_chars": len(text),
                "prompt_chars_per_call": len(prompt.read_text()),
                "recommended_chunk_size": 1,
            }
        )
    for name, text in files.items():
        path = out / name
        if path.exists() and path.read_text() != text:
            raise ValueError(f"review input already exists with different content; use a new review package: {name}")
    for name, text in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    summary = {
        "status": "inputs_prepared",
        "revision": str(revision.relative_to(REPO)),
        "revision_manifest_sha256": sha256_file(revision / "manifest.json"),
        "confirmation_sha256": sha256_file(confirmation),
        "human_confirmation": human,
        "samples": len(records),
        "gold_units": sum(len(s["required_gold_evidence"]) for s in samples),
        "multi_gold_records": sum(r.get("record_format") == "multi-gold-review-v1" for r in records),
        "batches": batches,
        "model_calls_by_preparation": 0,
        "note": "Full page inputs stay local/ignored. No prior verdicts, owner approval or proposal rationale are sent. One item per call prevents unrelated re-review cascades.",
    }
    (out / "preparation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", type=pathlib.Path)
    parser.add_argument("--confirmation", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = prepare(args.revision.resolve(), args.confirmation.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
