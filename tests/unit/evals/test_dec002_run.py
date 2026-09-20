"""DEC-002 vector run harness: report rendering from a results structure, the diagnostic threshold verdict,
the searcher's use of the boundary, and the refusal to overwrite a run directory (no database, no model)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from medops.evals.experiments import dec002_run as v
from medops.evals.experiments.dec001_run import CROSS_LINGUAL, LANGUAGE_MATCHED
from medops.retrieval.vector.embedding import HashingEmbeddingProvider


def _block(recall: float, n: int) -> dict:
    return {
        "queries": n,
        "strict_macro_recall": recall,
        "by_department": [{"label": "MA", "support": n, "recall": recall, "diagnostic_only": False}],
        "by_slice": [
            {"label": "negation", "support": 3, "recall": None, "diagnostic_only": True},
            {"label": "dose_unit", "support": 5, "recall": 0.5, "diagnostic_only": True},
        ],
        "by_gold_script": [],
        "sample_ids": [],
    }


def _manifest() -> dict:
    return {
        "run_id": "unit-run",
        "protocol": "docs/adr/ADR-0007-embedding-and-reranker-selection.md",
        "dataset": {
            "version": "v2",
            "dataset_hash": "1fc5089f6fa7f80a1a5e23940826b0d4c811cde29e225dd8305241a33beb0321",
        },
        "measurement": {"k": 20, "as_of": "2026-09-20"},
        "environment": {"device": "cpu"},
        "candidates": {
            "V": {
                "provider_spec": HashingEmbeddingProvider().spec.model_dump(),
                "index": {"chunk_count": 42},
            }
        },
    }


def _results(cross: float) -> dict:
    return {
        "run_manifest_sha256": "0" * 64,
        "candidates": {
            "V": {
                "queries": 107,
                "strict_macro_recall": 0.5,
                "scopes": {LANGUAGE_MATCHED: _block(0.7, 75), CROSS_LINGUAL: _block(cross, 32)},
                "leak_violations": [],
                "not_reproducible_queries": [],
                "candidate_exhausted_queries": 0,
                "zero_result_queries": 0,
                "latency_ms": {"p95": 80.5, "mean": 40.25, "max": 120.0},
            }
        },
    }


@pytest.mark.parametrize(("cross", "verdict"), [(0.5, "meets"), (0.49, "below")])
def test_report_renders_scopes_slices_integrity_and_the_diagnostic_verdict(tmp_path, cross, verdict):
    v.write_report(tmp_path, _manifest(), _results(cross))
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| language_matched | 75 | 0.700 |" in md and f"| cross_lingual | 32 | {cross:.3f} |" in md
    assert (
        f"**{verdict}**" in md and "| negation | 3 |  |" in md and "| dose_unit | 5 | 0.500 (diagnostic: n < 8) |" in md
    )
    assert "leak violations: 0" in md and "p95 80.5" in md and "hashing-bag-of-tokens" in md


def test_run_refuses_an_existing_output_directory(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    with pytest.raises(FileExistsError):
        v.run(
            repo=tmp_path,
            dataset_dir=tmp_path,
            out_dir=out,
            mapping_path=tmp_path / "m.json",
            app_dsn="postgresql://app:x@localhost/db",
            admin_dsn="postgresql://admin:x@localhost/db",
            provider=HashingEmbeddingProvider(),
            as_of=date(2026, 9, 20),
            k=20,
            warmup=1,
            measured=1,
            seed=1,
            device="cpu",
            purpose="unit",
        )


def test_manifest_refuses_an_unfrozen_dataset_or_a_foreign_mapping(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "draft", "dataset_hash": "a"}), encoding="utf-8")
    (tmp_path / "m.json").write_text(json.dumps({"dataset_hash": "a", "entries": []}), encoding="utf-8")
    kwargs = dict(
        run_id="r",
        repo=tmp_path,
        dataset_dir=tmp_path,
        mapping_path=tmp_path / "m.json",
        app_dsn="postgresql://app:x@localhost/db",
        admin_dsn="postgresql://admin:x@localhost/db",
        provider=HashingEmbeddingProvider(),
        as_of=date(2026, 9, 20),
        k=20,
        warmup=1,
        measured=1,
        seed=1,
        device="cpu",
        purpose="unit",
    )
    with pytest.raises(RuntimeError, match="not frozen"):
        v.build_manifest(**kwargs)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"status": "frozen", "dataset_hash": "b", "dataset_version": "v2"}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="dataset_hash differs"):
        v.build_manifest(**kwargs)
