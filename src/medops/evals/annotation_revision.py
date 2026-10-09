"""Check annotation edit proposals without claiming completed review or freezing data.

python -m medops.evals.annotation_revision DIRECTORY [--with-pages] [--out REPORT]
The proposal payload deliberately has no review block: old approvals cover old input.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from medops.core.canonical import canonical_json
from medops.evals.datasets import dataset_file, load_frozen_dataset, read_rows, sha256_file
from medops.evals.probe.pii import find_pii
from medops.retrieval.lexical.normalization import normalize_text


def annotation_hash(sample: Any) -> str:
    return hashlib.sha256(canonical_json(sample).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _by_id(rows: list[dict], key: str) -> dict:
    result = {r[key]: r for r in rows}
    _require(len(result) == len(rows), f"duplicate {key}")
    return result


def _gold_without_ids(sample: dict) -> list[dict]:
    return [{k: v for k, v in gold.items() if k != "gold_id"} for gold in sample["required_gold_evidence"]]


def check_confirmation(directory: Path, confirmation_path: Path) -> dict[str, Any]:
    """Bind a recorded first-human decision to exact proposals; never promote other review roles."""
    confirmation = json.loads(confirmation_path.read_text(encoding="utf-8"))
    _require(confirmation["format"] == "human-annotation-confirmation-v1", "unknown confirmation format")
    _require(confirmation["status"] == "confirmed", "human annotation is not confirmed")
    _require(confirmation["actor"]["kind"] == "human", "model review cannot be human confirmation")
    _require(confirmation["scope"]["independent_second_human"] is False, "confirmation is not second-human review")
    for name, key in (
        ("manifest.json", "manifest_sha256"),
        ("proposals.json", "proposals_sha256"),
        ("corpus_edits.json", "corpus_edits_sha256"),
    ):
        _require(sha256_file(directory / name) == confirmation["inputs"][key], f"confirmation input changed: {name}")
    proposals = _by_id(json.loads((directory / "proposals.json").read_text()), "sample_id")
    items = _by_id(confirmation["items"], "sample_id")
    _require(items.keys() == proposals.keys(), "confirmation sample coverage mismatch")
    _require(confirmation["scope"]["sample_count"] == len(items), "confirmation count mismatch")
    for sid, proposal in proposals.items():
        item = items[sid]
        _require(item["decision"] == "confirmed", f"{sid}: annotation is not confirmed")
        _require(
            item["annotation_sha256"] == annotation_hash(proposal["after"]), f"{sid}: confirmation annotation changed"
        )
        _require(
            item["required_gold_groups_sha256"] == annotation_hash(proposal["required_gold_groups"]),
            f"{sid}: confirmation evidence groups changed",
        )
    edits = json.loads((directory / "corpus_edits.json").read_text())
    _require(confirmation["scope"]["corpus_title_edits"] == len(edits), "confirmation corpus edit count mismatch")
    if edits:
        _require(confirmation["corpus_edits_decision"] == "confirmed", "corpus edits are not confirmed")
    return {"status": "confirmed", "count": len(items), "independent_second_human": False}


def check_annotations(
    proposals: list[dict],
    baseline: dict[str, dict],
    required_ids: set[str],
    docs: dict[str, dict],
    schema: dict,
    snapshot: dict,
    mapping: dict,
    pages: dict[tuple[str, int], str] | None = None,
    new_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Validate the draft-specific shape, source anchors, complete groups and twin closure."""
    by_id = _by_id(proposals, "sample_id")
    linked = {sid for sid, s in baseline.items() if s.get("derived_from") in required_ids}
    new_ids = new_ids or set()
    _require(not new_ids & baseline.keys(), "new sample ids must not reuse baseline ids")
    _require(
        set(by_id) == required_ids | linked | new_ids, "revision must include all targets and linked English twins"
    )
    draft_schema = copy.deepcopy(schema)
    draft_schema["required"].remove("review")
    del draft_schema["properties"]["review"]
    validator = Draft202012Validator(draft_schema)
    chunks = list(_by_id(snapshot["chunks"], "chunk_id").values())
    mapped = _by_id(mapping["entries"], "gold_id")
    _require(
        mapping["status"] == "draft_preview" and mapping["evidence_rule"] == "gold-groups-v1", "draft mapping rule"
    )
    used = set()
    for sid, proposal in by_id.items():
        old, new = baseline.get(sid), proposal["after"]
        _require(
            proposal["before_sha256"] == (annotation_hash(old) if old else None), f"{sid}: baseline annotation changed"
        )
        _require(new["sample_id"] == sid, f"{sid}: sample identity changed")
        _require("review" not in new, f"{sid}: old review cannot be carried into revised input")
        _require(
            proposal["review_state"]
            == dict.fromkeys(("human_annotation", "independent_llm", "second_human"), "pending"),
            f"{sid}: draft reviews must remain pending",
        )
        errors = list(validator.iter_errors(new))
        _require(not errors, f"{sid}: invalid draft annotation: {errors[0].message if errors else ''}")
        for key in ("dept", "language", "derived_from", "answerable", "conflict"):
            if old is not None:
                _require(new.get(key) == old.get(key), f"{sid}: out-of-scope change to {key}")
        for value in [
            new["query"],
            new["notes"],
            *(
                g[field] if field == "key_text" else g["evidence_span"]["text"]
                for g in new["required_gold_evidence"]
                for field in ("key_text", "text")
            ),
        ]:
            _require(not find_pii(value), f"{sid}: proposed content requires a PII review")
        expected_groups = []
        for gold in new["required_gold_evidence"]:
            gid, span = gold["gold_id"], gold["evidence_span"]
            _require(gid.startswith(sid + "-g") and gid not in used, f"{sid}: duplicate or misbound gold id")
            used.add(gid)
            doc = docs[gold["source_hash"]]
            _require(doc["version_label"] == gold["version_label"], f"{gid}: source version mismatch")
            _require(doc["document_key"] == proposal["source_document_key"], f"{gid}: source scope mismatch")
            _require(doc["owner_dept"] == new["dept"], f"{gid}: source department mismatch")
            _require(1 <= gold["page"] <= doc["pages"], f"{gid}: invalid source page")
            _require(span["char_end"] - span["char_start"] == len(span["text"]), f"{gid}: span length mismatch")
            key = gold["key_text"]
            _require(key == normalize_text(key) and key in span["text"], f"{gid}: key not in normalized span")
            entry = mapped[gid]
            start, end = entry["key_start"], entry["key_end"]
            _require(end - start == len(key), f"{gid}: key interval length mismatch")
            _require(span["char_start"] <= start < end <= span["char_end"], f"{gid}: key outside evidence span")
            _require(
                span["text"][start - span["char_start"] : end - span["char_start"]] == key,
                f"{gid}: key offset mismatch",
            )
            if pages is not None:
                text = pages[(gold["source_hash"], gold["page"])]
                _require(text[span["char_start"] : span["char_end"]] == span["text"], f"{gid}: source span mismatch")
                _require(
                    text.find(key) == start and text.find(key, start + 1) < 0, f"{gid}: nonunique or misplaced key"
                )
            matches = sorted(
                c["chunk_id"]
                for c in chunks
                if c["source_hash"] == gold["source_hash"]
                and c["version_label"] == gold["version_label"]
                and any(
                    s["page"] == gold["page"] and s["char_start"] <= start and s["char_end"] >= end for s in c["spans"]
                )
            )
            _require(entry["chunk_ids"] == matches, f"{gid}: mapping does not match source spans")
            _require(entry["status"] == ("mapped" if matches else "unmappable"), f"{gid}: mapping status mismatch")
            expected_groups.append(matches)
        _require(
            proposal["required_gold_groups"] == expected_groups, f"{sid}: required evidence groups lost or flattened"
        )
        if sid.startswith("ms-"):
            golds = new["required_gold_evidence"]
            is_long = any(len(g["evidence_span"]["text"]) > 1500 for g in golds) or len({g["page"] for g in golds}) >= 2
            _require(("long_context" in new["slices"]) == is_long, f"{sid}: stale long_context label")
    _require(used == set(mapped), "mapping contains extra or missing golds")
    merged = {**baseline, **{sid: p["after"] for sid, p in by_id.items()}}
    queries = [normalize_text(s["query"]) for s in merged.values()]
    keys = {normalize_text(g["key_text"]) for s in merged.values() for g in s["required_gold_evidence"]}
    _require(len(queries) == len(set(queries)), "projected queries are not unique")
    _require(not set(queries) & keys, "projected query equals a gold key")
    for sid in by_id:
        sample = merged[sid]
        if parent_id := sample.get("derived_from"):
            parent = merged[parent_id]
            _require(_gold_without_ids(sample) == _gold_without_ids(parent), f"{sid}: twin gold differs from parent")
            _require(
                sample["slices"] == parent["slices"] and sample["dept"] == parent["dept"], f"{sid}: twin slices differ"
            )
    return {
        "proposals": len(proposals),
        "target_samples": len(required_ids),
        "linked_twins": len(linked - required_ids),
        "new_samples": len(new_ids),
        "gold_units": len(used),
        "mapping": dict(Counter(e["status"] for e in mapped.values())),
        "projected_long_context": sum("long_context" in s["slices"] for s in merged.values()),
        "changed_probe_imports": sorted(sid for sid in by_id if sid.startswith("pc-")),
    }


