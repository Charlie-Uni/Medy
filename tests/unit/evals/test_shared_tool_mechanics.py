"""Byte compatibility, failed freeze recovery, budget assembly and review bindings."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from medops.evals import bootstrap
from medops.evals.files import atomic_write, jsonl_text, write_jsonl
from medops.evals.freeze import freeze_version
from medops.evals.successor_review import annotate_prompt, append_review_run, latest_verdicts, verdicts


@pytest.mark.parametrize("sort_manifest", [False, True])
def test_freeze_keeps_historical_checksum_and_manifest_bytes(tmp_path, sort_manifest):
    manifest = {"status": "draft", "dataset_version": "fixture-provisional"}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    sample_bytes = '{"query":"合成问题","sample_id":"test"}\n'.encode()
    (tmp_path / "samples.jsonl").write_bytes(sample_bytes)
    checksum = hashlib.sha256(sample_bytes).hexdigest()
    sums = f"{checksum}  samples.jsonl\n"
    expected = {
        **manifest,
        "files": [{"path": "samples.jsonl", "sha256": checksum}],
        "dataset_hash": hashlib.sha256(sums.encode()).hexdigest(),
        "frozen_at": "2026-10-12",
    }
    expected["status"] = "frozen"
    observed = []

    def validate(path, *, mode):
        observed.append((mode, json.loads((path / "manifest.json").read_bytes())))
        return SimpleNamespace(errors=[])

    validator = SimpleNamespace(validate=validate)
    freeze_version(tmp_path, manifest, validator, frozen_at="2026-10-12", sort_manifest=sort_manifest)
    assert (tmp_path / "SHA256SUMS").read_bytes() == sums.encode()
    assert (tmp_path / "manifest.json").read_bytes() == (
        json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=sort_manifest) + "\n"
    ).encode()
    assert observed == [("frozen", expected)] and manifest == expected
    with pytest.raises(ValueError, match="already frozen"):
        freeze_version(tmp_path, manifest, validator, frozen_at="tomorrow", sort_manifest=sort_manifest)


@pytest.mark.parametrize("failure", ["validation_errors", "validation_exception", "manifest_write"])
def test_failed_freeze_restores_exact_draft_and_removes_marker(tmp_path, monkeypatch, failure):
    from medops.evals import freeze

    original = b'{ "status" : "draft", "note" : "retain spacing" }\n'
    (tmp_path / "manifest.json").write_bytes(original)
    (tmp_path / "samples.jsonl").write_text('{"sample_id":"fixture"}\n')
    manifest = json.loads(original)

    def validate(*args, **kwargs):
        if failure == "validation_exception":
            raise RuntimeError("synthetic validation failure")
        return SimpleNamespace(errors=["synthetic invalid result"])

    if failure == "manifest_write":

        def write(path, text):
            if path.name == "manifest.json":
                raise OSError("synthetic write failure")
            atomic_write(path, text)

        monkeypatch.setattr(freeze, "atomic_write", write)
    if failure == "validation_errors":
        assert freeze_version(
            tmp_path, manifest, SimpleNamespace(validate=validate), frozen_at="today", sort_manifest=False
        ).errors
    else:
        with pytest.raises((RuntimeError, OSError)):
            freeze_version(
                tmp_path, manifest, SimpleNamespace(validate=validate), frozen_at="today", sort_manifest=False
            )
    assert (tmp_path / "manifest.json").read_bytes() == original
    assert not (tmp_path / "SHA256SUMS").exists() and manifest == json.loads(original)


def test_jsonl_order_and_unicode_bytes_and_bad_verdict_rows(tmp_path):
    rows = [{"z": "中文", "a": 1}, {"sample_id": "fixture-2"}]
    assert jsonl_text(rows) == '{"z": "中文", "a": 1}\n{"sample_id": "fixture-2"}\n'
    path = tmp_path / "rows.jsonl"
    write_jsonl(path, iter(rows))
    assert path.read_text() == '{"a": 1, "z": "中文"}\n{"sample_id": "fixture-2"}\n'
    path.write_text("[]\n")
    with pytest.raises(ValueError, match="JSON object"):
        verdicts(path)
    path.write_text('{"sample_id":"x"}\n{"sample_id":"x"}\n')
    with pytest.raises(ValueError, match="duplicate verdict"):
        verdicts(path)


def test_atomic_text_failure_keeps_old_file_and_removes_temp(tmp_path, monkeypatch):
    path = tmp_path / "bound.json"
    path.write_bytes(b"original")

    def refuse(*args):
        raise OSError("synthetic rename failure")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError):
        atomic_write(path, "replacement")
    assert path.read_bytes() == b"original" and list(tmp_path.iterdir()) == [path]


def test_review_append_offsets_bindings_preserves_source_and_refuses_bad_prompt():
    source = {
        "chunks": [{"verdicts": [{"sample_id": "new", "verdict": "agree"}]}],
        "latest": {"new": {"chunk_index": 0}},
        "sample_input_sha256": {"new": "input"},
        "review_prompt_sha256": "b" * 64,
    }
    original = json.dumps(source)
    merged = {"chunks": [{"verdicts": []}], "latest": {}, "sample_input_sha256": {}}
    append_review_run(merged, annotate_prompt(source), {"new"}, "b" * 64)
    assert merged["latest"]["new"]["chunk_index"] == 1
    assert latest_verdicts(merged) == {"new": {"sample_id": "new", "verdict": "agree"}}
    assert json.dumps(source) == original
    source["chunks"][0]["review_prompt_sha256"] = "bad"
    with pytest.raises(ValueError, match="invalid per-invocation prompt"):
        annotate_prompt(source)
    merged["chunks"][1]["verdicts"].append({"sample_id": "new", "verdict": "dispute"})
    with pytest.raises(ValueError, match="one verdict"):
        latest_verdicts(merged)


def test_shared_bootstrap_preserves_cap_and_required_budget_and_shares_views(monkeypatch):
    calls, outputs = [], []
    gpu = SimpleNamespace(close=lambda **kwargs: calls.append(("close", kwargs)))
    budgeted = SimpleNamespace()
    monkeypatch.setattr(bootstrap, "InferenceProcess", lambda **kwargs: calls.append(("gpu", kwargs)) or gpu)
    monkeypatch.setattr(bootstrap, "ProcessEmbedding", lambda lane: SimpleNamespace(lane=lane))
    monkeypatch.setattr(
        bootstrap, "build_budgeted_gateway", lambda settings, **kwargs: calls.append(("budget", kwargs)) or budgeted
    )
    monkeypatch.setattr(
        bootstrap,
        "ProcessReranker",
        lambda lane, *, output: outputs.append(output) or SimpleNamespace(lane=lane, output=output),
    )
    runtime = bootstrap.bootstrap_execution(
        object(), device="cpu", rerank_output=8, gpu_timeout_s=9.0, run_cap_usd=0.15
    )
    assert calls == [
        ("gpu", {"device": "cpu", "output": 8, "timeout_s": 9.0}),
        ("budget", {"run_cap_usd": 0.15, "require_execution_budget": True}),
    ]
    assert runtime.reranker(8) is runtime.reranker(8)
    assert runtime.reranker(20).lane is gpu and outputs == [8, 20]
    assert runtime.gateway.calls == 0


def test_failed_bootstrap_reaps_existing_lane(monkeypatch):
    closed = []
    monkeypatch.setattr(
        bootstrap, "InferenceProcess", lambda **kwargs: SimpleNamespace(close=lambda **kwargs: closed.append(kwargs))
    )

    def refuse(*args):
        raise RuntimeError("synthetic embedding startup failure")

    monkeypatch.setattr(bootstrap, "ProcessEmbedding", refuse)
    with pytest.raises(RuntimeError):
        bootstrap.bootstrap_execution(object(), device="cpu", rerank_output=8, gpu_timeout_s=9.0, run_cap_usd=0.15)
    assert closed == [{"graceful": False}]
