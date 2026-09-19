"""Do not turn a requested version string into an invented model snapshot."""

import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

from medops.evals.probe.review_provenance import validate_review_provenance
from medops.evals.probe.validator import PageTextProvider
from tests.unit.evals.fixture_builder import build


@pytest.fixture
def assembler(monkeypatch):
    tooling = Path(__file__).resolve().parents[3] / "evals/probe/precise_clause/drafts/v1/tooling"
    monkeypatch.syspath_prepend(str(tooling))
    return importlib.import_module("assemble")


def metadata_fixture():
    runs, evidence = {}, {"resolutions.json": b"{}\n"}
    for batch in ("MA", "PV", "CO"):
        run = {
            "model": "observed-alias",
            "active_review": None,
            "latest": {f"sample-{batch}": {"chunk_index": 0}},
            "chunks": [
                {
                    "model": "observed-alias",
                    "reasoning_effort": "high",
                    "returncode": 0,
                    "session_id": f"synthetic-{batch}",
                    "cli_version": "cli-1",
                    "started_at": "2026-09-19T12:00:00+00:00",
                    "finished_at": "2026-09-19T12:01:00+00:00",
                }
            ],
        }
        runs[batch] = run
        evidence[f"run_{batch}.json"] = json.dumps(run).encode()
        evidence[f"verdicts_{batch}.jsonl"] = b"{}\n"
    return runs, evidence


def test_missing_backend_is_explicit_and_evidence_is_snapshotted(assembler):
    runs, evidence = metadata_fixture()
    original = copy.deepcopy(evidence)
    version, provenance, snapshot = assembler.build_provenance(runs, evidence, "observed-alias", None)
    assert version == "service-alias:observed-alias;backend-version:not-exposed"
    assert provenance["backend_model_version"] is None
    assert len(provenance["artifacts"]) == 8
    runtime = json.loads(snapshot["reviewer_runtime_metadata.json"])
    assert runtime["cli_versions"] == ["cli-1"]
    assert runtime["observed_successful_calls"] == 3
    assert runtime["current_reviewed_samples"] == 3
    assert runtime["backend_model_version"] is None
    assert evidence == original


@pytest.mark.parametrize("requested", ["cli-1", "invented-snapshot-2026-09-20", "unknown"])
def test_unverified_version_argument_is_rejected(assembler, requested):
    runs, evidence = metadata_fixture()
    with pytest.raises(ValueError, match="unsupported by the observed runs"):
        assembler.build_provenance(runs, evidence, "observed-alias", requested)


def test_run_change_cannot_enter_evidence_snapshot(assembler):
    runs, evidence = metadata_fixture()
    runs["PV"]["chunks"][0]["session_id"] = "different-session"
    with pytest.raises(ValueError, match="changed while assembling"):
        assembler.build_provenance(runs, evidence, "observed-alias", None)


def test_missing_batch_evidence_is_rejected(assembler):
    runs, evidence = metadata_fixture()
    evidence.pop("verdicts_CO.jsonl")
    with pytest.raises(ValueError, match="all three batches"):
        assembler.build_provenance(runs, evidence, "observed-alias", None)


def test_backend_version_cannot_be_silently_ignored(assembler):
    runs, evidence = metadata_fixture()
    runs["MA"]["backend_model_version"] = "reported-snapshot"
    evidence["run_MA.json"] = json.dumps(runs["MA"]).encode()
    with pytest.raises(ValueError, match="explicit verification support"):
        assembler.build_provenance(runs, evidence, "observed-alias", None)