def check_revision(root: Path, directory: Path, *, with_pages: bool = False) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_text())
    _require(
        manifest["format"] in ("annotation-revision-v1", "annotation-revision-v2") and manifest["status"] == "draft",
        "draft manifest required",
    )
    _require(manifest["freeze_ready"] is False, "this edit bundle cannot declare review or freeze complete")
    required_files = {
        "proposals.json",
        "chunks.snapshot.json",
        "chunk_mapping.preview.json",
        "page_inputs.json",
        "corpus_edits.json",
        "document_verification.json",
    }
    _require(required_files <= manifest["files"].keys(), "revision manifest omits a required input digest")
    for name, digest in manifest["files"].items():
        _require(sha256_file(dataset_file(directory, name)) == digest, f"revision digest mismatch: {name}")
    base = dataset_file(root, manifest["base_dataset"]["path"])
    base_manifest = load_frozen_dataset(base, expected_id="precise_clause_main")
    _require(base_manifest["dataset_hash"] == manifest["base_dataset"]["dataset_hash"], "wrong base dataset")
    source = dataset_file(root, manifest["decision_source"]["path"])
    _require(sha256_file(source) == manifest["decision_source"]["sha256"], "decision source changed")
    work = json.loads(source.read_text())
    required = {s["sample_id"] for s in work["items"] if s["action"] == "versioned_gold_or_query_revision"}
    _require(set(manifest["target_sample_ids"]) == required, "target list differs from decisions")
    proposals = json.loads((directory / "proposals.json").read_text())
    rows = _by_id(read_rows(base / "samples.jsonl"), "sample_id")
    docs = _by_id(json.loads((base / "corpus.json").read_text())["documents"], "source_hash")
    snapshot = json.loads((directory / "chunks.snapshot.json").read_text())
    _require(snapshot["chunker_version"] == manifest["chunker_version"], "chunker version mismatch")
    _require(snapshot["normalization"] == base_manifest["normalization"], "normalization version mismatch")
    _require(
        snapshot["extraction"]
        == {k: base_manifest["extraction"][k] for k in ("extractor", "extractor_version", "params_hash")},
        "extraction mismatch",
    )
    page_map = None
    if with_pages:
        page_map = {}
        for item in json.loads((directory / "page_inputs.json").read_text()):
            path = dataset_file(root, item["path"])
            _require(sha256_file(path) == item["raw_sha256"], "source page hash mismatch")
            text = normalize_text(path.read_text())
            _require(
                hashlib.sha256(text.encode()).hexdigest() == item["normalized_sha256"], "normalized page hash mismatch"
            )
            page_map[(item["source_hash"], item["page"])] = text
    schema = json.loads((dataset_file(root, manifest["schema_dir"]) / "probe_sample.schema.json").read_text())
    info = check_annotations(
        proposals,
        rows,
        required,
        docs,
        schema,
        snapshot,
        json.loads((directory / "chunk_mapping.preview.json").read_text()),
        page_map,
        set(manifest.get("new_sample_ids", [])),
    )
    _require(
        set(manifest["linked_sample_ids"])
        == set(p["sample_id"] for p in proposals) - required - set(manifest.get("new_sample_ids", [])),
        "linked list mismatch",
    )
    approved = {s["sample_id"]: s["required_gold_groups"] for s in work["items"] if "required_gold_groups" in s}
    for proposal in proposals:
        origin = proposal["after"].get("derived_from", proposal["sample_id"])
        if origin in approved:
            _require(
                proposal["required_gold_groups"] == approved[origin],
                f"{origin}: existing joint-evidence decision changed",
            )
    for edit in json.loads((directory / "corpus_edits.json").read_text()):
        doc = docs[edit["source_hash"]]
        _require(edit["field"] == "title" and doc["document_key"] == edit["document_key"], "unsupported corpus edit")
        _require(doc["title"] == edit["before"] and bool(edit["after"]), "corpus title baseline changed")
    merged = {**rows, **{p["sample_id"]: p["after"] for p in proposals}}
    projected = projected_distribution(merged, docs, base_manifest["minimums"])
    return {
        "checks_passed": True,
        "status": "draft",
        "freeze_ready": False,
        "page_validation": "passed" if with_pages else "not_run",
        **info,
        "projected_distribution": projected,
        "limitations": [
            "Revised inputs need new annotation/review records; no old review was reused.",
            "Changed pc- imports require a new frozen probe before main-set import (PR-16).",
            f"Projected quota shortfalls: {projected['quota_shortfalls']}; satisfying counts does not complete review.",
            "This mapping preview is not a frozen dataset mapping or a new system-quality measurement.",
        ],
    }


