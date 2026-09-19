"""Regression tests for the frozen-mode gaps found in review (2026-09-10)."""

import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from tests.unit.evals.fixture_builder import build, refreeze

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals" / "probe" / "precise_clause" / "schema"


@pytest.fixture
def frozen(tmp_path):
    pages = tmp_path / "pages"
    return build(tmp_path / "data", pages), pages


def _run(version, pages=None, mode="frozen"):
    return ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages) if pages else None).validate(version, mode=mode)


def _errors(report, rule):
    return [f for f in report.errors if f.rule == rule]


def _edit_samples(version: Path, mutate):
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text(encoding="utf-8").splitlines()]
    mutate(samples)
    (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")


def _edit_corpus(version: Path, mutate):
    corpus = json.loads((version / "corpus.json").read_text(encoding="utf-8"))
    mutate(corpus)
    (version / "corpus.json").write_text(canonical_json(corpus) + "\n", encoding="utf-8")


def _edit_manifest(version: Path, mutate):
    manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
    mutate(manifest)
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---- document index and cross-file relations ----------------------------------------------


def test_duplicate_source_hash_is_rejected(frozen):
    version, pages = frozen
    _edit_corpus(version, lambda c: c["documents"].append(dict(c["documents"][0], document_key="dup-doc")))
    refreeze(version)
    assert _errors(_run(version, pages), "PR-01")


def test_duplicate_document_key_is_rejected(frozen):
    version, pages = frozen
    _edit_corpus(version, lambda c: c["documents"][1].__setitem__("document_key", c["documents"][0]["document_key"]))
    refreeze(version)
    assert any("document_key" in f.message for f in _errors(_run(version, pages), "PR-01"))


def test_corpus_version_must_match_manifest(frozen):
    version, pages = frozen
    _edit_corpus(version, lambda c: c.__setitem__("dataset_version", "v2"))
    refreeze(version)
    assert any("dataset_version" in f.message for f in _errors(_run(version, pages), "PR-01"))


def test_gold_version_label_and_page_range_are_checked(frozen):
    version, pages = frozen

    def mutate(samples):
        samples[0]["required_gold_evidence"][0]["version_label"] = "v9"
        samples[1]["required_gold_evidence"][0]["page"] = 99

    _edit_samples(version, mutate)
    refreeze(version)
    messages = [f.message for f in _errors(_run(version, pages), "PR-04")]
    assert any("version_label" in m for m in messages) and any("exceeds document pages" in m for m in messages)


# ---- PR-10 --------------------------------------------------------------------------------


def test_sha256sums_duplicate_path_and_malformed_line_are_rejected(frozen):
    version, pages = frozen
    good = (version / "SHA256SUMS").read_text(encoding="utf-8")
    first = good.splitlines()[0]
    bad_first = ("f" if first[0] != "f" else "e") + first[1:]
    (version / "SHA256SUMS").write_text(bad_first + "\n" + good, encoding="utf-8")
    _edit_manifest(
        version,
        lambda m: m.__setitem__(
            "dataset_hash", __import__("hashlib").sha256((version / "SHA256SUMS").read_bytes()).hexdigest()
        ),
    )
    report = _run(version, pages)
    assert any("duplicate path" in f.message for f in _errors(report, "PR-10"))
    (version / "SHA256SUMS").write_text("not a sums line\n" + good, encoding="utf-8")
    assert any("malformed" in f.message for f in _errors(_run(version, pages), "PR-10"))


# ---- PR-12 --------------------------------------------------------------------------------


def test_mapping_extraction_and_normalization_must_match_manifest(frozen):
    version, pages = frozen
    path = next((version / "mappings").glob("*.json"))
    mapping = json.loads(path.read_text(encoding="utf-8"))
    mapping["extraction"]["extractor_version"] = "unrelated"
    path.write_text(json.dumps(mapping, ensure_ascii=False) + "\n", encoding="utf-8")
    assert any("extractor_version" in f.message for f in _errors(_run(version, pages), "PR-12"))


# ---- PR-05 without page texts ---------------------------------------------------------------


def test_page_independent_anchoring_checks_run_in_draft_without_pages(frozen):
    version, _ = frozen

    def mutate(samples):
        samples[0]["required_gold_evidence"][0]["evidence_span"]["char_end"] += 3  # bad offsets
        samples[1]["required_gold_evidence"][0]["key_text"] = "NOT-IN-SPAN"  # span lacks key

    _edit_samples(version, mutate)
    refreeze(version)
    report = _run(version, pages=None, mode="draft")
    errs = _errors(report, "PR-05")
    assert any("offsets" in f.message for f in errs) and any("does not contain key_text" in f.message for f in errs)
    assert any(f.rule == "PR-05" and f.level == "warning" and "not provided" in f.message for f in report.findings)


def test_missing_pages_is_only_a_warning_in_draft_but_error_in_frozen(frozen):
    version, _ = frozen
    _edit_manifest(version, lambda m: m.update(status="draft", frozen_at=None, dataset_hash=None))
    assert not _errors(_run(version, None, "draft"), "PR-05")
    assert _errors(_run(version, None, "frozen"), "PR-05")


# ---- PR-08 --------------------------------------------------------------------------------


def test_query_equal_to_another_samples_key_text_is_rejected(frozen):
    version, pages = frozen
    _edit_samples(version, lambda s: s[0].__setitem__("query", s[5]["required_gold_evidence"][0]["key_text"]))
    refreeze(version)
    assert _errors(_run(version, pages), "PR-08")


# ---- input handling ----------------------------------------------------------------------


def test_jsonl_without_trailing_newline_and_blank_lines_report_findings_not_exceptions(frozen):
    version, pages = frozen
    text = (version / "samples.jsonl").read_text(encoding="utf-8")
    (version / "samples.jsonl").write_text(text.rstrip("\n"), encoding="utf-8")
    refreeze(version)
    assert any("end with a newline" in f.message for f in _errors(_run(version, pages), "PR-01"))
    (version / "samples.jsonl").write_text(text.replace("\n", "\n\n", 1), encoding="utf-8")
    refreeze(version)
    assert any("blank line" in f.message for f in _errors(_run(version, pages), "PR-01"))


def test_non_canonical_jsonl_line_is_rejected(frozen):
    version, pages = frozen
    lines = (version / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    lines[0] = json.dumps(
        json.loads(lines[0]), ensure_ascii=False, indent=None, separators=(", ", ": "), sort_keys=True
    )
    (version / "samples.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    refreeze(version)
    assert any("canonical" in f.message for f in _errors(_run(version, pages), "PR-01"))


def test_acl_probe_ids_and_references_are_checked(frozen):
    version, pages = frozen
    probe = {
        "probe_id": "acl-0002",
        "requesting_dept": "PV",
        "query": "示意查询",
        "forbidden_source_hashes": ["a" * 64],
        "derived_from_sample": "pc-9999",
        "notes": "示意",
    }
    lines = [canonical_json(probe), canonical_json(dict(probe, probe_id="acl-0001"))]
    (version / "acl_probes.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    refreeze(version)
    report = _run(version, pages)
    assert any("not sorted" in f.message for f in _errors(report, "PR-02"))
    assert any("derived_from_sample" in f.message for f in _errors(report, "PR-02"))


def test_non_canonical_acl_probe_line_is_a_pr01_finding(frozen):
    version, pages = frozen
    probe = {
        "probe_id": "acl-0001",
        "requesting_dept": "PV",
        "query": "示意查询",
        "forbidden_source_hashes": ["a" * 64],
        "derived_from_sample": None,
        "notes": "示意",
    }
    (version / "acl_probes.jsonl").write_text(
        json.dumps(probe, ensure_ascii=False, indent=1).replace("\n", "") + "\n", encoding="utf-8"
    )
    refreeze(version)
    report = _run(version, pages)
    assert any("canonical" in f.message and f.location.startswith("acl_probes.jsonl") for f in _errors(report, "PR-01"))


def test_invalid_utf8_prompt_and_corrupt_manifest_report_findings(frozen):
    version, pages = frozen
    (version / "review_prompt.md").write_bytes(b"\xff\xfe bad bytes\n")
    refreeze(version)
    assert any("not valid UTF-8" in f.message for f in _errors(_run(version, pages), "PR-09"))
    (version / "manifest.json").write_text("{not json", encoding="utf-8")
    report = _run(version, pages)
    assert any("invalid JSON" in f.message and f.location.startswith("manifest.json") for f in _errors(report, "PR-01"))


def test_unmodified_fixture_still_passes(frozen):
    version, pages = frozen
    report = _run(version, pages)
    assert report.passed, [f.__dict__ for f in report.errors]
