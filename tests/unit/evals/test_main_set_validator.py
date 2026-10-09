"""spec-m1 rules of the shared validator on a synthetic main-set fixture (evals/main_set/SPEC.md sections 2-4)."""

import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from tests.unit.evals.fixture_builder import refreeze
from tests.unit.evals.fixture_builder_main import build_main

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals" / "main_set" / "schema"


@pytest.fixture
def frozen(tmp_path):
    pages = tmp_path / "pages"
    version = build_main(tmp_path / "repo", pages)
    return version, pages, tmp_path / "repo"


def _validator(pages, root):
    return ProbeSetValidator(SCHEMA_DIR, PageTextProvider(pages), approval_records_root=root)


def _rules(report):
    return sorted({f.rule for f in report.errors})


def _rewrite(version: Path, mutate, *, manifest=False):
    if manifest:
        m = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
        mutate(m)
        (version / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        samples = [json.loads(line) for line in (version / "samples.jsonl").read_text(encoding="utf-8").splitlines()]
        mutate(samples)
        (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")
    refreeze(version)


def test_synthetic_main_set_passes_frozen_validation(frozen):
    version, pages, root = frozen
    report = _validator(pages, root).validate(version, mode="frozen")
    assert report.passed, [f.__dict__ for f in report.errors][:10]
    c = report.counts
    assert c["imported"] == 72 and c["no_answer"] == 40 and c["answerable"] >= 300 and c["conflict"] >= 20
    assert all(v >= 20 for v in c["per_slice"].values()) and all(v >= 60 for v in c["per_dept"].values())
    assert c["per_language"]["zh-Hant"] >= 80 and c["per_language"]["en"] >= 150 and c["per_language"]["zh-Hans"] >= 20


def test_probe_schema_dir_rejects_the_main_set_and_vice_versa(frozen):
    version, pages, root = frozen
    probe_schema = REPO / "evals" / "probe" / "precise_clause" / "schema"
    report = ProbeSetValidator(probe_schema, PageTextProvider(pages), approval_records_root=root).validate(version)
    assert "PR-01" in _rules(report)


def test_pr16_imported_samples_must_be_byte_identical(frozen):
    version, pages, root = frozen

    def edit(samples):
        s = next(x for x in samples if x["sample_id"] == "pc-0001")
        s["notes"] = "changed after the probe freeze"

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-16" in _rules(report)


def test_pr16_detects_a_changed_probe_file(frozen):
    version, pages, root = frozen
    probe = root / "evals/probe/precise_clause/v1/samples.jsonl"
    probe.write_bytes(probe.read_bytes() + b"\n")
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-16" in _rules(report)


def test_pr09_imported_samples_keep_the_probe_reviewer_binding(frozen):
    version, pages, root = frozen

    def edit(m):
        m["imported_samples"]["prompt_hash"] = "0" * 64

    _rewrite(version, edit, manifest=True)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-09" in _rules(report)


def test_pr16_imported_prompt_hash_set_must_cover_probe_sample_bindings(frozen):
    version, pages, root = frozen

    def edit(m):
        m["imported_samples"]["prompt_hashes"] = ["0" * 64]

    _rewrite(version, edit, manifest=True)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-16" in _rules(report)


def test_pr17_no_answer_scope_must_be_a_corpus_document(frozen):
    version, pages, root = frozen

    def edit(samples):
        s = next(x for x in samples if x.get("answerable") is False)
        s["abstention"]["scope_document_key"] = "no-such-doc"

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-17" in _rules(report)


def test_schema_rejects_gold_on_a_no_answer_sample(frozen):
    version, pages, root = frozen

    def edit(samples):
        s = next(x for x in samples if x.get("answerable") is False)
        donor = next(x for x in samples if x["sample_id"].startswith("ms-") and x["required_gold_evidence"])
        s["required_gold_evidence"] = [dict(donor["required_gold_evidence"][0], gold_id=f"{s['sample_id']}-g1")]

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-01" in _rules(report)


def test_pr18_conflict_gold_must_lie_in_the_current_version(frozen):
    version, pages, root = frozen

    def edit(samples):
        s = next(x for x in samples if x.get("conflict") and not x.get("derived_from"))
        other = next(
            x
            for x in samples
            if x["sample_id"].startswith("ms-") and not x.get("conflict") and x["required_gold_evidence"]
        )
        s["required_gold_evidence"] = [dict(other["required_gold_evidence"][0], gold_id=f"{s['sample_id']}-g1")]

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-18" in _rules(report)


def test_pr18_conflict_family_must_match_a_registered_fixture(frozen):
    version, pages, root = frozen

    def edit(m):
        m["conflict_fixtures"] = m["conflict_fixtures"][:1]

    _rewrite(version, edit, manifest=True)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-18" in _rules(report)


def test_pr19_long_context_slice_is_mechanical(frozen):
    version, pages, root = frozen

    def edit(samples):
        s = next(
            x for x in samples if "long_context" in x["slices"] and not x.get("derived_from") and not x.get("conflict")
        )
        s["slices"] = [sl for sl in s["slices"] if sl != "long_context"]
        twin = next((x for x in samples if x.get("derived_from") == s["sample_id"]), None)
        if twin:
            twin["slices"] = list(s["slices"])

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-19" in _rules(report)


def test_pr04_cap_comes_from_the_manifest(frozen):
    version, pages, root = frozen

    def edit(samples):
        # a ninth non-derived sample on a document that already carries eight
        s = next(x for x in samples if x["sample_id"] == "ms-0001")
        extra = json.loads(json.dumps(s))
        extra["sample_id"] = "ms-9999"
        extra["query"] = "主集文档13的第九条是什么"
        extra["required_gold_evidence"][0]["gold_id"] = "ms-9999-g1"
        samples.append(extra)

    _rewrite(version, edit)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-04" in _rules(report)
    assert any("> 8" in f.message for f in report.errors if f.rule == "PR-04")


def test_pending_second_human_review_forces_a_provisional_version(frozen):
    version, pages, root = frozen

    def edit(m):
        m["dataset_version"] = "main-v1"

    _rewrite(version, edit, manifest=True)
    corpus = json.loads((version / "corpus.json").read_text(encoding="utf-8"))
    corpus["dataset_version"] = "main-v1"
    (version / "corpus.json").write_text(canonical_json(corpus) + "\n", encoding="utf-8")
    refreeze(version)
    report = _validator(pages, root).validate(version, mode="frozen")
    assert "PR-01" in _rules(report)