def projected_distribution(samples: dict[str, dict], docs: dict[str, dict], minimums: dict) -> dict:
    """Count full projected inputs, not just edited rows; preserve existing minimums."""
    rows = list(samples.values())
    by_key = {d["document_key"]: d for d in docs.values()}
    counts: dict[str, Any] = {
        "samples": len(rows),
        "answerable": sum(s.get("answerable", True) for s in rows),
        "no_answer": sum(not s.get("answerable", True) for s in rows),
        "conflict": sum(bool(s.get("conflict")) for s in rows),
        "per_slice": dict(Counter(tag for s in rows for tag in s["slices"])),
        "per_dept": dict(Counter(s["dept"] for s in rows)),
    }
    languages = []
    for sample in rows:
        sources = {docs[g["source_hash"]]["language"] for g in sample["required_gold_evidence"]}
        if not sources:
            sources = {by_key[sample["abstention"]["scope_document_key"]]["language"]}
        languages.append(next(iter(sources)) if len(sources) == 1 else "mixed")
    counts["per_source_language"] = dict(Counter(languages))
    per_doc = Counter(
        h for s in rows if not s.get("derived_from") for h in {g["source_hash"] for g in s["required_gold_evidence"]}
    )
    _require(
        max(per_doc.values(), default=0) <= minimums["max_samples_per_document"],
        "projected document sample cap exceeded",
    )
    counts["max_non_derived_per_document"] = max(per_doc.values(), default=0)
    checks = {name: (counts[name], minimums[name + "_samples"]) for name in ("answerable", "no_answer", "conflict")}
    checks.update(
        {
            f"slice/{name}": (counts["per_slice"].get(name, 0), minimums["per_slice"])
            for name in (
                "drug_name_zh",
                "dose_unit",
                "negation",
                "time_window",
                "protocol_id",
                "mixed_zh_en",
                "version_conflict",
                "no_answer",
                "long_context",
            )
        }
    )
    checks.update(
        {f"dept/{name}": (counts["per_dept"].get(name, 0), minimums["per_dept"]) for name in ("MA", "PV", "CO")}
    )
    checks.update(
        {
            f"language/{name}": (counts["per_source_language"].get(name, 0), minimums[key])
            for name, key in (("zh-Hans", "zh_hans_samples"), ("zh-Hant", "zh_hant_samples"), ("en", "en_samples"))
        }
    )
    counts["quota_shortfalls"] = {
        name: {"actual": actual, "minimum": minimum} for name, (actual, minimum) in checks.items() if actual < minimum
    }
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--with-pages", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = check_revision(args.root, args.directory, with_pages=args.with_pages)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result = {"checks_passed": False, "error": str(exc)}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(raw)
    print(raw, end="")
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
