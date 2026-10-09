"""Assemble a provisional main-set successor without making model calls.

The assembler imports a frozen successor probe, applies a confirmed annotation
revision, merges the exact supplemental review runs that cover every changed
``ms-*`` reviewer input, and archives historical mixed inputs and prompt versions
needed to reconstruct retained review opinions.
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

from pack_review import pack

from medops.core.canonical import canonical_json
from medops.evals.annotation_revision import check_confirmation, check_revision
from medops.evals.probe.review_provenance import batch_of

REPO = Path(__file__).resolve().parents[3]
BATCHES = ("MA", "PV", "CO", "EN", "NA")
SLICES = [
    "drug_name_zh",
    "dose_unit",
    "negation",
    "time_window",
    "protocol_id",
    "mixed_zh_en",
    "version_conflict",
    "no_answer",
    "long_context",
]
DEPTS = ("MA", "PV", "CO")
LANGS = ("zh-Hans", "zh-Hant", "en", "mixed")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(value: Any) -> str:
    return sha(canonical_json(value).encode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verdicts(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    result = {row["sample_id"]: row for row in rows}
    require(len(result) == len(rows), f"duplicate verdict sample_id: {path}")
    return result


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def latest_verdicts(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for sid, binding in run["latest"].items():
        chunk = run["chunks"][binding["chunk_index"]]
        matches = [row for row in chunk["verdicts"] if row["sample_id"] == sid]
        require(len(matches) == 1, f"{sid}: latest invocation does not contain one verdict")
        result[sid] = matches[0]
    return result


def find_archived_input(input_path: str, roots: list[Path]) -> bytes:
    candidate = Path(input_path)
    require(not candidate.is_absolute() and ".." not in candidate.parts, "unsafe archived input path")
    matches = [(root / candidate).read_bytes() for root in roots if (root / candidate).is_file()]
    require(matches, f"archived input is missing: {input_path}")
    require(all(raw == matches[0] for raw in matches), f"conflicting archived input bytes: {input_path}")
    return matches[0]


def sample_language(
    sample: dict[str, Any], by_hash: dict[str, dict[str, Any]], by_key: dict[str, dict[str, Any]]
) -> str:
    if sample.get("answerable", True) is False:
        return by_key[sample["abstention"]["scope_document_key"]]["language"]
    languages = {by_hash[gold["source_hash"]]["language"] for gold in sample["required_gold_evidence"]}
    return next(iter(languages)) if len(languages) == 1 else "mixed"


def second_reviewer(base_manifest: dict[str, Any], prompt_hash: str) -> dict[str, Any]:
    old = next(
        row for row in base_manifest["reviewers"] if row.get("role") == "second_reviewer" and row.get("kind") == "llm"
    )
    return {**old, "prompt_hash": prompt_hash}


def review_block(
    base_sample: dict[str, Any] | None,
    second: dict[str, Any],
    prompt_hash: str,
    verdict: dict[str, Any],
    resolution: dict[str, Any] | None,
) -> dict[str, Any]:
    annotator = (
        copy.deepcopy(base_sample["review"]["annotator"])
        if base_sample and base_sample.get("review")
        else {"id": "annotator-01", "kind": "human"}
    )
    reviewer = {key: second[key] for key in ("id", "kind", "model", "model_version")}
    reviewer["prompt_hash"] = prompt_hash
    if verdict["verdict"] == "agree":
        require(resolution is None, f"{verdict['sample_id']}: agree verdict has an unnecessary resolution")
        return {"annotator": annotator, "second_reviewer": reviewer, "status": "agreed", "resolution_note": None}
    require(resolution is not None, f"{verdict['sample_id']}: unresolved current dispute")
    require(not resolution.get("accepted"), f"{verdict['sample_id']}: accepted dispute requires another review")
    return {
        "annotator": annotator,
        "second_reviewer": reviewer,
        "status": "disputed_resolved",
        "resolution_note": resolution["resolution_note"],
    }


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
    base, probe, revision, confirmation, target, prompt = (
        path.resolve() for path in (args.base, args.probe, args.revision, args.confirmation, args.out, args.prompt)
    )
    require(not (target / "SHA256SUMS").exists(), "refusing to overwrite a frozen target")
    check_revision(REPO, revision, with_pages=True)
    confirmed = check_confirmation(revision, confirmation)
    revision_manifest = json.loads((revision / "manifest.json").read_text(encoding="utf-8"))

    base_manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    probe_manifest = json.loads((probe / "manifest.json").read_text(encoding="utf-8"))
    require(base_manifest["dataset_id"] == "precise_clause_main" and base_manifest["status"] == "frozen", "bad base")
    require(
        probe_manifest["dataset_id"] == "precise_clause_probe" and probe_manifest["status"] == "frozen", "bad probe"
    )
    require(
        revision_manifest["base_dataset"]["dataset_hash"] == base_manifest["dataset_hash"],
        "revision is not based on the supplied frozen main set",
    )

    base_samples = {row["sample_id"]: row for row in read_jsonl(base / "samples.jsonl")}
    projected = copy.deepcopy(base_samples)
    proposal_ids = set()
    for proposal in json.loads((revision / "proposals.json").read_text(encoding="utf-8")):
        if proposal["sample_id"].startswith("ms-"):
            proposal_ids.add(proposal["sample_id"])
            projected[proposal["sample_id"]] = copy.deepcopy(proposal["after"])

    imported = read_jsonl(probe / "samples.jsonl")
    require(all(row["sample_id"].startswith("pc-") for row in imported), "probe contains non-pc sample")
    require(len({row["sample_id"] for row in imported}) == len(imported), "duplicate probe sample IDs")
    for sid in [sid for sid in projected if sid.startswith("pc-")]:
        del projected[sid]
    projected.update({row["sample_id"]: copy.deepcopy(row) for row in imported})

    corpus = copy.deepcopy(json.loads((base / "corpus.json").read_text(encoding="utf-8")))
    corpus["dataset_version"] = args.version
    by_key = {row["document_key"]: row for row in corpus["documents"]}
    for edit in json.loads((revision / "corpus_edits.json").read_text(encoding="utf-8")):
        document = by_key[edit["document_key"]]
        require(document[edit["field"]] == edit["before"], f"stale corpus edit: {edit['document_key']}")
        document[edit["field"]] = edit["after"]
    by_hash = {row["source_hash"]: row for row in corpus["documents"]}

    local_samples = [sample for sid, sample in sorted(projected.items()) if sid.startswith("ms-")]
    records = {record["sample_id"]: record for record in pack(local_samples, by_key, projected)}
    current_hashes = {sid: digest(record) for sid, record in records.items()}

    prompt_raw = prompt.read_bytes()
    current_prompt_hash = sha(prompt_raw)
    second = second_reviewer(base_manifest, current_prompt_hash)
    old_prompt_raw = (base / "review_prompt.md").read_bytes()
    old_prompt_hash = sha(old_prompt_raw)

    source_runs = [path.resolve() for path in args.supplemental_run]
    resolutions = json.loads(args.resolution_file.resolve().read_text(encoding="utf-8"))
    base_resolutions = json.loads((base / "review_evidence/resolutions.json").read_text(encoding="utf-8"))
    merged_runs: dict[str, dict[str, Any]] = {}
    merged_verdicts: dict[str, dict[str, Any]] = {}
    source_provenance = []
    for batch in BATCHES:
        run = annotate_prompt(json.loads((base / f"review_evidence/run_{batch}.json").read_text(encoding="utf-8")))
        merged_runs[batch] = run
        merged_verdicts.update(verdicts(base / f"review_evidence/verdicts_{batch}.jsonl"))

    for run_path in source_runs:
        run = annotate_prompt(json.loads(run_path.read_text(encoding="utf-8")))
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
        current_source_verdicts = latest_verdicts(run)
        require(current_source_verdicts == verdicts(verdict_path), f"supplemental verdict mirror mismatch: {run_path}")
        source_ids = set(current_source_verdicts)
        merged = merged_runs[batch]
        offset = len(merged["chunks"])
        merged["chunks"].extend(copy.deepcopy(run["chunks"]))
        merged["sample_input_sha256"].update({sid: run["sample_input_sha256"][sid] for sid in source_ids})
        for sid, binding in run["latest"].items():
            updated = copy.deepcopy(binding)
            updated["chunk_index"] += offset
            merged["latest"][sid] = updated
        merged["review_prompt_sha256"] = current_prompt_hash
        merged_verdicts.update(current_source_verdicts)
        source_provenance.append(
            {
                "run": relative(run_path),
                "run_sha256": sha(run_path.read_bytes()),
                "verdicts": relative(verdict_path),
                "verdicts_sha256": sha(verdict_path.read_bytes()),
                "sample_ids": sorted(source_ids),
                "review_prompt_sha256": run["review_prompt_sha256"],
            }
        )

    base_records = pack(
        [sample for sid, sample in sorted(base_samples.items()) if sid.startswith("ms-")],
        {row["document_key"]: row for row in json.loads((base / "corpus.json").read_text())["documents"]},
        base_samples,
    )
    base_hashes = {record["sample_id"]: digest(record) for record in base_records}
    changed_ids = {sid for sid, value in current_hashes.items() if base_hashes.get(sid) != value}
    require(changed_ids, "successor has no changed local review inputs")
    dropped = set(base_manifest.get("dropped_after_review") or {})

    for batch, run in merged_runs.items():
        group = {sid for sid, sample in projected.items() if sid.startswith("ms-") and batch_of(sample) == batch}
        live_hashes = {sid: value for sid, value in run["sample_input_sha256"].items() if sid not in dropped}
        require(set(live_hashes) == group, f"{batch}: merged review coverage mismatch")
        require(
            live_hashes == {sid: current_hashes[sid] for sid in group},
            f"{batch}: changed reviewer inputs lack a matching supplemental review",
        )
        require(set(run["latest"]) - dropped == group, f"{batch}: latest coverage mismatch")
        require(set(merged_verdicts) >= group, f"{batch}: verdict coverage mismatch")

    current_resolutions = {sid: value for sid, value in base_resolutions.items() if sid not in changed_ids}
    require(not (current_resolutions.keys() & resolutions.keys()), "duplicate successor resolution")
    current_resolutions.update(resolutions)
    disputed = set()
    for sid in sorted(current_hashes):
        batch = batch_of(projected[sid])
        run = merged_runs[batch]
        binding = run["latest"][sid]
        chunk = run["chunks"][binding["chunk_index"]]
        verdict = merged_verdicts[sid]
        prompt_hash = chunk["review_prompt_sha256"]
        resolution = current_resolutions.get(sid)
        if verdict["verdict"] == "dispute":
            disputed.add(sid)
            require(resolution is not None, f"{sid}: dispute lacks a resolution")
            require(
                resolution["sample_input_sha256"] == binding["sample_input_sha256"]
                and resolution["verdict_sha256"] == digest(verdict),
                f"{sid}: stale successor resolution",
            )
            require(
                set(resolution["issue_scope"]) == {key for key, value in verdict["items"].items() if value == "issue"},
                f"{sid}: resolution issue scope mismatch",
            )
        projected[sid]["review"] = review_block(base_samples.get(sid), second, prompt_hash, verdict, resolution)
    require(set(current_resolutions) == disputed, "resolutions must cover exactly the current disputes")

    ordered_samples = [projected[sid] for sid in sorted(projected)]
    require(
        len(ordered_samples) == len({row["sample_id"] for row in ordered_samples}), "duplicate assembled sample IDs"
    )

    archive_roots = [path.resolve() for path in args.archive_root]
    archived_inputs: dict[str, bytes] = {}
    all_chunks = []
    evidence: dict[str, bytes] = {}
    for batch, run in merged_runs.items():
        for sid, binding in run["latest"].items():
            if sid in dropped:
                continue
            chunk = run["chunks"][binding["chunk_index"]]
            current = {member: current_hashes[member] for member in chunk["sample_ids"]}
            if chunk["sample_input_sha256"] == current:
                continue
            input_path = chunk.get("input_path")
            require(isinstance(input_path, str), f"{batch}: historical mixed chunk lacks input_path")
            raw = find_archived_input(input_path, archive_roots)
            artifact_path = f"review_evidence/{input_path}"
            previous = archived_inputs.setdefault(artifact_path, raw)
            require(previous == raw, f"conflicting archive bytes: {artifact_path}")
        all_chunks.extend(run["chunks"])
        evidence[f"run_{batch}.json"] = (json.dumps(run, ensure_ascii=False, indent=2) + "\n").encode()
        group = sorted(sid for sid, sample in projected.items() if sid.startswith("ms-") and batch_of(sample) == batch)
        evidence[f"verdicts_{batch}.jsonl"] = "".join(
            json.dumps(merged_verdicts[sid], ensure_ascii=False) + "\n" for sid in group
        ).encode()

    evidence["resolutions.json"] = (canonical_json(current_resolutions) + "\n").encode()
    runtime = json.loads((base / "review_evidence/reviewer_runtime_metadata.json").read_text(encoding="utf-8"))
    runtime.update(
        model=second["model"],
        backend_model_version=second["model_version"],
        cli_versions=sorted({chunk["cli_version"] for chunk in all_chunks}),
        system_prompt_sha256=sorted({chunk["system_prompt_sha256"] for chunk in all_chunks}),
        review_prompt_sha256s=sorted({chunk["review_prompt_sha256"] for chunk in all_chunks}),
        first_started_at=min(chunk["started_at"] for chunk in all_chunks),
        last_finished_at=max(chunk["finished_at"] for chunk in all_chunks),
        observed_successful_calls=len(all_chunks),
        current_reviewed_samples=len(current_hashes),
        imported_samples_not_rereviewed=len(imported),
        total_cost_usd=round(sum(float(chunk.get("cost_usd") or 0) for chunk in all_chunks), 6),
    )
    evidence["reviewer_runtime_metadata.json"] = (canonical_json(runtime) + "\n").encode()
    prompt_artifact: dict[str, bytes] = {}
    for entry in base_manifest["review_provenance"]["artifacts"]:
        artifact_path = entry["path"]
        if not artifact_path.startswith("review_evidence/review_prompts/review_prompt_"):
            continue
        raw = (base / artifact_path).read_bytes()
        require(sha(raw) == entry["sha256"], f"base archived prompt changed: {artifact_path}")
        prompt_artifact[artifact_path] = raw
    if old_prompt_hash != current_prompt_hash:
        legacy_prompt_path = f"review_evidence/review_prompts/review_prompt_{old_prompt_hash}.md"
        previous = prompt_artifact.setdefault(legacy_prompt_path, old_prompt_raw)
        require(previous == old_prompt_raw, "base prompt conflicts with its archived prompt")
    require(
        all(sha(raw) != current_prompt_hash for raw in prompt_artifact.values()),
        "current prompt must not be duplicated as a historical prompt artifact",
    )

    target.mkdir(parents=True, exist_ok=True)
    evidence_dir = target / "review_evidence"
    evidence_dir.mkdir(exist_ok=True)
    for name, raw in evidence.items():
        (evidence_dir / name).write_bytes(raw)
    for artifact_path, raw in (archived_inputs | prompt_artifact).items():
        path = target / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    (target / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pii = json.loads((base / "pii_exceptions.json").read_text(encoding="utf-8"))
    pii["dataset_version"] = args.version
    (target / "pii_exceptions.json").write_text(canonical_json(pii) + "\n", encoding="utf-8")
    (target / "review_prompt.md").write_bytes(prompt_raw)
    (target / "samples.jsonl").write_text(
        "".join(canonical_json(sample) + "\n" for sample in ordered_samples), encoding="utf-8"
    )

    resolution_raw = args.resolution_file.resolve().read_bytes()
    revision_provenance = {
        "format": "main-successor-revision-provenance-v1",
        "base": {"path": relative(base), "dataset_hash": base_manifest["dataset_hash"]},
        "probe": {"path": relative(probe), "dataset_hash": probe_manifest["dataset_hash"]},
        "annotation_revision": {
            "path": relative(revision),
            "manifest_sha256": sha((revision / "manifest.json").read_bytes()),
            "proposals_sha256": sha((revision / "proposals.json").read_bytes()),
            "corpus_edits_sha256": sha((revision / "corpus_edits.json").read_bytes()),
            "confirmation_path": relative(confirmation),
            "confirmation_sha256": sha(confirmation.read_bytes()),
        },
        "supplemental_reviews": source_provenance,
        "successor_resolutions": {
            "path": relative(args.resolution_file),
            "sha256": sha(resolution_raw),
            "sample_ids": sorted(resolutions),
        },
        "changed_review_input_ids": sorted(changed_ids),
        "proposal_sample_ids": sorted(proposal_ids),
        "human_confirmation": confirmed,
        "independent_second_human": False,
        "archived_mixed_chunk_inputs": [
            {"path": path, "sha256": sha(raw)} for path, raw in sorted(archived_inputs.items())
        ],
        "archived_review_prompts": [
            {"path": path, "sha256": sha(raw)} for path, raw in sorted(prompt_artifact.items())
        ],
        "note": (
            "The project owner confirmed the exact annotation revision. Changed and corpus-dependent inputs "
            "were independently rereviewed by the fixed LLM; this remains a one-human provisional dataset."
        ),
    }
    (target / "revision_provenance.json").write_text(canonical_json(revision_provenance) + "\n", encoding="utf-8")

    slice_counts = Counter(value for sample in ordered_samples for value in sample["slices"])
    dept_counts = Counter(sample["dept"] for sample in ordered_samples)
    language_counts = Counter(sample_language(sample, by_hash, by_key) for sample in ordered_samples)
    counts = {
        "samples": len(ordered_samples),
        "answerable": sum(sample.get("answerable", True) is not False for sample in ordered_samples),
        "no_answer": sum(sample.get("answerable", True) is False for sample in ordered_samples),
        "conflict": sum("version_conflict" in sample["slices"] for sample in ordered_samples),
        "derived": sum(bool(sample.get("derived_from")) for sample in ordered_samples),
        "imported": len(imported),
        "documents": len(corpus["documents"]),
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
            f"主评测集 {args.version}：导入探针 {probe_manifest['dataset_version']}，应用 2026-10-08 人工确认的"
            "标注与语料元数据修订，并对全部变化的复核输入完成独立 LLM 复核。第二独立人工仍未完成。"
        ),
        counts=counts,
        reviewers=[base_manifest["reviewers"][0], second],
        files=[{"path": name, "sha256": sha((target / name).read_bytes())} for name in files],
        dataset_hash=None,
        supersedes=base_manifest["dataset_version"],
        change_reason=(
            f"导入 {probe_manifest['dataset_version']} 的两条 EVAL-11 证据修订；"
            "将 ICH E7 两题改为五个共同必需 gold；两个 GVP 跨 chunk gold 保留为 unmappable miss。"
            "全部变化的复核输入均有 agree 意见，历史混合调用输入与旧提示按 SHA-256 归档。"
        ),
    )
    artifacts = {f"review_evidence/{name}": raw for name, raw in evidence.items()} | archived_inputs | prompt_artifact
    manifest["review_provenance"].update(
        reviewer_id=second["id"],
        version_source="pinned_model_id",
        backend_model_version=second["model_version"],
        reasoning_effort="high",
        artifacts=[{"path": path, "sha256": sha(raw)} for path, raw in sorted(artifacts.items())],
    )
    manifest["imported_samples"] = {
        "dataset_id": probe_manifest["dataset_id"],
        "dataset_version": probe_manifest["dataset_version"],
        "dataset_hash": probe_manifest["dataset_hash"],
        "path": f"evals/probe/precise_clause/{probe_manifest['dataset_version']}/samples.jsonl",
        "samples_sha256": sha((probe / "samples.jsonl").read_bytes()),
        "count": len(imported),
        "prompt_hash": next(
            row["prompt_hash"] for row in probe_manifest["reviewers"] if row.get("role") == "second_reviewer"
        ),
        "prompt_hashes": sorted({row["review"]["second_reviewer"]["prompt_hash"] for row in imported}),
        "reviewer_id": next(row["id"] for row in probe_manifest["reviewers"] if row.get("role") == "second_reviewer"),
        "statement": (
            f"探针 {probe_manifest['dataset_version']} 的 {len(imported)} 条样本原样并入（canonical 字节一致），"
            "保留每条样本实际使用的历史或当前复核提示哈希；报告中探针子集单列。"
        ),
    }
    manifest["derived_samples"]["count"] = counts["derived"]
    manifest["derived_samples"]["human_confirmation"]["confirmed_on"] = args.created_at
    manifest["second_human_review"] = {
        "status": "pending",
        "reviewer_id": None,
        "statement": (
            "项目当前只有一名人工参与者；项目所有者完成裁决与确认，但不是独立第二人工复核。"
            "本集继续以 provisional 运行并在报告中披露该限制。"
        ),
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "status": "draft",
        "dataset_version": args.version,
        "samples": len(ordered_samples),
        "imported": len(imported),
        "local": len(current_hashes),
        "changed_review_input_ids": sorted(changed_ids),
        "current_disputes": sorted(disputed),
        "archived_mixed_chunk_inputs": sorted(archived_inputs),
        "archived_review_prompts": sorted(prompt_artifact),
        "model_calls": 0,
        "target": relative(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--revision", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--supplemental-run", type=Path, action="append", required=True)
    parser.add_argument("--resolution-file", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--created-at", default=dt.date.today().isoformat())
    args = parser.parse_args()
    print(json.dumps(assemble(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
