"""Runner mechanics with fakes: fixed per-pass order, warm-up exclusion, reproducibility detection, strict
recall against a mapping, unmappable golds as misses, script/slice grouping and the refusal to overwrite."""

from __future__ import annotations

import json
from datetime import date

import pytest

from medops.evals.experiments import dec001_run as r
from medops.retrieval.contracts import LexicalCandidate, LexicalSearchResult

VERSIONS = {
    "retriever_version": "x",
    "tokenizer_version": "y",
    "dictionary_version": "z",
    "normalization_version": "norm-v1",
}


def result(ids: list[str], k: int) -> LexicalSearchResult:
    return LexicalSearchResult(
        candidates=tuple(
            LexicalCandidate(chunk_id=c, raw_score=float(len(ids) - i), rank=i + 1) for i, c in enumerate(ids)
        ),
        requested_k=k,
        returned_count=len(ids),
        candidate_exhausted=len(ids) < k,
        **VERSIONS,
    )


QUERIES = [
    r.Query("pc-0001", "MA", "q1", ("drug_name_zh", "dose_unit"), ("pc-0001-g1",), "zh-Hant"),
    r.Query("pc-0002", "PV", "q2", ("negation",), ("pc-0002-g1",), "zh-Hans"),
    r.Query("pc-0003", "CO", "q3", ("protocol_id",), ("pc-0003-g1", "pc-0003-g2"), "en"),
]
MAPPING = {"pc-0001-g1": ["c1"], "pc-0002-g1": [], "pc-0003-g1": ["c3a", "c3b"], "pc-0003-g2": ["c4"]}


def test_execute_passes_uses_seeded_order_and_excludes_warmup_latencies():
    seen: list[str] = []

    def search(q: r.Query, k: int) -> LexicalSearchResult:
        seen.append(q.sample_id)
        return result({"pc-0001": ["c1", "c9"], "pc-0002": ["c2"], "pc-0003": ["c3b"]}[q.sample_id], k)

    outcomes = r.execute_passes(QUERIES, search, k=20, warmup=2, measured=3, seed=7)
    assert len(seen) == 15
    passes = [seen[i : i + 3] for i in range(0, 15, 3)]
    assert all(sorted(p) == ["pc-0001", "pc-0002", "pc-0003"] for p in passes)
    assert passes != [sorted(passes[0])] * 5  # shuffled, not always sorted
    # same seed, same order
    seen.clear()
    r.execute_passes(QUERIES, search, k=20, warmup=2, measured=3, seed=7)
    assert [seen[i : i + 3] for i in range(0, 15, 3)] == passes
    for out in outcomes.values():
        assert len(out.rankings) == 5 and len(out.latencies_ns) == 3
    assert outcomes["pc-0002"].candidate_exhausted is True and outcomes["pc-0002"].returned_count == 1


def test_summarize_scores_strictly_and_groups_by_dept_slice_and_script():
    def search(q: r.Query, k: int) -> LexicalSearchResult:
        return result({"pc-0001": ["c1", "c9"], "pc-0002": ["c2"], "pc-0003": ["c3b"]}[q.sample_id], k)

    outcomes = r.execute_passes(QUERIES, search, k=20, warmup=0, measured=1, seed=1)
    summary = r.summarize("A", QUERIES, outcomes, MAPPING)
    per = summary.pop("_per_query_recall")
    assert per == {"pc-0001": 1.0, "pc-0002": 0.0, "pc-0003": 0.5}
    assert summary["strict_macro_recall"] == pytest.approx(0.5)
    dept = {g["label"]: g for g in summary["by_department"]}
    assert dept["MA"]["recall"] == 1.0 and dept["PV"]["recall"] == 0.0 and dept["CO"]["recall"] == 0.5
    assert all(g["diagnostic_only"] for g in summary["by_slice"])  # support 1 < 8
    script = {g["label"]: g["recall"] for g in summary["by_gold_script"]}
    assert script == {"zh-Hant": 1.0, "zh-Hans": 0.0, "en": 0.5}
    assert summary["drug_name_zh_by_script"][0]["label"] == "drug_name_zh/zh-Hant"
    row = {x["sample_id"]: x for x in summary["per_query"]}
    assert row["pc-0002"]["unmappable_golds"] == ["pc-0002-g1"]
    assert row["pc-0003"]["gold_ranks"] == {"pc-0003-g1": 1, "pc-0003-g2": None}
    assert summary["not_reproducible_queries"] == []
    assert summary["latency_ms"]["measured_executions"] == 3


def test_non_identical_repeated_rankings_are_reported():
    calls = {"n": 0}

    def search(q: r.Query, k: int) -> LexicalSearchResult:
        calls["n"] += 1
        ids = ["c1", "c9"] if calls["n"] % 2 else ["c9", "c1"]
        return result(ids if q.sample_id == "pc-0001" else ["c2"], k)

    outcomes = r.execute_passes(QUERIES, search, k=20, warmup=0, measured=2, seed=3)
    summary = r.summarize("B", QUERIES, outcomes, MAPPING)
    assert summary["not_reproducible_queries"] == ["pc-0001"]


def test_load_mapping_treats_unmappable_as_empty(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"gold_id": "g1", "status": "mapped", "chunk_ids": ["a"]},
                    {"gold_id": "g2", "status": "unmappable", "chunk_ids": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert r.load_mapping(path) == {"g1": ["a"], "g2": []}


def test_run_refuses_an_existing_output_directory(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    with pytest.raises(FileExistsError):
        r.run(
            repo=tmp_path,
            dataset_dir=tmp_path,
            out_dir=out,
            servers={},
            plan={},
            as_of=date(2026, 1, 1),
            k=20,
            warmup=0,
            measured=1,
            seed=1,
            purpose="x",
        )


def test_with_user_rewrites_only_the_credentials():
    assert r._with_user("postgresql://admin:pw@localhost:5433/medops", "medops_app_user", "p@ss") == (
        "postgresql://medops_app_user:p%40ss@localhost:5433/medops"
    )
