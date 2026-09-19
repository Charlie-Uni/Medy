"""Institutional email decisions exempt only the exact independently approved hit."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe.pii import find_pii_matches, find_pii_spans
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from medops.retrieval.lexical.normalization import normalize_text
from tests.unit.evals.fixture_builder import build, refreeze

SCHEMAS = Path(__file__).resolve().parents[3] / "evals/probe/precise_clause/schema"
EMAIL = "public-office@example.org"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def email_set(tmp_path):
    pages = tmp_path / "pages"
    version = build(tmp_path / "data", pages)
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    sample = samples[-1]  # Last clause on the page: appending does not shift other fixture offsets.
    gold = sample["required_gold_evidence"][0]
    page_path = pages / gold["source_hash"] / f"{gold['page']}.txt"
    old = gold["evidence_span"]["text"]
    text = normalize_text(old + f" 机构联系 {EMAIL}")
    gold["evidence_span"].update(text=text, char_end=gold["evidence_span"]["char_start"] + len(text))
    page_path.write_text(normalize_text(page_path.read_text()).replace(old, text), encoding="utf-8")
    approval = tmp_path / "docs/reviews/synthetic-approval.md"
    approval.parent.mkdir(parents=True)
    approval.write_text("Synthetic human approval: this exact public institution contact is not personal data.\n")
    hit = find_pii_spans(text)[0]
    entry = {
        "sample_id": sample["sample_id"],
        "gold_id": gold["gold_id"],
        "source_hash": gold["source_hash"],
        "field": "evidence_span.text",
        "field_sha256": sha(text),
        "rule": hit[0],
        "match": hit[1],
        "char_start": hit[2],
        "char_end": hit[3],
        "human_review": {
            "reviewer_id": "annotator-01",
            "reviewed_at": "2026-09-01",
            "decision": "public_institutional_contact",
            "approval_record": "docs/reviews/synthetic-approval.md",
            "approval_record_sha256": hashlib.sha256(approval.read_bytes()).hexdigest(),
            "reason": "Synthetic reviewed public institution contact, not an individual identifier.",
        },
    }
    exceptions = {"dataset_version": "v1", "pii_ruleset_version": "pii-rules-v1", "exceptions": [entry]}
    return version, pages, tmp_path, samples, exceptions


def publish(case, *, exceptions=True):
    version, _, _, samples, document = case
    (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples), encoding="utf-8")
    if exceptions:
        (version / "pii_exceptions.json").write_text(canonical_json(document) + "\n", encoding="utf-8")
    refreeze(version)


def run(case, mode="frozen"):
    version, pages, root, _, _ = case
    return ProbeSetValidator(SCHEMAS, PageTextProvider(pages), approval_records_root=root).validate(version, mode=mode)


def errors(report, rule="PR-07"):
    return [finding for finding in report.errors if finding.rule == rule]


def change_span(case, text):
    _, pages, _, samples, _ = case
    gold = samples[-1]["required_gold_evidence"][0]
    old = gold["evidence_span"]["text"]
    gold["evidence_span"].update(text=text, char_end=gold["evidence_span"]["char_start"] + len(text))
    page = pages / gold["source_hash"] / f"{gold['page']}.txt"
    page.write_text(page.read_text().replace(old, text), encoding="utf-8")


@pytest.mark.parametrize("mode", ["draft", "frozen"])
def test_exact_reviewed_hit_passes_and_is_frozen(email_set, mode):
    publish(email_set)
    report = run(email_set, mode)
    assert report.passed, [f.__dict__ for f in report.errors]
    assert "pii_exceptions.json" in (email_set[0] / "SHA256SUMS").read_text()


def test_without_explicit_exception_notes_do_not_authorize_an_email(email_set):
    email_set[3][-1]["notes"] = "Human reviewed: all institution contacts are allowed."
    publish(email_set, exceptions=False)
    report = run(email_set)
    assert len(errors(report)) == 1
    assert EMAIL not in str(report.to_dict())  # Findings do not repeat possibly sensitive matching text.


@pytest.mark.parametrize(
    "field,value",
    [
        ("sample_id", "pc-9999"),
        ("gold_id", "pc-0072-g2"),
        ("source_hash", "f" * 64),
        ("field", "key_text"),
        ("field_sha256", "f" * 64),
        ("match", "another-office@example.org"),
        ("char_start", 0),
        ("char_end", 1),
    ],
)
def test_every_binding_must_match_a_current_hit(email_set, field, value):
    email_set[4]["exceptions"][0][field] = value
    publish(email_set)
    findings = errors(run(email_set))
    assert any("without an exact reviewed exception" in f.message for f in findings)
    assert any("unused or stale" in f.message for f in findings)


def test_field_edit_away_from_email_invalidates_approval(email_set):
    text = email_set[3][-1]["required_gold_evidence"][0]["evidence_span"]["text"]
    change_span(email_set, text + " changed context")
    publish(email_set)
    assert any("unused or stale" in f.message for f in errors(run(email_set)))


@pytest.mark.parametrize("suffix", [f" and {EMAIL}", " and second-office@example.org", " 13812345678"])
def test_other_hits_in_same_field_remain_rejected(email_set, suffix):
    text = email_set[3][-1]["required_gold_evidence"][0]["evidence_span"]["text"] + suffix
    change_span(email_set, text)
    email_set[4]["exceptions"][0]["field_sha256"] = sha(text)
    publish(email_set)
    assert len(errors(run(email_set))) == 1


@pytest.mark.parametrize("field", ["query", "notes"])
def test_same_email_in_query_or_notes_is_not_covered(email_set, field):
    email_set[3][-1][field] += " " + EMAIL
    publish(email_set)
    assert any(f.location.endswith("/" + field) for f in errors(run(email_set)))


def test_key_and_span_require_independent_approvals(email_set):
    email_set[3][-1]["required_gold_evidence"][0]["key_text"] = EMAIL
    publish(email_set)
    assert len(errors(run(email_set))) == 1
    entry = copy.deepcopy(email_set[4]["exceptions"][0])
    entry.update(field="key_text", field_sha256=sha(EMAIL), char_start=0, char_end=len(EMAIL))
    email_set[4]["exceptions"].append(entry)
    publish(email_set)
    report = run(email_set)
    assert report.passed, report.to_dict()


def test_unicode_positions_are_character_not_byte_offsets(email_set):
    entry = email_set[4]["exceptions"][0]
    text = email_set[3][-1]["required_gold_evidence"][0]["evidence_span"]["text"]
    start = len(text[: entry["char_start"]].encode("utf-8"))
    assert start != entry["char_start"]
    entry.update(char_start=start, char_end=start + len(EMAIL))
    publish(email_set)
    assert errors(run(email_set))


def test_duplicate_identity_is_rejected_even_if_other_binding_is_different(email_set):
    duplicate = copy.deepcopy(email_set[4]["exceptions"][0])
    duplicate["field_sha256"] = "f" * 64
    email_set[4]["exceptions"].append(duplicate)
    publish(email_set)
    assert any("duplicate PII exception" in f.message for f in errors(run(email_set)))


@pytest.mark.parametrize("field,value", [("dataset_version", "v2"), ("pii_ruleset_version", "pii-rules-v2")])
def test_dataset_or_rule_version_must_match(email_set, field, value):
    email_set[4][field] = value
    publish(email_set)
    assert run(email_set).errors


@pytest.mark.parametrize(
    "field,value",
    [
        ("field", "query"),
        ("field", "notes"),
        ("rule", "cn_mobile"),
        ("rule", "patient_identifier"),
        ("extra", True),
    ],
)
def test_unsupported_exception_shapes_are_not_accepted(email_set, field, value):
    email_set[4]["exceptions"][0][field] = value
    publish(email_set)
    assert errors(run(email_set), "PR-01")


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_id", "reviewer-llm-01"),
        ("reviewed_at", "2026-09-03"),
        ("reviewed_at", "not-a-date"),
        ("reviewed_at", "2999-01-01"),
        ("reason", "          "),
        ("reason", "Additional personal contact 13812345678"),
        ("decision", "allow-all-emails"),
    ],
)
def test_human_approval_is_required_and_scoped(email_set, field, value):
    email_set[4]["exceptions"][0]["human_review"][field] = value
    publish(email_set)
    assert run(email_set).errors


@pytest.mark.parametrize("operation", ["delete", "alter", "directory", "external-symlink", "symlink-loop"])
def test_missing_or_changed_approval_record_cannot_authorize(email_set, operation):
    _, _, root, _, exceptions = email_set
    record = root / exceptions["exceptions"][0]["human_review"]["approval_record"]
    if operation == "alter":
        record.write_text("Replaced approval statement")
    else:
        original = record.read_bytes()
        record.unlink()
        if operation == "directory":
            record.mkdir()
        elif operation == "symlink-loop":
            record.symlink_to(record)
        elif operation == "external-symlink":
            external = root.parent / "outside-approval.md"
            external.write_bytes(original)
            record.symlink_to(external)
    publish(email_set)
    assert errors(run(email_set))


@pytest.mark.parametrize(
    "path", ["../approval.md", "/tmp/approval.md", "docs/reviews/../approval.md", "docs\\reviews\\approval.md"]
)
def test_approval_paths_cannot_escape_the_explicit_root(email_set, path):
    email_set[4]["exceptions"][0]["human_review"]["approval_record"] = path
    publish(email_set)
    assert errors(run(email_set), "PR-01")


@pytest.mark.parametrize("operation", ["missing", "wrong-hash", "duplicate", "missing-file"])
def test_manifest_binding_is_checked_even_in_draft(email_set, operation):
    publish(email_set)
    version = email_set[0]
    manifest = json.loads((version / "manifest.json").read_text())
    entry = next(f for f in manifest["files"] if f["path"] == "pii_exceptions.json")
    if operation == "missing":
        manifest["files"].remove(entry)
    elif operation == "wrong-hash":
        entry["sha256"] = "f" * 64
    elif operation == "duplicate":
        manifest["files"].append({**entry, "sha256": "f" * 64})
    else:
        (version / "pii_exceptions.json").unlink()
    (version / "manifest.json").write_text(json.dumps(manifest))
    assert run(email_set, "draft").errors


def test_exception_must_also_be_bound_in_sha256sums(email_set):
    publish(email_set)
    version = email_set[0]
    sums = (version / "SHA256SUMS").read_text()
    (version / "SHA256SUMS").write_text(
        "\n".join(line for line in sums.splitlines() if "pii_exceptions.json" not in line) + "\n"
    )
    assert errors(run(email_set), "PR-10")


def test_duplicate_json_properties_are_rejected(email_set):
    publish(email_set)
    path = email_set[0] / "pii_exceptions.json"
    path.write_text(path.read_text().replace('"dataset_version":"v1"', '"dataset_version":"v1","dataset_version":"v1"'))
    refreeze(email_set[0])
    assert any("duplicate JSON property" in f.message for f in errors(run(email_set), "PR-01"))


def test_null_exception_document_is_not_treated_as_absent(email_set):
    publish(email_set)
    (email_set[0] / "pii_exceptions.json").write_text("null\n")
    refreeze(email_set[0])
    assert errors(run(email_set), "PR-01")


@pytest.mark.parametrize("mutation", ["invalid-field", "unknown-property", "duplicate-property"])
def test_invalid_exception_report_never_echoes_sensitive_input(email_set, mutation):
    sensitive = "private-person@example.org"
    entry = email_set[4]["exceptions"][0]
    if mutation == "invalid-field":
        entry["field"] = sensitive
    else:
        entry[sensitive] = {"value": sensitive}
    publish(email_set)
    if mutation == "duplicate-property":
        path = email_set[0] / "pii_exceptions.json"
        path.write_text(path.read_text().replace('"sample_id":', f'"{sensitive}":0,"sample_id":'))
        refreeze(email_set[0])
    report = run(email_set)
    assert errors(report, "PR-01")
    assert sensitive not in str(report.to_dict())


def test_exception_gold_id_schema_matches_existing_sample_contract():
    sample = json.loads((SCHEMAS / "probe_sample.schema.json").read_text())
    exception = json.loads((SCHEMAS / "pii_exceptions.schema.json").read_text())
    assert (
        exception["properties"]["exceptions"]["items"]["properties"]["gold_id"]["pattern"]
        == sample["$defs"]["goldEvidence"]["properties"]["gold_id"]["pattern"]
    )


def test_existing_ingestion_match_api_still_returns_pairs():
    assert find_pii_matches(EMAIL) == [("email", EMAIL)]
    assert find_pii_spans(EMAIL) == [("email", EMAIL, 0, len(EMAIL))]
