"""Replay exports use exact frozen input snapshots; mutable drafts cannot change an experiment."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from medops.core.canonical import canonical_hash
from medops.evals.datasets import bind_run_dataset, load_frozen_dataset, read_rows, sha256_file
from medops.evals.main_scoring import SCORING_BINDING, SCORING_VERSION, bind_run_scoring
from medops.evals.replay_inputs import safety_samples_for_replay

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "replay_builder_inputs_test", REPO / "evals/replay/tools/build_replay_set.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def frozen(path, rows, dataset_id):
    path.mkdir()
    write_rows(path / "samples.jsonl", rows)
    files = {"samples.jsonl": sha256_file(path / "samples.jsonl")}
    (path / "SHA256SUMS").write_text(f"{files['samples.jsonl']}  samples.jsonl\n")
    manifest = {
        "dataset_id": dataset_id,
        "dataset_version": path.name,
        "dataset_hash": sha256_file(path / "SHA256SUMS"),
        "status": "frozen",
        "files": files,
    }
    (path / "manifest.json").write_text(json.dumps(manifest))
    return manifest


@pytest.fixture
def source_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "REPO", tmp_path)
    main = [
        {
            "sample_id": f"ms-{i:04d}",
            "dept": "PV",
            "language": "en",
            "slices": [],
            "query": f"Question {i}?",
            "required_gold_evidence": [{"gold_id": f"g{i}"}],
        }
        for i in range(200)
    ]
    safety = [
        {
            "sample_id": "ss-0001",
            "dataset_version": "safety-v2-provisional",
            "category": "acl_skill_scope",
            "dept": "PV",
            "language": "en",
            "slices": [],
            "query": "Check access.",
            "expected": {"outcome": ["escalated"], "reason_codes": ["acl_denied"]},
            "skill_call": {"skill": "label_query", "version": "1.0.0", "input": {"query": "x"}, "acl_scopes": []},
            "acl": {"forbidden_document_keys": ["doc-a"], "forbidden_source_hashes": []},
            "attack": {"canary": "synthetic-test-only"},
        }
    ]
    paths = {
        name: tmp_path / name for name in ("main-run", "safety-run", "main-v4-provisional", "safety-v2-provisional")
    }
    mm = frozen(paths["main-v4-provisional"], main, "precise_clause_main")
    sm = frozen(paths["safety-v2-provisional"], safety, "safety_set")
    mr = []
    for i, s in enumerate(main):
        mr.append(
            {
                **s,
                "sample_input_sha256": canonical_hash(s),
                "kind": "answerable",
                "outcome": "answered",
                "reason_codes": [],
                "gold_chunks": ["chunk-a"],
                "required_gold_groups": [["chunk-a"]],
                "cited_chunks": ["chunk-a"] if i < 150 else [],
                "gold_cited": i < 150,
                "scoring_version": SCORING_VERSION,
                "versions": {},
            }
        )
    sr = [
        {
            **safety[0],
            "sample_input_sha256": canonical_hash(safety[0]),
            "outcome": "escalated",
            "database": "medops_v2",
            "checks": [{"check": "reason_codes", "ok": True}],
            "passed": True,
            "failed_checks": [],
            "reason_codes": ["acl_denied"],
            "versions": {},
        }
    ]
    for path, manifest, rows, extra in (
        (paths["main-run"], mm, mr, {"scoring": SCORING_BINDING}),
        (paths["safety-run"], sm, sr, {"not_exercised": []}),
    ):
        bind_run_dataset(path, manifest)
        bind_run_scoring(path)
        write_rows(path / "rows.jsonl", rows)
        (path / "results.json").write_text(
            json.dumps(
                {
                    "dataset": {"version": manifest["dataset_version"], "dataset_hash": manifest["dataset_hash"]},
                    "versions": {},
                    **extra,
                }
            )
        )
    return {
        "out": tmp_path / "replay-v4-test",
        "subset_size": 20,
        "seed": 12,
        "bad_share": 0.3,
        "main_run": paths["main-run"],
        "safety_run": paths["safety-run"],
        "main_set": paths["main-v4-provisional"],
        "safety_set": paths["safety-v2-provisional"],
    }


def test_new_export_is_self_contained_and_uses_actual_safety_version(source_runs):
    m = builder.build(**source_runs)
    out = source_runs["out"]
    assert load_frozen_dataset(out, expected_id="loop_replay") == m
    assert builder.check(out) == []
    items = read_rows(out / "safety_items.jsonl")
    samples = safety_samples_for_replay(m, items)
    original = read_rows(source_runs["safety_set"] / "samples.jsonl")[0]
    assert samples["ss-0001"] == original
    assert all(k in samples["ss-0001"] for k in ("skill_call", "attack", "acl"))
    assert items[0]["source"]["dataset"] == m["sources"]["safety"]["dataset_version"] == "safety-v2-provisional"
    assert m["sources"]["safety"]["dataset_hash"] and m["sources"]["safety"]["results_sha256"]
    # Execution reads the embedded copy even if the original source tree is gone.
    (source_runs["safety_set"] / "samples.jsonl").unlink()
    assert safety_samples_for_replay(m, items) == samples
    digest = sha256_file(out / "manifest.json")
    with pytest.raises(ValueError, match="already exists"):
        builder.build(**source_runs)
    assert sha256_file(out / "manifest.json") == digest


@pytest.mark.parametrize(
    "mutation",
    [
        "no_binding",
        "wrong_results",
        "partial",
        "query",
        "expected",
        "hash",
        "checks",
        "not_exercised",
        "old_scoring",
        "main_kind",
        "main_groups",
        "main_runtime_versions",
    ],
)
def test_invalid_source_is_rejected_before_any_output_is_frozen(source_runs, mutation):
    run = (
        source_runs["main_run"]
        if mutation.startswith("main_") or mutation == "old_scoring"
        else source_runs["safety_run"]
    )
    rows = read_rows(run / "rows.jsonl")
    result_path = run / "results.json"
    result = json.loads(result_path.read_text())
    if mutation == "no_binding":
        (run / "dataset_binding.json").unlink()
    elif mutation == "wrong_results":
        result["dataset"]["dataset_hash"] = "f" * 64
    elif mutation == "partial":
        rows = []
    elif mutation in {"query", "expected"}:
        rows[0][mutation] = "changed"
    elif mutation == "hash":
        rows[0].pop("sample_input_sha256")
    elif mutation == "checks":
        rows[0]["checks"][0]["ok"] = False
    elif mutation == "not_exercised":
        result["not_exercised"] = ["ss-0001"]
    elif mutation == "old_scoring":
        result.pop("scoring")
    elif mutation == "main_kind":
        rows[0]["kind"] = "no_answer"
    elif mutation == "main_runtime_versions":
        rows[0]["versions"] = {"policy_version": "another-policy"}
    else:
        rows[0]["required_gold_groups"] = []
    write_rows(run / "rows.jsonl", rows)
    result_path.write_text(json.dumps(result))
    with pytest.raises(ValueError):
        builder.build(**source_runs)
    assert not source_runs["out"].exists()


@pytest.mark.parametrize(
    "mutation", ["hash", "missing_sample", "version", "query", "historical", "database", "duplicate"]
)
def test_tampered_embedded_input_cannot_be_executed(source_runs, mutation):
    manifest = builder.build(**source_runs)
    items = read_rows(source_runs["out"] / "safety_items.jsonl")
    if mutation == "hash":
        items[0]["sample"]["acl"]["forbidden_document_keys"] = []
    elif mutation == "missing_sample":
        items[0].pop("sample")
    elif mutation == "version":
        items[0]["source"]["dataset"] = "safety-v1-provisional"
    elif mutation == "duplicate":
        items.append(copy.deepcopy(items[0]))
    else:
        items[0][mutation] = "changed"
    with pytest.raises(ValueError):
        safety_samples_for_replay(manifest, items)


def test_legacy_inputs_fail_before_runtime_and_no_output_directory_is_created(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "replay_runtime_inputs_test", REPO / "evals/replay/tools/replay_run.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    out = tmp_path / "unstarted"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "replay_run",
            "--set",
            str(REPO / "evals/replay/replay-v3"),
            "--out",
            str(out),
            "--candidate-file",
            "missing.json",
        ],
    )
    with pytest.raises(ValueError, match="legacy replay safety inputs"):
        runner.main()
    assert not out.exists()
    assert safety_samples_for_replay({}, []) == {}
