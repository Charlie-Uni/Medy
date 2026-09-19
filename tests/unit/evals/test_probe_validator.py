import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from tests.unit.evals.fixture_builder import build, refreeze

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals" / "probe" / "precise_clause" / "schema"
EXAMPLES = REPO / "evals" / "probe" / "precise_clause" / "examples"


@pytest.fixture
def frozen(tmp_path):
    pages = tmp_path / "pages"
    version = build(tmp_path / "data", pages)
    return version, pages


def _rules(report):
    return sorted({f.rule for f in report.errors})


def _rewrite_samples(version: Path, mutate):
    lines = (version / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    samples = [json.loads(line) for line in lines]
    mutate(samples)
    (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")


def test_synthetic_frozen_dataset_passes_all_rules(frozen):
    version, pages = frozen
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    assert report.passed, [f.__dict__ for f in report.errors]
    assert report.counts["samples"] == 72 and report.counts["per_language"]["zh-Hans"] == 24
    assert all(v >= 8 for v in report.counts["per_slice"].values())


def test_examples_directory_is_a_valid_draft_with_warnings_only(tmp_path):
    version = tmp_path / "draft"
    version.mkdir()
    for src, dst in (
        ("manifest.example.json", "manifest.json"),
        ("corpus.example.json", "corpus.json"),
        ("samples.example.jsonl", "samples.jsonl"),
        ("review_prompt.example.md", "review_prompt.md"),
    ):
        (version / dst).write_bytes((EXAMPLES / src).read_bytes())
    report = ProbeSetValidator(SCHEMA_DIR).validate(version, mode="draft")
    assert report.passed, [f.__dict__ for f in report.errors]
    warned = {f.rule for f in report.findings if f.level == "warning"}
    assert {"PR-03", "PR-04", "PR-05"} <= warned


def test_draft_examples_fail_when_frozen_mode_is_requested(tmp_path):
    version = tmp_path / "draft"
    version.mkdir()
    for src, dst in (
        ("manifest.example.json", "manifest.json"),
        ("corpus.example.json", "corpus.json"),
        ("samples.example.jsonl", "samples.jsonl"),
        ("review_prompt.example.md", "review_prompt.md"),
    ):
        (version / dst).write_bytes((EXAMPLES / src).read_bytes())
    report = ProbeSetValidator(SCHEMA_DIR).validate(version, mode="frozen")
    assert {"PR-03", "PR-05", "PR-10"} <= set(_rules(report))


def test_duplicate_key_text_on_page_is_rejected(frozen):
    version, pages = frozen
    sample = json.loads((version / "samples.jsonl").read_text(encoding="utf-8").splitlines()[0])
    gold = sample["required_gold_evidence"][0]
    page_file = pages / gold["source_hash"] / f"{gold['page']}.txt"
    page_file.write_text(page_file.read_text(encoding="utf-8") + f"\n重复 {gold['key_text']} 出现\n", encoding="utf-8")
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    assert "PR-05" in _rules(report)


def test_tampered_sha256sums_and_stale_counts_are_rejected(frozen):
    version, pages = frozen
    sums = (version / "SHA256SUMS").read_text(encoding="utf-8")
    (version / "SHA256SUMS").write_text(sums.replace(sums[:1], "f" if sums[0] != "f" else "e", 1), encoding="utf-8")
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    assert "PR-10" in _rules(report)


def test_dept_mismatch_query_equals_key_and_pii_are_rejected(frozen):
    version, pages = frozen

    def mutate(samples):
        samples[0]["dept"] = "CO" if samples[0]["dept"] != "CO" else "MA"  # PR-06 (and PR-03 counts drift)
        samples[1]["query"] = samples[1]["required_gold_evidence"][0]["key_text"]  # PR-08
        samples[2]["notes"] = "联系 13812345678"  # PR-07

    _rewrite_samples(version, mutate)
    refreeze(version)
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    assert {"PR-06", "PR-07", "PR-08"} <= set(_rules(report))


def test_missing_mapping_entry_and_bad_prompt_hash_are_rejected(frozen):
    version, pages = frozen
    mapping_path = next((version / "mappings").glob("*.json"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["entries"].pop()
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False) + "\n", encoding="utf-8")
    (version / "review_prompt.md").write_bytes(b"changed prompt\n")
    refreeze(version)  # hashes consistent again, but reviewers.prompt_hash is now stale
    report = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages)).validate(version, mode="frozen")
    assert {"PR-09", "PR-12"} <= set(_rules(report))


def test_cli_returns_nonzero_on_failure(frozen, capsys):
    from medops.evals.probe.__main__ import main

    version, pages = frozen
    assert main([str(version), "--mode", "frozen", "--pages", str(pages), "--schema-dir", str(SCHEMA_DIR)]) == 0
    (version / "review_prompt.md").write_bytes(b"tampered\n")
    assert main([str(version), "--mode", "frozen", "--pages", str(pages), "--schema-dir", str(SCHEMA_DIR)]) == 1
    assert "FAIL" in capsys.readouterr().out
