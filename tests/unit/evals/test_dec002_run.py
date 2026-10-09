"""DEC-002 vector run harness: report rendering from a results structure, the diagnostic threshold verdict,
the searcher's use of the boundary, and the refusal to overwrite a run directory (no database, no model)."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from types import SimpleNamespace

import pytest

from medops.evals.experiments import dec002_run as v
from medops.evals.experiments.dec001_run import CROSS_LINGUAL, LANGUAGE_MATCHED, Query
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


@pytest.mark.parametrize("gold_only", [False, True])
def test_no_gold_queries_are_refused_before_any_database_or_model_work(tmp_path, monkeypatch, gold_only):
    no_gold = Query("no-gold", "MA", "query", (), (), "en")
    monkeypatch.setattr(v, "load_queries", lambda path: [no_gold])

    def unexpected_manifest(**kwargs):
        pytest.fail("input validation must happen before database inspection or manifest creation")

    monkeypatch.setattr(v, "build_manifest", unexpected_manifest)
    out = tmp_path / "run"
    with pytest.raises(ValueError, match="gold evidence"):
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
            warmup=0,
            measured=1,
            seed=1,
            device="cpu",
            purpose="unit",
            gold_only=gold_only,
        )
    assert not out.exists()


def test_explicit_gold_subset_keeps_unmappable_misses_and_auditable_rankings(tmp_path, monkeypatch):
    queries = [
        Query("mapped", "MA", "q1", (), ("g1", "unmappable"), "en", language="en"),
        Query("cross", "PV", "q2", (), ("g2",), "en"),
        Query("refusal", "CO", "q3", (), (), "en"),
    ]
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "entries": [
                    {"gold_id": "g1", "status": "mapped", "chunk_ids": ["c1"]},
                    {"gold_id": "g2", "status": "mapped", "chunk_ids": ["c2"]},
                    {"gold_id": "unmappable", "status": "unmappable", "chunk_ids": []},
                ]
            }
        )
    )
    monkeypatch.setattr(v, "load_queries", lambda path: queries)
    manifest = _manifest()
    manifest["measurement"].update(warmup_full_passes=0, measured_full_passes=1)
    monkeypatch.setattr(v, "build_manifest", lambda **kwargs: manifest)
    seen = []

    def search(q, k):
        seen.append(q.sample_id)
        return SimpleNamespace(
            candidates=[SimpleNamespace(chunk_id={"mapped": "c1", "cross": "c2"}[q.sample_id])],
            returned_count=1,
            candidate_exhausted=True,
        )

    search.close = lambda: seen.append("closed")
    monkeypatch.setattr(v, "db_searcher", lambda *args: search)
    monkeypatch.setattr(v, "leak_check", lambda *args: [])
    monkeypatch.setattr(v, "plan_evidence", lambda *args: [])
    out = tmp_path / "run"
    results = v.run(
        repo=tmp_path,
        dataset_dir=tmp_path,
        out_dir=out,
        mapping_path=mapping_path,
        app_dsn="unused",
        admin_dsn="unused",
        provider=HashingEmbeddingProvider(),
        as_of=date(2026, 9, 20),
        k=20,
        warmup=0,
        measured=1,
        seed=1,
        device="cpu",
        purpose="unit",
        gold_only=True,
    )
    assert sorted(seen[:-1]) == ["cross", "mapped"] and seen[-1] == "closed"
    assert results["candidates"]["V"]["strict_macro_recall"] == 0.75
    selection = json.loads((out / "run_manifest.json").read_text())["measurement"]["query_selection"]
    assert selection["source_queries"] == 3 and selection["selected_queries"] == 2
    assert selection["excluded_no_gold_sample_ids"] == ["refusal"]
    rankings = (out / "rankings.json").read_bytes()
    assert results["rankings_sha256"] == hashlib.sha256(rankings).hexdigest()
    assert json.loads(rankings)["mapped"]["rankings"] == [["c1"]]
    assert "repeatability was not assessed" in (out / "report.md").read_text()