def test_draft_changed_after_verification_cannot_replace_verified_assembly_snapshot(assembler, monkeypatch, tmp_path):
    """A deterministic concurrent edit between verification and assembly must stay out of the output."""
    runner = importlib.import_module("run_codex_review")
    pages = tmp_path / "data/v1/pages"
    version = build(tmp_path / "data", pages)
    manifest = json.loads((version / "manifest.json").read_text())
    manifest.update(status="draft", frozen_at=None, dataset_hash=None)
    (version / "manifest.json").write_text(json.dumps(manifest))
    (version / "SHA256SUMS").unlink()
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    # Draft inputs use the recorded prompt wire order; the fixture's canonical JSONL sorts these keys.
    for sample in samples:
        gold = sample["required_gold_evidence"][0]
        gold["evidence_span"] = {key: gold["evidence_span"][key] for key in ("text", "char_start", "char_end")}
    corpus = json.loads((version / "corpus.json").read_text())
    docs = {doc["source_hash"]: doc for doc in corpus["documents"]}
    prompt = (version / "review_prompt.md").read_text()
    drafts = tmp_path / "drafts"
    review = drafts / "review"
    review.mkdir(parents=True)
    (review / "resolutions.json").write_text("{}\n")
    for batch in ("MA", "PV", "CO"):
        group = [sample for sample in samples if sample["dept"] == batch]
        (drafts / f"samples_draft_{batch}.json").write_text(json.dumps(group, ensure_ascii=False))
        records = assembler.pack_samples(group, docs, pages)
        hashes = {record["sample_id"]: runner.record_hash(record) for record in records}
        verdicts = [
            {
                "sample_id": record["sample_id"],
                "verdict": "agree",
                "items": dict.fromkeys(runner.ITEM_KEYS, "ok"),
                "reason": "",
                "suggestion": "",
            }
            for record in records
        ]
        chunk = {
            "model": "test-model",
            "reasoning_effort": "high",
            "returncode": 0,
            "session_id": f"synthetic-{batch}",
            "cli_version": "test-cli-1",
            "started_at": "2026-09-19T12:00:00+00:00",
            "finished_at": "2026-09-19T12:01:00+00:00",
            "sample_ids": list(hashes),
            "sample_input_sha256": hashes,
            "prompt_sha256": runner.actual_prompt_hash(prompt, records),
            "verdicts": verdicts,
        }
        run = {
            "batch": batch,
            "model": "test-model",
            "reasoning_effort_requested": "high",
            "review_prompt_sha256": assembler.sha256_file(version / "review_prompt.md"),
            "provenance_version": 2,
            "active_review": None,
            "sample_input_sha256": hashes,
            "chunks": [chunk],
            "latest": {v["sample_id"]: runner.binding(chunk, 0, v) for v in verdicts},
        }
        (review / f"run_{batch}.json").write_text(json.dumps(run, ensure_ascii=False))
        (review / f"verdicts_{batch}.jsonl").write_text("".join(json.dumps(v) + "\n" for v in verdicts))

    original_query = samples[0]["query"]
    changed_query = "This question was edited after its review was already verified."
    real_verify = assembler.verify_batch_run
    verified_batches = []

    def edit_earlier_draft_after_last_verification(run, *args, **kwargs):
        real_verify(run, *args, input_dir=review, **kwargs)
        verified_batches.append(run["batch"])
        if run["batch"] == "CO":
            path = drafts / "samples_draft_MA.json"
            changed = json.loads(path.read_text())
            changed[0]["query"] = changed_query
            path.write_text(json.dumps(changed, ensure_ascii=False))

    monkeypatch.setattr(assembler, "DRAFTS", drafts)
    monkeypatch.setattr(assembler, "verify_batch_run", edit_earlier_draft_after_last_verification)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble.py",
            "--out",
            str(version),
            "--llm-model",
            "test-model",
            "--verdicts",
            str(review / "verdicts_*.jsonl"),
            "--resolutions",
            str(review / "resolutions.json"),
        ],
    )
    assembler.main()

    assert verified_batches == ["MA", "PV", "CO"]
    assert json.loads((drafts / "samples_draft_MA.json").read_text())[0]["query"] == changed_query
    assembled = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    assert assembled[0]["query"] == original_query
    manifest = json.loads((version / "manifest.json").read_text())
    assert validate_review_provenance(version, manifest, pages=PageTextProvider(pages)) == []
