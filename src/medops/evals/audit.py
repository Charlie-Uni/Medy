"""Audit registered evaluation inputs without models, database writes or label changes.

python -m medops.evals.audit [--with-pages] [--out report.json]
Exit 0 means the mechanical checks passed, not that evaluation or release gates passed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from medops.evals.annotation_revision import check_confirmation, check_revision
from medops.evals.datasets import dataset_file, load_frozen_dataset, read_rows, sha256_file
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from medops.evals.source_semantics import load_source_contracts, validate_source_contracts


class LocalPages(PageTextProvider):
    def __init__(self, roots: list[Path]):
        self.providers = [PageTextProvider(root) for root in roots]

    def page_text(self, source_hash: str, page: int) -> str | None:
        for provider in self.providers:
            text = provider.page_text(source_hash, page)
            if text is not None:
                return text
        return None


def _unique(rows: list[dict[str, Any]], key: str) -> None:
    ids = [row[key] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {key}")


def _mapping(root: Path, entry: dict[str, Any], manifest: dict[str, Any], rows: list[dict[str, Any]]) -> dict:
    path = dataset_file(root, entry["chunk_mapping"]["path"])
    if sha256_file(path) != entry["chunk_mapping"]["sha256"]:
        raise ValueError("chunk mapping digest differs from catalog")
    mapping = json.loads(path.read_text())
    if any(mapping[k] != manifest[k] for k in ("dataset_hash", "dataset_version")):
        raise ValueError("chunk mapping is bound to another dataset")
    _unique(mapping["entries"], "gold_id")
    expected = {g["gold_id"] for row in rows for g in row.get("required_gold_evidence", [])}
    if expected != {g["gold_id"] for g in mapping["entries"]}:
        raise ValueError("chunk mapping gold ids differ from samples")
    return dict(Counter(g["status"] for g in mapping["entries"]))


def _samples(root: Path, entry: dict, manifest: dict, *, with_pages: bool, pages: LocalPages) -> tuple[dict, list]:
    directory = dataset_file(root, entry["path"])
    rows = read_rows(directory / "samples.jsonl")
    _unique(rows, "sample_id")
    if len(rows) != manifest["counts"]["samples"]:
        raise ValueError("sample count differs from manifest")
    schema_name = "safety_sample" if entry["role"] == "safety" else "probe_sample"
    schema = json.loads((dataset_file(root, entry["schema_dir"]) / f"{schema_name}.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for row in rows:
        errors = list(validator.iter_errors(row))
        if errors:
            raise ValueError(f"{row['sample_id']}: schema violation at {list(errors[0].path)}")
    info = {
        "samples": len(rows),
        "query_language": dict(sorted(Counter(row["language"] for row in rows).items())),
        "departments": dict(sorted(Counter(row["dept"] for row in rows).items())),
        "second_human_review": manifest.get("second_human_review", "not_declared"),
        "page_validation": "not_applicable" if entry["role"] == "safety" else "not_run",
    }
    if entry["role"] in ("main", "probe"):
        if with_pages:
            checked = ProbeSetValidator(dataset_file(root, entry["schema_dir"]), pages, approval_records_root=root)
            report = checked.validate(directory, mode="frozen")
            if not report.passed:
                details = "; ".join(f"{f.rule} {f.location}: {f.message}" for f in report.errors[:5])
                raise ValueError(f"frozen semantic validation: {details}")
            info["page_validation"] = "passed"
        info["source_language"] = manifest["counts"]["per_language"]
        info["answerable"] = sum(bool(row.get("answerable", True)) for row in rows)
        info["no_answer"] = len(rows) - info["answerable"]
        info["derived"] = sum(bool(row.get("derived_from")) for row in rows)
        info["required_gold_groups"] = dict(Counter(len(row["required_gold_evidence"]) for row in rows))
        for row in rows:
            if bool(row.get("answerable", True)) != bool(row["required_gold_evidence"]):
                raise ValueError(f"{row['sample_id']}: answerable and gold disagree")
        if entry.get("chunk_mapping"):
            info["mapping"] = _mapping(root, entry, manifest, rows)
    else:
        for field in ("category", "language", "dept"):
            if dict(Counter(row[field] for row in rows)) != manifest["counts"][f"by_{field}"]:
                raise ValueError(f"safety {field} counts differ from manifest")
        if {row["dataset_version"] for row in rows} != {manifest["dataset_version"]}:
            raise ValueError("safety samples carry a different dataset version")
        withdrawn = read_rows(directory / "withdrawn.jsonl")
        _unique(withdrawn, "sample_id")
        retired = {row["sample_id"] for row in withdrawn}
        active = {row["sample_id"] for row in rows}
        replacements = json.loads((directory / "withdrawn_manifest.json").read_text())
        if retired & active or retired != replacements.keys() or len(retired) != manifest["counts"]["withdrawn"]:
            raise ValueError("withdrawn sample ids or counts are inconsistent")
        if any(change["replaced_by"] not in active for change in replacements.values()):
            raise ValueError("a withdrawn sample has no active replacement")
        info["withdrawn"] = sorted(retired)
        info["confirmation"] = manifest["confirmation"]["confirmed_by"]
    return info, rows


def _replay(root: Path, entry: dict, manifest: dict) -> tuple[dict, list, list]:
    directory = dataset_file(root, entry["path"])
    main = read_rows(directory / "items.jsonl")
    safety = read_rows(directory / "safety_items.jsonl")
    _unique(main + safety, "replay_id")
    for name, rows in (("main", main), ("safety", safety)):
        _unique([row["source"] for row in rows], "sample_id")
        if len(rows) != manifest["counts"][name]["items"]:
            raise ValueError(f"replay {name} count differs from manifest")
        if dict(Counter(row["label"] for row in rows)) != manifest["counts"][name]["by_label"]:
            raise ValueError(f"replay {name} labels differ from manifest")
        source = manifest["sources"][name]
        if {row["source"]["dataset"] for row in rows} != {source["dataset_version"]}:
            raise ValueError(f"replay {name} source version differs from manifest")
        run_rows = dataset_file(root, source["run"]) / "rows.jsonl"
        if sha256_file(run_rows) != source["rows_sha256"]:
            raise ValueError(f"replay {name} source run hash mismatch")
    subset = json.loads((directory / "subset.json").read_text())
    ids = subset["replay_ids"]
    by_id = {row["replay_id"]: row for row in main}
    if len(ids) != len(set(ids)) or len(ids) != subset["size"] or len(ids) != manifest["subset"]["size"]:
        raise ValueError("replay screening subset size or uniqueness mismatch")
    if any(sid not in by_id or by_id[sid]["derived"] for sid in ids):
        raise ValueError("replay subset has missing or derived samples")
    return (
        {"main": len(main), "safety": len(safety), "screening_subset": len(ids), "sources": manifest["sources"]},
        main,
        safety,
    )


def audit(root: Path, catalog: dict[str, Any], *, with_pages: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "catalog_version": catalog["catalog_version"],
        "checks_passed": False,
        "datasets": [],
        "findings": [],
    }
    loaded: dict[str, tuple[dict, list]] = {}
    pages = LocalPages([dataset_file(root, path) for path in catalog["page_roots"]])
    roles = [entry["role"] for entry in catalog["datasets"]]
    if len(roles) != len(set(roles)) or set(roles) != {"probe", "main", "safety", "replay"}:
        raise ValueError("catalog must contain exactly one probe, main, safety and replay entry")
    for entry in catalog["datasets"]:
        info = {"role": entry["role"], "path": entry["path"], "integrity": "failed"}
        try:
            directory = dataset_file(root, entry["path"])
            manifest = load_frozen_dataset(directory, expected_id=entry["dataset_id"])
            if sha256_file(directory / "manifest.json") != entry["manifest_sha256"]:
                raise ValueError("manifest metadata differs from the pinned catalog")
            if any(manifest[key] != entry[key] for key in ("dataset_version", "dataset_hash")):
                raise ValueError("dataset version/hash differs from the catalog")
            if entry["role"] == "replay":
                details, rows, safety_rows = _replay(root, entry, manifest)
                loaded["replay_safety"] = manifest, safety_rows
            else:
                details, rows = _samples(root, entry, manifest, with_pages=with_pages, pages=pages)
            info.update(
                details,
                integrity="passed",
                dataset_version=manifest["dataset_version"],
                dataset_hash=manifest["dataset_hash"],
            )
            loaded[entry["role"]] = manifest, rows
            if details.get("mapping", {}).get("unmappable"):
                report["findings"].append(
                    {
                        "level": "warning",
                        "code": "unmappable_gold",
                        "detail": f"{details['mapping']['unmappable']} gold groups remain unmappable; keep them as misses in the recall denominator.",
                    }
                )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["findings"].append(
                {"level": "error", "code": "dataset_check", "role": entry["role"], "detail": str(exc)}
            )
        report["datasets"].append(info)
    if catalog.get("review_worklist") and "main" in loaded:
        try:
            record = catalog["review_worklist"]
            path = dataset_file(root, record["path"])
            if sha256_file(path) != record["sha256"]:
                raise ValueError("review worklist differs from catalog")
            worklist = json.loads(path.read_text())
            if sha256_file(dataset_file(root, worklist["source"])) != worklist["source_sha256"]:
                raise ValueError("review decision source changed; reconcile the worklist")
            _unique(worklist["items"], "sample_id")
            current_ids = {row["sample_id"] for row in loaded["main"][1]}
            if any(row["sample_id"] not in current_ids for row in worklist["items"]):
                raise ValueError("review worklist references a missing main sample")
            if (
                len(worklist["items"]) != worklist["unique_samples"]
                or sum(len(row["decision_records"]) for row in worklist["items"]) != worklist["source_rows"]
            ):
                raise ValueError("review worklist counts differ from records")
            report["review_actions"] = dict(Counter(row["action"] for row in worklist["items"]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["findings"].append({"level": "error", "code": "review_worklist", "detail": str(exc)})
    if catalog.get("source_contracts") and "main" in loaded:
        try:
            record = catalog["source_contracts"]
            path = dataset_file(root, record["path"])
            if sha256_file(path) != record["sha256"]:
                raise ValueError("source contracts differ from catalog")
            main_entry = next(item for item in catalog["datasets"] if item["role"] == "main")
            main_dir = dataset_file(root, main_entry["path"])
            corpus = json.loads((main_dir / "corpus.json").read_text(encoding="utf-8"))
            report["source_contracts"] = validate_source_contracts(
                load_source_contracts(path), loaded["main"][0], loaded["main"][1], corpus
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["findings"].append({"level": "error", "code": "source_contracts", "detail": str(exc)})
    if "safety" in loaded and "replay_safety" in loaded:
        current, rows = loaded["safety"]
        old, old_rows = loaded["replay_safety"]
        if old["sources"]["safety"]["dataset_version"] != current["dataset_version"]:
            active = {row["sample_id"]: row for row in rows}
            missing = sorted(row["source"]["sample_id"] for row in old_rows if row["source"]["sample_id"] not in active)
            report["findings"].append(
                {
                    "level": "warning",
                    "code": "replay_uses_old_safety",
                    "detail": "Historical replay is intact but cannot stand in for the current frozen safety set.",
                    "retired_sample_ids": missing,
                }
            )
    report["findings"].append(
        {
            "level": "warning",
            "code": "independent_review_pending",
            "detail": "Main and safety remain provisional. Mechanical success is not independent human review or release acceptance.",
        }
    )
    report["findings"].append(
        {
            "level": "warning",
            "code": "no_unseen_holdout",
            "detail": "Registered sets have been used for development/regression; no new unseen holdout is registered.",
        }
    )
    for entry in catalog.get("annotation_drafts", []):
        try:
            directory = dataset_file(root, entry["path"])
            if sha256_file(directory / "manifest.json") != entry["manifest_sha256"]:
                raise ValueError("annotation revision manifest differs from catalog")
            revision = check_revision(root, directory, with_pages=with_pages)
            if confirmation := entry.get("human_confirmation"):
                path = dataset_file(root, confirmation["path"])
                if sha256_file(path) != confirmation["sha256"]:
                    raise ValueError("human confirmation differs from catalog")
                revision["human_annotation"] = check_confirmation(directory, path)
            annotation = {"path": entry["path"], "status": entry.get("status", "draft"), **revision}
            if applied := entry.get("applied_to"):
                main_manifest = loaded["main"][0]
                if any(main_manifest[key] != applied[key] for key in ("dataset_version", "dataset_hash")):
                    raise ValueError("annotation revision applied_to differs from the current main set")
                if dataset_file(root, applied["path"]) != dataset_file(
                    root, next(item["path"] for item in catalog["datasets"] if item["role"] == "main")
                ):
                    raise ValueError("annotation revision applied_to path differs from the current main set")
                annotation["applied_to"] = applied
            else:
                report["findings"].append(
                    {
                        "level": "warning",
                        "code": "annotation_draft_pending",
                        "detail": f"{revision['proposals']} revised annotations remain unapplied to the current main set; verify recorded review status and probe lineage before main versioning; projected long_context={revision['projected_long_context']} (minimum 20).",
                    }
                )
            report.setdefault("annotation_drafts", []).append(annotation)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["findings"].append({"level": "error", "code": "annotation_revision", "detail": str(exc)})
    report["checks_passed"] = not any(f["level"] == "error" for f in report["findings"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--catalog", type=Path, default=Path("evals/dataset_catalog.json"))
    parser.add_argument("--with-pages", action="store_true", help="also run frozen probe/main semantic and page checks")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", action="store_true", help="print only check status and outstanding findings")
    args = parser.parse_args()
    catalog = json.loads((args.root / args.catalog).read_text(encoding="utf-8"))
    result = audit(args.root, catalog, with_pages=args.with_pages)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    if args.summary:
        print(f"evaluation inputs: {'PASS' if result['checks_passed'] else 'FAIL'}; {len(result['datasets'])} datasets")
        for finding in result["findings"]:
            print(f"[{finding['level']}] {finding['code']}: {finding['detail']}")
    else:
        print(output, end="")
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
