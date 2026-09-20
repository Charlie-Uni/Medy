"""Glossary builder (ADR-0008): TFDA rows become brand entries only when the brand occurs in the corpus
pages, synonyms are distinct and capped, curated abbreviations need abbreviation and expansion on one page,
and the result validates as a runtime Glossary with a content-addressed version."""

from __future__ import annotations

import importlib
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from medops.retrieval.rewrite import load_glossary


@pytest.fixture
def builder(monkeypatch):
    tooling = Path(__file__).resolve().parents[3] / "evals/glossary/tools"
    monkeypatch.syspath_prepend(str(tooling))
    return importlib.import_module("build_glossary")


PAGES = {
    "doc-a": {
        1: "美洛醣膜衣錠 衛署藥製字第 000001 號 用法用量。The Development Safety Update Report (DSUR) is annual.",
        2: "無關頁 葡萄糖",
    },
    "doc-b": {
        1: "Signal confirmation by the PRAC Rapporteur; the Pharmacovigilance Risk Assessment Committee decides."
    },
}
ROWS = [
    {
        "許可證字號": "衛署藥製字第000001號",
        "註銷狀態": "",
        "中文品名": "美洛醣膜衣錠",
        "英文品名": "MELOGLU F.C. TABLETS",
        "主成分略述": "METFORMIN HCL;;METFORMIN HCL;;meloglu f.c. tablets",
    },
    {
        "許可證字號": "衛署藥製字第000002號",
        "註銷狀態": "已註銷",
        "中文品名": "不在語料的藥",
        "英文品名": "ABSENT",
        "主成分略述": "X",
    },
    {
        "許可證字號": "衛署藥製字第000003號",
        "註銷狀態": "",
        "中文品名": "美洛醣膜衣錠",
        "英文品名": "DUPLICATE ROW",
        "主成分略述": "Y",
    },
]


def test_tfda_entries_are_anchored_by_licence_number_and_keep_distinct_capped_synonyms(builder):
    entries, stats = builder.tfda_entries(ROWS, PAGES)
    assert stats == {"rows": 3, "licence_numbers_in_pages": 1, "licences_in_corpus": 1, "entries": 2}
    brand, english = entries
    assert brand["term"] == "美洛醣膜衣錠" and brand["synonyms"] == ["MELOGLU F.C. TABLETS", "METFORMIN HCL"]
    assert english["term"] == "MELOGLU F.C. TABLETS" and english["synonyms"] == ["美洛醣膜衣錠", "METFORMIN HCL"]
    assert brand["evidence"] == [{"document_key": "doc-a", "page": 1}]
    assert builder._distinct("t", ["a", "A", "t", "b", "c", "d", "e", "f"]) == ["a", "b", "c", "d", "e"]


def test_abbreviations_are_kept_only_with_same_page_evidence(builder):
    curated = {
        "entries": [
            {"term": "DSUR", "expansion": "development safety update report"},
            {"term": "PRAC", "expansion": "Pharmacovigilance Risk Assessment Committee"},
            {"term": "PT", "expansion": "preferred term"},  # never defined in these pages
            {"term": "RAC", "expansion": "Risk Assessment Committee"},  # substring of PRAC, not a word -> rejected
        ]
    }
    kept, rejected = builder.abbreviation_entries(curated, PAGES)
    assert [(k["term"], k["evidence"]) for k in kept] == [
        ("DSUR", [{"document_key": "doc-a", "page": 1}]),
        ("PRAC", [{"document_key": "doc-b", "page": 1}]),
    ]
    assert [r["term"] for r in rejected] == ["PT", "RAC"]


def test_build_writes_a_validating_glossary_and_provenance(builder, tmp_path, monkeypatch):
    pages = tmp_path / "pages"
    corpus = {
        "documents": [
            {"document_key": "doc-a", "source_hash": "a" * 64},
            {"document_key": "doc-b", "source_hash": "b" * 64},
        ]
    }
    for key, hash_ in (("doc-a", "a" * 64), ("doc-b", "b" * 64)):
        (pages / hash_).mkdir(parents=True)
        for page, text in PAGES[key].items():
            (pages / hash_ / f"{page}.txt").write_text(text, encoding="utf-8")
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    zip_path = tmp_path / "tfda.zip"
    header = "許可證字號,註銷狀態,中文品名,英文品名,主成分略述\n"
    body = "".join(
        f"{r['許可證字號']},{r['註銷狀態']},{r['中文品名']},{r['英文品名']},{r['主成分略述']}\n" for r in ROWS
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("36_2.csv", ("﻿" + header + body).encode("utf-8"))
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps({"entries": [{"term": "DSUR", "expansion": "development safety update report"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(builder, "REPO", tmp_path)
    (tmp_path / "evals/glossary/sources").mkdir(parents=True)
    (tmp_path / "evals/glossary/sources/abbreviations_curated.json").write_text(
        curated.read_text(encoding="utf-8"), encoding="utf-8"
    )
    summary = builder.build(
        tfda_zip=zip_path,
        pages_dir=pages,
        corpus_path=corpus_path,
        out_dir=tmp_path / "out",
        built_on=date(2026, 9, 20),
    )
    assert summary["entries"] == {"total": 3, "brand": 2, "abbreviation": 1} and summary["rejected"] == []
    glossary = load_glossary(Path(summary["glossary"]))
    assert glossary.version.startswith("glossary-20260920-") and len(glossary.entries) == 3
    provenance = json.loads(Path(summary["provenance"]).read_text(encoding="utf-8"))
    assert provenance["sources"]["tfda"]["snapshot_sha256"] and provenance["sources"]["tfda"]["licence"].startswith(
        "政府資料開放授權"
    )
    assert "美洛醣膜衣錠" in json.dumps(provenance, ensure_ascii=False) and "無關頁" not in json.dumps(
        provenance, ensure_ascii=False
    )
    with pytest.raises(SystemExit, match="already exists"):
        builder.build(
            tfda_zip=zip_path,
            pages_dir=pages,
            corpus_path=corpus_path,
            out_dir=tmp_path / "out",
            built_on=date(2026, 9, 20),
        )
