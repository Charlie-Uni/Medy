"""Frozen service-alias evidence must bind real samples, calls and human resolutions."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from medops.core.canonical import canonical_json
from medops.evals.probe import review_provenance as provenance
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from tests.unit.evals.fixture_builder import build, refreeze

SCHEMA = Path(__file__).resolve().parents[3] / "evals/probe/precise_clause/schema/manifest.schema.json"
LIMITATION = (
    "The service alias is observed, but its backend snapshot is not exposed; exact model replay is unavailable."
)


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")


def save_samples(version, samples):
    (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")


def rehash(version, manifest, name):
    path = f"review_evidence/{name}"
    entry = next(a for a in manifest["review_provenance"]["artifacts"] if a["path"] == path)
    entry["sha256"] = hashlib.sha256((version / path).read_bytes()).hexdigest()


def add_artifact(version, manifest, relative):
    manifest["review_provenance"]["artifacts"].append(
        {"path": relative, "sha256": hashlib.sha256((version / relative).read_bytes()).hexdigest()}
    )


@pytest.fixture
def recorded(tmp_path):
    pages_root = tmp_path / "pages"
    version = build(tmp_path / "data", pages_root)
    pages = PageTextProvider(pages_root)
    manifest = json.loads((version / "manifest.json").read_text())
    second = next(r for r in manifest["reviewers"] if r["kind"] == "llm")
    second.update(model="test-model", model_version=provenance.service_alias_version("test-model"))
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    for sample in samples:
        sample["review"]["second_reviewer"] = {k: v for k, v in second.items() if k != "role"}
    disputed = samples[0]["sample_id"]
    samples[0]["review"].update(status="disputed_resolved", resolution_note="Owner retains this exact span.")
    save_samples(version, samples)
    records = provenance._current_records(version, samples, pages)
    prompt = (version / "review_prompt.md").read_text()
    evidence = version / "review_evidence"
    evidence.mkdir()
    resolutions = {}
    for batch in provenance.BATCHES:
        group = [s for s in samples if s["dept"] == batch]
        chunks, latest, verdicts = [], {}, []
        for sample in group:
            sid = sample["sample_id"]
            verdict = {
                "sample_id": sid,
                "verdict": "agree",
                "items": dict.fromkeys(provenance.ITEM_KEYS, "ok"),
                "reason": "",
                "suggestion": "",
            }
            if sid == disputed:
                verdict.update(verdict="dispute", reason="Question about the span boundary.")
                verdict["items"]["evidence_span"] = "issue"
            chunk = {
                "model": second["model"],
                "reasoning_effort": "high",
                "returncode": 0,
                "session_id": f"test-session-{sid}",
                "cli_version": "test-cli-1",
                "started_at": "2026-09-19T12:00:00+00:00",
                "finished_at": "2026-09-19T12:01:00+00:00",
                "sample_ids": [sid],
                "sample_input_sha256": {sid: provenance._digest(records[sid])},
                "prompt_sha256": provenance._actual_prompt_hash(prompt, [records[sid]]),
                "verdicts": [verdict],
            }
            reference = {
                "chunk_index": len(chunks),
                "sample_input_sha256": chunk["sample_input_sha256"][sid],
                "prompt_sha256": chunk["prompt_sha256"],
                "verdict_sha256": provenance._digest(verdict),
            }
            latest[sid] = reference
            chunks.append(chunk)
            verdicts.append(verdict)
            if sid == disputed:
                resolutions[sid] = {
                    "sample_input_sha256": reference["sample_input_sha256"],
                    "verdict_sha256": reference["verdict_sha256"],
                    "issue_scope": ["evidence_span"],
                    "resolution_note": sample["review"]["resolution_note"],
                }
        run = {
            "batch": batch,
            "model": second["model"],
            "reasoning_effort_requested": "high",
            "review_prompt_sha256": second["prompt_hash"],
            "provenance_version": 2,
            "active_review": None,
            "sample_input_sha256": {s["sample_id"]: provenance._digest(records[s["sample_id"]]) for s in group},
            "chunks": chunks,
            "latest": latest,
        }
        save_json(evidence / f"run_{batch}.json", run)
        (evidence / f"verdicts_{batch}.jsonl").write_text("".join(json.dumps(v) + "\n" for v in verdicts))
    save_json(evidence / "resolutions.json", resolutions)
    save_json(
        evidence / "reviewer_runtime_metadata.json",
        {
            "model_service_alias": second["model"],
            "backend_model_version": None,
            "backend_model_version_status": "not exposed by observed outputs",
            "cli_versions": ["test-cli-1"],
            "reasoning_effort": "high",
            "first_started_at": "2026-09-19T12:00:00+00:00",
            "last_finished_at": "2026-09-19T12:01:00+00:00",
            "observed_successful_calls": len(samples),
            "current_reviewed_samples": len(samples),
        },
    )
    manifest["review_provenance"] = {
        "reviewer_id": second["id"],
        "version_source": "service_alias",
        "backend_model_version": None,
        "reproducibility_limitations": LIMITATION,
        "artifacts": [
            {"path": path, "sha256": hashlib.sha256((version / path).read_bytes()).hexdigest()}
            for path in provenance.EVIDENCE_PATHS
        ],
    }
    save_json(version / "manifest.json", manifest)
    refreeze(version)
    manifest = json.loads((version / "manifest.json").read_text())
    return version, manifest, pages


def failures(recorded):
    version, manifest, pages = recorded
    return [
        f.message for f in provenance.validate_review_provenance(version, manifest, pages=pages) if f.level == "error"
    ]


def test_complete_frozen_evidence_passes_with_canonical_samples(recorded):
    version, manifest, pages = recorded
    assert provenance.validate_review_provenance(version, manifest, pages=pages) == []
    assert list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(manifest)) == []


def test_existing_real_version_without_provenance_remains_compatible(tmp_path):
    manifest = {"reviewers": [{"role": "second_reviewer", "kind": "llm", "model_version": "provider-snapshot-2026-01"}]}
    assert provenance.validate_review_provenance(tmp_path, manifest) == []


def test_sentinel_requires_provenance_in_schema_and_validator(recorded):
    _, manifest, _ = recorded
    del manifest["review_provenance"]
    assert failures(recorded)
    assert list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(manifest))


def test_changing_version_string_cannot_hide_existing_evidence(recorded):
    _, manifest, _ = recorded
    del manifest["review_provenance"]
    next(r for r in manifest["reviewers"] if r["kind"] == "llm")["model_version"] = "invented-snapshot"
    assert failures(recorded)


@pytest.mark.parametrize(
    "field,value",
    [
        ("backend_model_version", "invented-version"),
        ("version_source", "snapshot"),
        ("reviewer_id", "unrelated-reviewer"),
        ("reproducibility_limitations", " "),
    ],
)
def test_invalid_missing_version_declaration_is_rejected(recorded, field, value):
    recorded[1]["review_provenance"][field] = value
    assert failures(recorded)


def test_sentinel_cannot_name_a_different_model(recorded):
    second = next(r for r in recorded[1]["reviewers"] if r["kind"] == "llm")
    second["model_version"] = provenance.service_alias_version("other-model")
    assert failures(recorded)


@pytest.mark.parametrize("change", ["missing", "duplicate", "traversal", "absolute", "digest"])
def test_artifacts_have_exact_paths_coverage_and_hashes(recorded, change):
    entries = recorded[1]["review_provenance"]["artifacts"]
    if change == "missing":
        entries.pop()
    elif change == "duplicate":
        entries[-1] = copy.deepcopy(entries[0])
    elif change in ("traversal", "absolute"):
        entries[0]["path"] = "../run_MA.json" if change == "traversal" else "/tmp/run_MA.json"
    else:
        entries[0]["sha256"] = "0" * 64
    assert failures(recorded)


@pytest.mark.parametrize("directory", [False, True])
def test_even_hash_matching_external_symlinks_are_rejected(recorded, tmp_path, directory):
    version, _, _ = recorded
    target = version / "review_evidence" if directory else version / "review_evidence/run_MA.json"
    outside = tmp_path / "outside"
    target.rename(outside)
    target.symlink_to(outside, target_is_directory=directory)
    assert failures(recorded)


@pytest.mark.parametrize("change", ["empty", "model", "pending", "coverage", "session", "binding", "prompt"])
def test_rehashed_but_unrelated_or_stale_runs_are_rejected(recorded, change):
    version, manifest, _ = recorded
    path = version / "review_evidence/run_MA.json"
    run = json.loads(path.read_text())
    sid = next(iter(run["latest"]))
    if change == "empty":
        run = {}
    elif change == "model":
        run["model"] = "unrelated"
    elif change == "pending":
        run["active_review"] = {"pending_ids": [sid]}
    elif change == "coverage":
        del run["latest"][sid]
    elif change == "session":
        run["chunks"][0]["session_id"] = None
    elif change == "binding":
        run["latest"][sid]["verdict_sha256"] = "0" * 64
    else:
        run["chunks"][0]["prompt_sha256"] = "0" * 64
        run["latest"][sid]["prompt_sha256"] = "0" * 64
    save_json(path, run)
    rehash(version, manifest, path.name)
    assert failures(recorded)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_service_alias", "other-model"),
        ("backend_model_version", "invented"),
        ("observed_successful_calls", 0),
        ("cli_versions", ["unrelated"]),
        ("current_reviewed_samples", 1),
    ],
)
def test_runtime_claims_must_match_recorded_calls(recorded, field, value):
    version, manifest, _ = recorded
    path = version / "review_evidence/reviewer_runtime_metadata.json"
    runtime = json.loads(path.read_text())
    runtime[field] = value
    save_json(path, runtime)
    rehash(version, manifest, path.name)
    assert failures(recorded)


def test_old_resolution_cannot_cover_current_dispute(recorded):
    version, manifest, _ = recorded
    path = version / "review_evidence/resolutions.json"
    resolution = json.loads(path.read_text())
    resolution[next(iter(resolution))]["verdict_sha256"] = "0" * 64
    save_json(path, resolution)
    rehash(version, manifest, path.name)
    assert failures(recorded)


@pytest.mark.parametrize("with_verdict", [True, False])
def test_latest_cannot_hide_a_later_appended_invocation(recorded, with_verdict):
    version, manifest, _ = recorded
    path = version / "review_evidence/run_MA.json"
    run = json.loads(path.read_text())
    # The same reviewed input first agreed, then received a new dispute. Leaving the
    # old latest pointer and JSONL mirror intact must not conceal the newer call.
    newer = copy.deepcopy(run["chunks"][1])
    newer["session_id"] = "later-appended-session"
    newer["verdicts"][0].update(verdict="dispute", reason="A newly found query issue.")
    newer["verdicts"][0]["items"]["query"] = "issue"
    if not with_verdict:
        newer["verdicts"] = []
    run["chunks"].append(newer)
    save_json(path, run)
    rehash(version, manifest, path.name)
    runtime_path = version / "review_evidence/reviewer_runtime_metadata.json"
    runtime = json.loads(runtime_path.read_text())
    runtime["observed_successful_calls"] += 1
    save_json(runtime_path, runtime)
    rehash(version, manifest, runtime_path.name)
    assert any("last appended invocation" in message for message in failures(recorded))


@pytest.mark.parametrize("forge_input_hashes", [False, True])
def test_changed_sample_cannot_reuse_review_after_refreezing(recorded, forge_input_hashes):
    version, manifest, pages = recorded
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    samples[0]["query"] = "A changed question after the completed review?"
    save_samples(version, samples)
    if forge_input_hashes:
        records = provenance._current_records(version, samples, pages)
        sid = samples[0]["sample_id"]
        path = version / "review_evidence/run_MA.json"
        run = json.loads(path.read_text())
        digest = provenance._digest(records[sid])
        run["sample_input_sha256"][sid] = digest
        run["latest"][sid]["sample_input_sha256"] = digest
        run["chunks"][0]["sample_input_sha256"][sid] = digest
        save_json(path, run)
        rehash(version, manifest, path.name)
    save_json(version / "manifest.json", manifest)
    refreeze(version)
    manifest.update(json.loads((version / "manifest.json").read_text()))
    messages = failures(recorded)
    assert any("actual prompt" in message if forge_input_hashes else "input hash" in message for message in messages)


def test_hashed_archived_pack_preserves_unchanged_member_of_a_mixed_historical_chunk(recorded):
    version, manifest, pages = recorded
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    by_id = {sample["sample_id"]: sample for sample in samples}
    old_records = provenance._current_records(version, samples, pages)
    run_path = version / "review_evidence/run_MA.json"
    run = json.loads(run_path.read_text())
    verdict_path = version / "review_evidence/verdicts_MA.jsonl"
    verdicts = {row["sample_id"]: row for row in provenance._jsonl(verdict_path.read_bytes())}
    stable, changed = "pc-0002", "pc-0003"

    old_inputs = [old_records[stable], old_records[changed]]
    historical = copy.deepcopy(run["chunks"][1])
    historical.update(
        session_id="mixed-historical-session",
        sample_ids=[stable, changed],
        sample_input_sha256={sid: provenance._digest(old_records[sid]) for sid in (stable, changed)},
        prompt_sha256=provenance._actual_prompt_hash((version / "review_prompt.md").read_text(), old_inputs),
        verdicts=[verdicts[stable], verdicts[changed]],
        input_path="chunk_inputs/pending.jsonl",
    )
    historical["input_path"] = f"chunk_inputs/input_{historical['prompt_sha256']}.jsonl"
    archive_path = version / "review_evidence" / historical["input_path"]
    archive_path.parent.mkdir()
    archive_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in old_inputs))
    historical_index = len(run["chunks"])
    run["chunks"].append(historical)
    for sid in (stable, changed):
        run["latest"][sid] = {
            "chunk_index": historical_index,
            "sample_input_sha256": historical["sample_input_sha256"][sid],
            "prompt_sha256": historical["prompt_sha256"],
            "verdict_sha256": provenance._digest(verdicts[sid]),
        }

    by_id[changed]["query"] = "A changed, newly reviewed question for the same evidence?"
    save_samples(version, samples)
    current_records = provenance._current_records(version, samples, pages)
    newer = copy.deepcopy(run["chunks"][2])
    newer.update(
        session_id="targeted-current-session",
        sample_ids=[changed],
        sample_input_sha256={changed: provenance._digest(current_records[changed])},
        prompt_sha256=provenance._actual_prompt_hash(
            (version / "review_prompt.md").read_text(), [current_records[changed]]
        ),
        verdicts=[verdicts[changed]],
    )
    newer.pop("input_path", None)
    newer_index = len(run["chunks"])
    run["chunks"].append(newer)
    run["sample_input_sha256"][changed] = newer["sample_input_sha256"][changed]
    run["latest"][changed] = {
        "chunk_index": newer_index,
        "sample_input_sha256": newer["sample_input_sha256"][changed],
        "prompt_sha256": newer["prompt_sha256"],
        "verdict_sha256": provenance._digest(verdicts[changed]),
    }
    save_json(run_path, run)
    rehash(version, manifest, run_path.name)
    runtime_path = version / "review_evidence/reviewer_runtime_metadata.json"
    runtime = json.loads(runtime_path.read_text())
    runtime["observed_successful_calls"] += 2
    save_json(runtime_path, runtime)
    rehash(version, manifest, runtime_path.name)
    add_artifact(version, manifest, archive_path.relative_to(version).as_posix())
    save_json(version / "manifest.json", manifest)
    refreeze(version)
    manifest.update(json.loads((version / "manifest.json").read_text()))

    assert provenance.validate_review_provenance(version, manifest, pages=pages) == []
    assert list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(manifest)) == []

    archive_path.write_text(archive_path.read_text().replace(stable, "pc-9999", 1))
    assert any("artifact SHA-256 mismatch" in message for message in failures(recorded))


def test_hashed_archived_prompt_preserves_historical_reviews_after_prompt_upgrade(recorded):
    version, manifest, pages = recorded
    old_prompt = (version / "review_prompt.md").read_bytes()
    old_hash = hashlib.sha256(old_prompt).hexdigest()
    archived = version / "review_evidence/review_prompts" / f"review_prompt_{old_hash}.md"
    archived.parent.mkdir()
    archived.write_bytes(old_prompt)
    add_artifact(version, manifest, archived.relative_to(version).as_posix())

    new_prompt = old_prompt + b"\nSuccessor-only multi-evidence instructions.\n"
    (version / "review_prompt.md").write_bytes(new_prompt)
    new_hash = hashlib.sha256(new_prompt).hexdigest()
    next(r for r in manifest["reviewers"] if r["kind"] == "llm")["prompt_hash"] = new_hash
    save_json(version / "manifest.json", manifest)
    refreeze(version)
    manifest.update(json.loads((version / "manifest.json").read_text()))

    assert provenance.validate_review_provenance(version, manifest, pages=pages) == []
    assert list(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(manifest)) == []
    report = ProbeSetValidator(SCHEMA.parent, pages).validate(version, mode="frozen")
    assert report.errors == []

    archived.write_bytes(old_prompt + b"tampered")
    rehash(version, manifest, archived.relative_to(version / "review_evidence").as_posix())
    assert any("filename/content" in message for message in failures(recorded))


def test_without_page_texts_only_metadata_is_verified(recorded):
    version, manifest, _ = recorded
    findings = provenance.validate_review_provenance(version, manifest)
    assert len(findings) == 1 and findings[0].level == "warning"
    assert "not reconstructed" in findings[0].message
