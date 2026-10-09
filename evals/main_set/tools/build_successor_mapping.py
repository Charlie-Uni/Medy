"""Build a main-set successor mapping from a frozen base mapping plus reviewed preview entries.

This path is used when annotations change but the chunk coordinate system and corpus
source hashes remain stable.  Every changed or new gold must be present in the
revision preview; unchanged golds retain the frozen base mapping.  No database or
model call is made.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from medops.core.canonical import canonical_json
from medops.evals.probe.chunk_mapping import publish_artifact
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals/main_set/schema"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def golds(version: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for sample in read_jsonl(version / "samples.jsonl"):
        for gold in sample["required_gold_evidence"]:
            require(gold["gold_id"] not in result, f"duplicate gold_id: {gold['gold_id']}")
            result[gold["gold_id"]] = gold
    return result


def validate_frozen(version: Path, pages: Path) -> dict[str, Any]:
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    require(report.passed, f"frozen dataset validation failed: {version}")
    return json.loads((version / "manifest.json").read_text(encoding="utf-8"))


def build(
    base: Path,
    base_mapping_path: Path,
    successor: Path,
    preview_path: Path,
    pages: Path,
    *,
    generated_at: str,
) -> dict[str, Any]:
    base_manifest = validate_frozen(base, pages)
    successor_manifest = validate_frozen(successor, pages)
    require(successor_manifest["supersedes"] == base_manifest["dataset_version"], "datasets are not successors")
    require(
        successor_manifest["normalization"] == base_manifest["normalization"]
        and successor_manifest["extraction"] == base_manifest["extraction"],
        "coordinate system changed; a full chunk snapshot is required",
    )
    base_corpus = json.loads((base / "corpus.json").read_text(encoding="utf-8"))
    successor_corpus = json.loads((successor / "corpus.json").read_text(encoding="utf-8"))
    base_sources = {(row["document_key"], row["source_hash"], row["version_label"]) for row in base_corpus["documents"]}
    successor_sources = {
        (row["document_key"], row["source_hash"], row["version_label"]) for row in successor_corpus["documents"]
    }
    require(base_sources == successor_sources, "corpus source identity changed; a full chunk snapshot is required")

    base_mapping = json.loads(base_mapping_path.read_text(encoding="utf-8"))
    require(base_mapping["dataset_hash"] == base_manifest["dataset_hash"], "base mapping dataset hash mismatch")
    require(base_mapping["dataset_version"] == base_manifest["dataset_version"], "base mapping version mismatch")
    base_entries = {row["gold_id"]: row for row in base_mapping["entries"]}
    require(len(base_entries) == len(base_mapping["entries"]), "duplicate base mapping gold_id")

    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    require(preview.get("status") == "draft_preview", "unexpected preview status")
    preview_entries = {row["gold_id"]: row for row in preview["entries"]}
    require(len(preview_entries) == len(preview["entries"]), "duplicate preview gold_id")
    base_gold, successor_gold = golds(base), golds(successor)
    changed = {
        gold_id for gold_id, gold in successor_gold.items() if gold_id not in base_gold or gold != base_gold[gold_id]
    }
    require(
        changed <= preview_entries.keys(),
        f"changed gold is missing from preview: {sorted(changed - preview_entries.keys())}",
    )

    entries = []
    for gold_id in sorted(successor_gold):
        source = preview_entries.get(gold_id) or base_entries.get(gold_id)
        require(source is not None, f"gold lacks a mapping entry: {gold_id}")
        status = source["status"]
        chunk_ids = source["chunk_ids"]
        entries.append(
            {
                "gold_id": gold_id,
                "status": status,
                "chunk_ids": chunk_ids,
                "reason": source.get("reason") if status == "unmappable" else None,
            }
        )

    result = {
        "dataset_version": successor_manifest["dataset_version"],
        "dataset_hash": successor_manifest["dataset_hash"],
        "chunker_version": base_mapping["chunker_version"],
        "extraction": base_mapping["extraction"],
        "normalization": base_mapping["normalization"],
        "generated_at": generated_at,
        "generator": "medops.evals.main_successor_mapping/v1",
        "entries": entries,
    }
    schema = json.loads((SCHEMA_DIR / "chunk_mapping.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result))
    require(not errors, f"successor mapping violates schema: {errors[0].message if errors else ''}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--base-mapping", type=Path, required=True)
    parser.add_argument("--successor", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--generated-at", default=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"))
    args = parser.parse_args()
    result = build(
        args.base.resolve(),
        args.base_mapping.resolve(),
        args.successor.resolve(),
        args.preview.resolve(),
        args.pages.resolve(),
        generated_at=args.generated_at,
    )
    publish_artifact(
        (canonical_json(result) + "\n").encode("utf-8"),
        args.out,
        protected_dir=args.successor,
    )
    misses = [row for row in result["entries"] if row["status"] == "unmappable"]
    print(f"wrote {args.out}: {len(result['entries']) - len(misses)} mapped, {len(misses)} unmappable")


if __name__ == "__main__":
    main()
