"""Assemble a probe successor from a frozen probe and a confirmed annotation revision.

The command reuses unchanged review evidence, appends actual targeted review calls for
changed ``pc-*`` samples, and snapshots any historical mixed-chunk input packs needed
to reconstruct still-current verdicts. It makes no model calls and never overwrites a
frozen target.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_json
from medops.evals.annotation_revision import check_confirmation

REPO = Path(__file__).resolve().parents[4]
BATCHES = ("MA", "PV", "CO", "EN")
SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
DEPTS = ["MA", "PV", "CO"]
LANGS = ["zh-Hans", "zh-Hant", "en", "mixed"]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verdicts(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    result = {row["sample_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate verdict sample_id: {path}")
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def find_archived_input(input_path: str, roots: list[Path]) -> Path:
    candidate = Path(input_path)
    require(not candidate.is_absolute() and ".." not in candidate.parts, "unsafe archived input path")
    matches = [root / candidate for root in roots if (root / candidate).is_file()]
    require(len(matches) == 1, f"archived input must exist in exactly one source root: {input_path}")
    return matches[0]


def review_block(base_sample: dict[str, Any], second: dict[str, Any], prompt_hash: str) -> dict[str, Any]:
    return {
        "annotator": copy.deepcopy(base_sample["review"]["annotator"]),
        "second_reviewer": {
            **{key: second[key] for key in ("id", "kind", "model", "model_version")},
            "prompt_hash": prompt_hash,
        },
        "status": "agreed",
        "resolution_note": None,
    }


def sample_language(sample: dict[str, Any], documents: dict[str, dict[str, Any]]) -> str:
    languages = {documents[gold["source_hash"]]["language"] for gold in sample["required_gold_evidence"]}
    return next(iter(languages)) if len(languages) == 1 else "mixed"


def latest_verdicts(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for sid, binding in run["latest"].items():
        chunk = run["chunks"][binding["chunk_index"]]
        matches = [row for row in chunk["verdicts"] if row["sample_id"] == sid]
        require(len(matches) == 1, f"{sid}: latest invocation does not contain one verdict")
        result[sid] = matches[0]
    return result


def annotate_prompt(run: dict[str, Any]) -> dict[str, Any]:
    run = copy.deepcopy(run)
    prompt_hash = run["review_prompt_sha256"]
    for chunk in run["chunks"]:
        observed = chunk.setdefault("review_prompt_sha256", prompt_hash)
        require(
            isinstance(observed, str) and len(observed) == 64 and set(observed) <= set("0123456789abcdef"),
            "source run contains an invalid per-invocation prompt hash",
        )
    return run


def assemble(args: argparse.Namespace) -> dict[str, Any]:
    base, revision, target, prompt = (path.resolve() for path in (args.base, args.revision, args.out, args.prompt))
    require(not (target / "SHA256SUMS").exists(), "refusing to overwrite a frozen target")
    confirmation = args.confirmation.resolve()
    confirmed = check_confirmation(revision, confirmation)

    base_manifest = json.loads((base / "manifest.json").read_text())
    require(
        base_manifest["dataset_id"] == "precise_clause_probe" and base_manifest["status"] == "frozen",
        "base must be a frozen probe",
    )
    require(args.version != base_manifest["dataset_version"], "successor version must differ from base")
    base_samples = {row["sample_id"]: row for row in read_jsonl(base / "samples.jsonl")}
    proposals = [
        row for row in json.loads((revision / "proposals.json").read_text()) if row["sample_id"].startswith("pc-")
    ]
    changed_ids = {row["sample_id"] for row in proposals}
    require(bool(changed_ids) and changed_ids <= base_samples.keys(), "revision must change existing probe samples")

    base_second = next(
        row for row in base_manifest["reviewers"] if row.get("role") == "second_reviewer" and row.get("kind") == "llm"
    )
    prompt_raw = prompt.read_bytes()
    current_prompt_hash = sha(prompt_raw)
    old_prompt_raw = (base / "review_prompt.md").read_bytes()
    old_prompt_hash = sha(old_prompt_raw)
    require(old_prompt_hash != current_prompt_hash, "successor prompt must differ from the archived base prompt")
    second = {**base_second, "prompt_hash": current_prompt_hash}

    merged_runs: dict[str, dict[str, Any]] = {}
    merged_verdicts: dict[str, dict[str, Any]] = {}
    for batch in BATCHES:
        run = annotate_prompt(json.loads((base / f"review_evidence/run_{batch}.json").read_text()))
        merged_runs[batch] = run
        merged_verdicts.update(verdicts(base / f"review_evidence/verdicts_{batch}.jsonl"))

    reviewed_ids: set[str] = set()
    source_provenance = []
    for run_path in [path.resolve() for path in args.supplemental_run]:
        run = annotate_prompt(json.loads(run_path.read_text()))
        require(run["active_review"] is None, f"supplemental review is unfinished: {run_path}")
        batch = run["batch"]
        require(batch in BATCHES, f"unknown supplemental batch: {batch}")
        require(
            run["model"] == second["model"]
            and run["reasoning_effort_requested"] == "high"
            and run["review_prompt_sha256"] == current_prompt_hash,
            f"supplemental model, effort or prompt mismatch: {run_path}",
        )
        verdict_path = run_path.with_name(f"verdicts_{batch}.jsonl")
        current = latest_verdicts(run)
        require(current == verdicts(verdict_path), f"supplemental verdict mirror mismatch: {run_path}")
        ids = set(current)
        require(
            bool(ids) and ids <= changed_ids and ids.isdisjoint(reviewed_ids),
            f"unexpected or duplicate supplemental IDs: {run_path}",
        )
        require(
            all(row["verdict"] == "agree" for row in current.values()), "changed samples must agree before assembly"
        )
        reviewed_ids.update(ids)

        merged = merged_runs[batch]
        offset = len(merged["chunks"])
        merged["chunks"].extend(copy.deepcopy(run["chunks"]))
        merged["sample_input_sha256"].update({sid: run["sample_input_sha256"][sid] for sid in ids})
        for sid, binding in run["latest"].items():
            updated = copy.deepcopy(binding)
            updated["chunk_index"] += offset
            merged["latest"][sid] = updated
        merged["review_prompt_sha256"] = current_prompt_hash
        merged_verdicts.update(current)
        source_provenance.append(
            {
                "run": relative(run_path),
                "run_sha256": sha(run_path.read_bytes()),
                "verdicts": relative(verdict_path),
                "verdicts_sha256": sha(verdict_path.read_bytes()),
                "sample_ids": sorted(ids),
                "review_prompt_sha256": run["review_prompt_sha256"],
            }
        )
    require(reviewed_ids == changed_ids, "supplemental review coverage differs from changed probe samples")

    samples = copy.deepcopy(base_samples)
    for proposal in proposals:
        sid = proposal["sample_id"]
        projected = {key: value for key, value in proposal["after"].items() if key != "drafted_by"}
        projected["review"] = review_block(base_samples[sid], second, current_prompt_hash)
        samples[sid] = projected
    ordered_samples = [samples[sid] for sid in sorted(samples)]

    corpus = json.loads((base / "corpus.json").read_text())
    corpus["dataset_version"] = args.version
    pii = json.loads((base / "pii_exceptions.json").read_text())
    pii["dataset_version"] = args.version
    documents = {row["source_hash"]: row for row in corpus["documents"]}

    evidence: dict[str, bytes] = {}
    all_chunks: list[dict[str, Any]] = []
    base_resolutions = json.loads((base / "review_evidence/resolutions.json").read_text())
    require(not (changed_ids & base_resolutions.keys()), "changed probe sample has a retained base dispute")
    for batch in BATCHES:
        run = merged_runs[batch]
        all_chunks.extend(run["chunks"])
        evidence[f"run_{batch}.json"] = (json.dumps(run, ensure_ascii=False, indent=2) + "\n").encode()
        group = sorted(
            sid for sid, sample in samples.items() if ("EN" if sample.get("derived_from") else sample["dept"]) == batch
        )
        evidence[f"verdicts_{batch}.jsonl"] = "".join(
            json.dumps(merged_verdicts[sid], ensure_ascii=False) + "\n" for sid in group
        ).encode()

    evidence["resolutions.json"] = (canonical_json(base_resolutions) + "\n").encode()
    runtime = json.loads((base / "review_evidence/reviewer_runtime_metadata.json").read_text())
    runtime.update(
        cli_versions=sorted({chunk["cli_version"] for chunk in all_chunks}),
        system_prompt_sha256=sorted({chunk["system_prompt_sha256"] for chunk in all_chunks}),
        first_started_at=min(chunk["started_at"] for chunk in all_chunks),
        last_finished_at=max(chunk["finished_at"] for chunk in all_chunks),
        observed_successful_calls=len(all_chunks),
        current_reviewed_samples=len(ordered_samples),
        total_cost_usd=round(sum(float(chunk.get("cost_usd") or 0) for chunk in all_chunks), 4),
        review_prompt_sha256s=sorted({chunk["review_prompt_sha256"] for chunk in all_chunks}),
    )
    evidence["reviewer_runtime_metadata.json"] = (canonical_json(runtime) + "\n").encode()

    archive_roots = [path.resolve() for path in args.archive_root]
    archived: dict[str, bytes] = {}
    for run in merged_runs.values():
        for binding in run["latest"].values():
            chunk = run["chunks"][binding["chunk_index"]]
            current_hashes = {member: run["sample_input_sha256"][member] for member in chunk["sample_ids"]}
            if chunk["sample_input_sha256"] == current_hashes:
                continue
            source = find_archived_input(chunk["input_path"], archive_roots)
            artifact_path = f"review_evidence/{chunk['input_path']}"
            raw = source.read_bytes()
            previous = archived.setdefault(artifact_path, raw)
            require(previous == raw, f"conflicting archived input bytes: {artifact_path}")

    target.mkdir(parents=True, exist_ok=True)
    evidence_dir = target / "review_evidence"
    evidence_dir.mkdir(exist_ok=True)
    for name, raw in evidence.items():
        (evidence_dir / name).write_bytes(raw)
    for artifact_path, raw in archived.items():
        path = target / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (target / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n")
    (target / "pii_exceptions.json").write_text(canonical_json(pii) + "\n")
    (target / "review_prompt.md").write_bytes(prompt_raw)
    (target / "samples.jsonl").write_text("".join(canonical_json(row) + "\n" for row in ordered_samples))

    revision_provenance = {
        "format": "probe-successor-revision-provenance-v1",
        "base": {"path": relative(base), "dataset_hash": base_manifest["dataset_hash"]},
        "annotation_revision": {
            "path": relative(revision),
            "manifest_sha256": sha((revision / "manifest.json").read_bytes()),
            "proposals_sha256": sha((revision / "proposals.json").read_bytes()),
            "confirmation_path": relative(confirmation),
            "confirmation_sha256": sha(confirmation.read_bytes()),
        },
        "supplemental_reviews": source_provenance,
        "human_confirmation": confirmed,
        "independent_second_human": False,
        "archived_mixed_chunk_inputs": [{"path": path, "sha256": sha(raw)} for path, raw in sorted(archived.items())],
        "note": (
            "The project owner confirmed the exact revision; the stable dataset role annotator-01 is retained "
            "because this project has one human participant. This is not a second-human review."
        ),
    }
    legacy_prompt_path = f"review_evidence/review_prompts/review_prompt_{old_prompt_hash}.md"
    prompt_artifact = {legacy_prompt_path: old_prompt_raw}
    for artifact_path, raw in prompt_artifact.items():
        path = target / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    revision_provenance["archived_review_prompts"] = [
        {"path": path, "sha256": sha(raw)} for path, raw in sorted(prompt_artifact.items())
    ]
    (target / "revision_provenance.json").write_text(canonical_json(revision_provenance) + "\n")

    slice_counts = Counter(sl for row in ordered_samples for sl in row["slices"])
    dept_counts = Counter(row["dept"] for row in ordered_samples)
    language_counts = Counter(sample_language(row, documents) for row in ordered_samples)
    counts = {
        "samples": len(ordered_samples),
        "documents": len(documents),
        "per_slice": {name: slice_counts[name] for name in SLICES},
        "per_dept": {name: dept_counts[name] for name in DEPTS},
        "per_language": {name: language_counts[name] for name in LANGS},
    }
    files = ["corpus.json", "pii_exceptions.json", "revision_provenance.json", "review_prompt.md", "samples.jsonl"]
    manifest = copy.deepcopy(base_manifest)
    manifest.update(
        dataset_version=args.version,
        status="draft",
        created_at=args.created_at,
        frozen_at=None,
        purpose=(
            f"精确条款探针集 {args.version}：继承 {base_manifest['dataset_version']} 的 107 条样本，"
            "修正无法映射的证据单元；变化样本已完成同一固定模型的定向独立复核。"
        ),
        counts=counts,
        files=[{"path": name, "sha256": sha((target / name).read_bytes())} for name in files],
        dataset_hash=None,
        supersedes=base_manifest["dataset_version"],
        change_reason=(
            f"项目所有者确认 {relative(revision)} 的 {', '.join(sorted(changed_ids))} 修订；"
            f"{len(changed_ids)} 条定向 LLM 复核均 agree，历史输入与提示按哈希归档。"
        ),
    )
    for row in manifest["reviewers"]:
        if row.get("role") == "second_reviewer":
            row.update(second)
    artifacts = {f"review_evidence/{name}": raw for name, raw in evidence.items()} | archived | prompt_artifact
    manifest["review_provenance"]["artifacts"] = [
        {"path": path, "sha256": sha(raw)} for path, raw in sorted(artifacts.items())
    ]
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "status": "draft",
        "dataset_version": args.version,
        "samples": len(ordered_samples),
        "changed_sample_ids": sorted(changed_ids),
        "archived_mixed_chunk_inputs": sorted(archived),
        "model_calls": 0,
        "target": relative(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--supplemental-run", type=Path, action="append", required=True)
    parser.add_argument("--archive-root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--created-at", default=dt.date.today().isoformat())
    args = parser.parse_args()
    print(json.dumps(assemble(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
