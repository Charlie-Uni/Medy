"""Frozen inputs fail before model loading; resumes never mix dataset versions."""

import hashlib
import json
import runpy
import sys
from pathlib import Path

import pytest

from medops.evals.audit import audit
from medops.evals.datasets import bind_run_dataset, load_frozen_dataset

REPO = Path(__file__).resolve().parents[3]


def frozen(path, *, layout="paths", dataset_id="safety_set"):
    path.mkdir()
    content = b'{"sample_id":"ss-1"}\n'
    (path / "samples.jsonl").write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    sums = f"{digest}  samples.jsonl\n".encode()
    (path / "SHA256SUMS").write_bytes(sums)
    files = {
        "paths": ["samples.jsonl"],
        "objects": [{"path": "samples.jsonl", "sha256": digest}],
        "dict": {"samples.jsonl": digest},
    }[layout]
    manifest = {
        "dataset_id": dataset_id,
        "dataset_version": "test-v1",
        "status": "frozen",
        "files": files,
        "dataset_hash": hashlib.sha256(sums).hexdigest(),
    }
    (path / "manifest.json").write_text(json.dumps(manifest))
    return manifest


@pytest.mark.parametrize("layout", ["paths", "objects", "dict"])
def test_all_existing_manifest_layouts_are_supported(tmp_path, layout):
    directory = tmp_path / "set"
    expected = frozen(directory, layout=layout)
    assert load_frozen_dataset(directory, expected_id="safety_set") == expected


@pytest.mark.parametrize(
    "mutation",
    ["sample_bytes", "dataset_hash", "declared_files", "status", "review_artifact", "duplicate_path", "escaped_path"],
)
def test_corrupted_or_unbound_inputs_fail(tmp_path, mutation):
    directory = tmp_path / "set"
    manifest = frozen(directory)
    if mutation == "sample_bytes":
        (directory / "samples.jsonl").write_text('{"sample_id":"changed"}\n')
    elif mutation == "dataset_hash":
        manifest["dataset_hash"] = "0" * 64
    elif mutation == "declared_files":
        manifest["files"] = []
    elif mutation == "status":
        manifest["status"] = "draft"
    elif mutation == "review_artifact":
        manifest["review_provenance"] = {"artifacts": [{"path": "samples.jsonl", "sha256": "0" * 64}]}
    else:
        sums = (directory / "SHA256SUMS").read_text()
        if mutation == "duplicate_path":
            sums += sums
        else:
            (tmp_path / "outside").write_bytes((directory / "samples.jsonl").read_bytes())
            sums = sums.replace("samples.jsonl", "../outside")
            manifest["files"] = ["../outside"]
        (directory / "SHA256SUMS").write_text(sums)
        manifest["dataset_hash"] = hashlib.sha256(sums.encode()).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_frozen_dataset(directory)


def test_resumes_require_the_same_dataset_and_do_not_adopt_legacy_rows(tmp_path):
    manifest = frozen(tmp_path / "set")
    out = tmp_path / "run"
    bind_run_dataset(out, manifest)
    (out / "rows.jsonl").write_text('{"sample_id":"ss-1"}\n')
    before = (out / "dataset_binding.json").read_bytes()
    bind_run_dataset(out, manifest)
    with pytest.raises(ValueError, match="another dataset"):
        bind_run_dataset(out, {**manifest, "dataset_hash": "0" * 64})
    assert (out / "dataset_binding.json").read_bytes() == before
    (out / "dataset_binding.json").unlink()
    with pytest.raises(ValueError, match="no dataset binding"):
        bind_run_dataset(out, manifest)
    assert not (out / "dataset_binding.json").exists()


@pytest.mark.parametrize(
    ("script", "flag", "dataset_id", "extra"),
    [
        ("evals/harness/tools/safety_run.py", "--dataset", "safety_set", []),
        ("evals/harness/tools/smoke_ask.py", "--dataset", "precise_clause_main", []),
        ("evals/replay/tools/replay_run.py", "--set", "loop_replay", ["--candidate-file", "unused.json"]),
    ],
)
def test_cli_rejects_corruption_before_initializing_runtime(tmp_path, monkeypatch, script, flag, dataset_id, extra):
    directory = tmp_path / "set"
    frozen(directory, dataset_id=dataset_id)
    (directory / "samples.jsonl").write_text("corrupt")
    namespace = runpy.run_path(str(REPO / script))

    def forbidden():
        pytest.fail("runtime must not initialize for a corrupted dataset")

    namespace["main"].__globals__["Settings"] = forbidden
    monkeypatch.setattr(sys, "argv", [script, "--out", str(tmp_path / "run"), flag, str(directory), *extra])
    with pytest.raises(ValueError, match="digest mismatch"):
        namespace["main"]()
    assert not (tmp_path / "run").exists()


def test_frozen_safety_rejudge_never_overwrites_the_original(tmp_path, monkeypatch):
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"dataset": {"dataset_hash": "a" * 64}}))
    before = results.read_bytes()
    namespace = runpy.run_path(str(REPO / "evals/harness/tools/safety_run.py"))
    monkeypatch.setattr(sys, "argv", ["safety_run", "--out", str(tmp_path), "--rejudge"])
    with pytest.raises(SystemExit, match="cannot overwrite"):
        namespace["main"]()
    assert results.read_bytes() == before


def test_catalog_integrity_and_stale_lineage_are_separate_results():
    catalog = json.loads((REPO / "evals/dataset_catalog.json").read_text())
    report = audit(REPO, catalog)
    assert report["checks_passed"], report["findings"]
    warning = next(f for f in report["findings"] if f["code"] == "replay_uses_old_safety")
    assert len(warning["retired_sample_ids"]) == 7
    assert {f["code"] for f in report["findings"]} >= {"independent_review_pending", "no_unseen_holdout"}
