"""Gold hits require one exact source/version/page span, not text or combined fragments."""

from __future__ import annotations

import copy
import json
import os

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from medops.core.canonical import canonical_json
from medops.evals.probe import chunk_mapping as mapper
from medops.retrieval.lexical.normalization import normalize_text
from tests.unit.evals.fixture_builder import build, refreeze

STAMP = "2026-09-20T00:00:00Z"


@pytest.fixture
def frozen_export(tmp_path):
    pages = tmp_path / "pages"
    version = build(tmp_path / "data", pages)
    manifest = json.loads((version / "manifest.json").read_text())
    corpus = json.loads((version / "corpus.json").read_text())
    samples = [json.loads(line) for line in (version / "samples.jsonl").read_text().splitlines()]
    snapshot = {
        "chunker_version": "fixture-chunker-1",
        "normalization": "norm-v1",
        "extraction": {k: manifest["extraction"][k] for k in ("extractor", "extractor_version", "params_hash")},
        "chunks": [
            {
                "chunk_id": f"{doc['document_key']}-page-{page}",
                "source_hash": doc["source_hash"],
                "version_label": doc["version_label"],
                "spans": [
                    {
                        "page": page,
                        "char_start": 0,
                        "char_end": len(normalize_text((pages / doc["source_hash"] / f"{page}.txt").read_text())),
                    }
                ],
            }
            for doc in corpus["documents"]
            for page in range(1, doc["pages"] + 1)
        ],
    }
    return version, pages, snapshot, samples


def result(case):
    version, pages, snapshot, _ = case
    return mapper.build_mapping(version, pages, snapshot, generated_at=STAMP)


def first_entry(mapping):
    return next(entry for entry in mapping["entries"] if entry["gold_id"] == "pc-0001-g1")


def first_key(case):
    _, pages, _, samples = case
    gold = samples[0]["required_gold_evidence"][0]
    text = normalize_text((pages / gold["source_hash"] / f"{gold['page']}.txt").read_text())
    start = text.index(gold["key_text"])
    return gold, text, start, start + len(gold["key_text"])


def test_complete_mapping_is_schema_valid_and_bound_to_frozen_versions(frozen_export):
    version, _, snapshot, _ = frozen_export
    before = {p.name: p.read_bytes() for p in version.iterdir() if p.is_file()}
    mapping = result(frozen_export)
    manifest = json.loads((version / "manifest.json").read_text())
    assert mapping["dataset_hash"] == manifest["dataset_hash"]
    assert mapping["dataset_version"] == manifest["dataset_version"]
    assert mapping["chunker_version"] == snapshot["chunker_version"]
    assert mapping["extraction"] == snapshot["extraction"]
    assert mapping["normalization"] == snapshot["normalization"]
    assert len(mapping["entries"]) == 72
    assert all(entry["status"] == "mapped" and entry["reason"] is None for entry in mapping["entries"])
    schema = json.loads((mapper.SCHEMA_DIR / "chunk_mapping.schema.json").read_text())
    assert not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(mapping))
    assert before == {p.name: p.read_bytes() for p in version.iterdir() if p.is_file()}


def test_key_coverage_uses_unicode_positions_and_does_not_require_full_evidence_span(frozen_export):
    gold, text, start, end = first_key(frozen_export)
    assert len(text[:start].encode("utf-8")) != start
    assert gold["evidence_span"]["char_start"] < start
    frozen_export[2]["chunks"][0]["spans"] = [{"page": gold["page"], "char_start": start, "char_end": end}]
    assert first_entry(result(frozen_export))["status"] == "mapped"


@pytest.mark.parametrize("field,value", [("source_hash", "f" * 64), ("version_label", "another-version")])
def test_matching_coordinates_from_wrong_source_or_version_are_misses(frozen_export, field, value):
    frozen_export[2]["chunks"][0][field] = value
    entry = first_entry(result(frozen_export))
    assert entry["status"] == "unmappable" and entry["chunk_ids"] == []
    assert "miss" in entry["reason"]


def test_text_on_another_page_cannot_substitute_for_gold_page_coverage(frozen_export):
    gold, _, _, _ = first_key(frozen_export)
    _, pages, snapshot, _ = frozen_export
    page2 = pages / gold["source_hash"] / "2.txt"
    text = normalize_text(page2.read_text()) + " " + gold["key_text"]
    page2.write_text(text)
    assert gold["key_text"] in text
    snapshot["chunks"][0]["spans"] = [{"page": 2, "char_start": 0, "char_end": len(text)}]
    assert first_entry(result(frozen_export))["status"] == "unmappable"


def test_cross_page_chunk_hits_only_through_its_gold_page_fragment(frozen_export):
    gold, _, start, end = first_key(frozen_export)
    chunk = frozen_export[2]["chunks"][0]
    chunk["spans"] = [
        {"page": 2, "char_start": 0, "char_end": 5},
        {"page": gold["page"], "char_start": start, "char_end": end},
    ]
    assert first_entry(result(frozen_export))["chunk_ids"] == [chunk["chunk_id"]]


def test_two_adjacent_spans_cannot_be_joined_to_cover_the_key(frozen_export):
    gold, text, start, end = first_key(frozen_export)
    middle = start + 2
    assert middle < end
    frozen_export[2]["chunks"][0]["spans"] = [
        {"page": gold["page"], "char_start": 0, "char_end": middle},
        {"page": gold["page"], "char_start": middle, "char_end": len(text)},
    ]
    assert first_entry(result(frozen_export))["status"] == "unmappable"


@pytest.mark.parametrize("start_delta,end_delta", [(1, 0), (0, -1)])
def test_partial_key_overlap_is_not_a_hit(frozen_export, start_delta, end_delta):
    gold, _, start, end = first_key(frozen_export)
    frozen_export[2]["chunks"][0]["spans"] = [
        {"page": gold["page"], "char_start": start + start_delta, "char_end": end + end_delta},
    ]
    assert first_entry(result(frozen_export))["status"] == "unmappable"


def test_multiple_matching_chunks_are_deduplicated_and_stably_sorted(frozen_export):
    snapshot = frozen_export[2]
    extra = copy.deepcopy(snapshot["chunks"][0])
    extra["chunk_id"] = "aaa-extra-chunk"
    # Two different covering spans in one chunk do not duplicate its id in the result.
    extra["spans"].append({**extra["spans"][0], "char_start": 1})
    snapshot["chunks"].append(extra)
    expected = result(frozen_export)
    snapshot["chunks"].reverse()
    assert result(frozen_export) == expected
    assert first_entry(expected)["chunk_ids"] == ["aaa-extra-chunk", "doc-01-page-1"]


def test_empty_chunk_export_produces_explicit_miss_for_every_gold(frozen_export):
    frozen_export[2]["chunks"] = []
    mapping = result(frozen_export)
    assert len(mapping["entries"]) == 72
    assert all(
        entry["status"] == "unmappable" and not entry["chunk_ids"] and entry["reason"] for entry in mapping["entries"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("extractor", "another-extractor"),
        ("extractor_version", "new-version"),
        ("params_hash", "f" * 64),
    ],
)
def test_extraction_metadata_mismatch_is_refused(frozen_export, field, value):
    frozen_export[2]["extraction"][field] = value
    with pytest.raises(mapper.MappingRefused, match="extraction differs"):
        result(frozen_export)


def test_normalization_mismatch_is_refused(frozen_export):
    frozen_export[2]["normalization"] = "norm-v2"
    with pytest.raises(mapper.MappingRefused, match="normalization differs"):
        result(frozen_export)


@pytest.mark.parametrize(
    "mutation", ["duplicate-id", "duplicate-span", "no-spans", "content", "bad-source", "empty-version"]
)
def test_malformed_or_ambiguous_chunk_exports_are_refused(frozen_export, mutation):
    snapshot = frozen_export[2]
    chunk = snapshot["chunks"][0]
    if mutation == "duplicate-id":
        snapshot["chunks"].append(copy.deepcopy(chunk))
    elif mutation == "duplicate-span":
        chunk["spans"].append(copy.deepcopy(chunk["spans"][0]))
    elif mutation == "no-spans":
        chunk["spans"] = []
    elif mutation == "content":
        chunk["content"] = frozen_export[3][0]["required_gold_evidence"][0]["key_text"]
    elif mutation == "bad-source":
        chunk["source_hash"] = "../source"
    else:
        chunk["version_label"] = " "
    with pytest.raises(mapper.MappingRefused):
        result(frozen_export)


@pytest.mark.parametrize(
    "field,value",
    [
        ("page", 0),
        ("page", 3),
        ("page", True),
        ("char_start", -1),
        ("char_start", 1.5),
        ("char_end", 0),
        ("char_end", 100000),
    ],
)
def test_invalid_or_out_of_bounds_spans_are_refused(frozen_export, field, value):
    frozen_export[2]["chunks"][0]["spans"][0][field] = value
    with pytest.raises(mapper.MappingRefused):
        result(frozen_export)


@pytest.mark.parametrize("mutation", ["missing-page", "duplicate-key", "stale-evidence", "tampered-samples", "draft"])
def test_invalid_gold_or_unfrozen_inputs_cannot_be_mapped(frozen_export, mutation):
    version, pages, _, _ = frozen_export
    gold, text, _, _ = first_key(frozen_export)
    page = pages / gold["source_hash"] / f"{gold['page']}.txt"
    if mutation == "missing-page":
        page.unlink()
    elif mutation == "duplicate-key":
        page.write_text(text + " " + gold["key_text"])
    elif mutation == "stale-evidence":
        page.write_text("changed prefix " + text)
    elif mutation == "tampered-samples":
        path = version / "samples.jsonl"
        path.write_text(path.read_text().replace("查询", "changed-query", 1) + "\n")
    else:
        manifest = json.loads((version / "manifest.json").read_text())
        manifest.update(status="draft", frozen_at=None, dataset_hash=None)
        (version / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(mapper.MappingRefused, match="frozen probe validation failed"):
        result(frozen_export)


def test_overlapping_key_occurrences_are_not_treated_as_unique(frozen_export):
    version, pages, snapshot, samples = frozen_export
    gold = samples[-1]["required_gold_evidence"][0]
    page = pages / gold["source_hash"] / f"{gold['page']}.txt"
    old = gold["evidence_span"]["text"]
    new = "aaab"
    page.write_text(normalize_text(page.read_text()).replace(old, new))
    gold["key_text"] = "aa"
    gold["evidence_span"].update(text=new, char_end=gold["evidence_span"]["char_start"] + len(new))
    snapshot["chunks"][-1]["spans"][0]["char_end"] = len(normalize_text(page.read_text()))
    (version / "samples.jsonl").write_text("".join(canonical_json(s) + "\n" for s in samples))
    refreeze(version)
    with pytest.raises(mapper.MappingRefused, match="overlapping occurrences"):
        result(frozen_export)


@pytest.mark.parametrize("kind", ["inside", "symlink-inside", "existing", "dangling-symlink", "symlink-loop"])
def test_publication_refuses_frozen_paths_and_existing_targets(frozen_export, tmp_path, kind):
    version = frozen_export[0]
    out = tmp_path / "experiment/mapping.json"
    if kind == "inside":
        out = version / "new-mapping.json"
    elif kind == "symlink-inside":
        alias = tmp_path / "frozen-alias"
        alias.symlink_to(version, target_is_directory=True)
        out = alias / "new-mapping.json"
    elif kind == "existing":
        out.parent.mkdir()
        out.write_bytes(b"keep existing bytes")
    else:
        out.parent.mkdir()
        out.symlink_to(out if kind == "symlink-loop" else tmp_path / "absent-file")
    with pytest.raises(mapper.MappingRefused):
        mapper.publish_mapping({"test": True}, out, version_dir=version)
    if kind == "existing":
        assert out.read_bytes() == b"keep existing bytes"
    assert not (version / "new-mapping.json").exists()


def test_atomic_publication_never_replaces_a_concurrently_created_target(frozen_export, tmp_path, monkeypatch):
    out = tmp_path / "experiment/mapping.json"
    payload = {"complete": [1, 2, 3]}
    link = os.link

    def competing_writer(temporary, target, **kwargs):
        assert kwargs["src_dir_fd"] == kwargs["dst_dir_fd"]
        assert kwargs["follow_symlinks"] is False
        with os.fdopen(os.open(temporary, os.O_RDONLY, dir_fd=kwargs["src_dir_fd"]), "rb") as stream:
            assert stream.read() == (canonical_json(payload) + "\n").encode()
        assert target == out.name
        assert not out.exists()  # No partially written destination was exposed.
        out.write_bytes(b"other writer")
        link(temporary, target, **kwargs)

    monkeypatch.setattr(mapper.os, "link", competing_writer)
    with pytest.raises(FileExistsError):
        mapper.publish_mapping(payload, out, version_dir=frozen_export[0])
    assert out.read_bytes() == b"other writer"
    assert not list(out.parent.glob(".probe-artifact-*.tmp"))


def test_interrupted_write_cleans_temporary_file_without_publishing(frozen_export, tmp_path, monkeypatch):
    out = tmp_path / "experiment/mapping.json"

    def fail_fsync(fd):
        raise OSError("synthetic interrupted write")

    monkeypatch.setattr(mapper.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="interrupted write"):
        mapper.publish_mapping({"complete": True}, out, version_dir=frozen_export[0])
    assert not out.exists()
    assert not list(out.parent.glob(".probe-artifact-*.tmp"))


@pytest.mark.parametrize("stage", ["directory-open", "mkdir", "temporary-open", "link", "cleanup"])
def test_parent_symlink_substitution_cannot_write_or_clean_inside_frozen_directory(tmp_path, monkeypatch, stage):
    """Deterministic interleavings reproduce swaps after resolve and after the FD is opened."""
    protected = tmp_path / "frozen"
    protected.mkdir()
    (protected / "manifest.json").write_bytes(b"frozen bytes")
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    parked = tmp_path / "original-experiment"
    out = experiment / ("new/mapping.json" if stage == "mkdir" else "mapping.json")
    swapped = False
    real_open, real_mkdir, real_link = os.open, os.mkdir, os.link

    def swap():
        nonlocal swapped
        assert not swapped
        experiment.rename(parked)
        experiment.symlink_to(protected, target_is_directory=True)
        swapped = True

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        if not swapped and (
            (stage == "directory-open" and path == "experiment")
            or (stage == "temporary-open" and str(path).startswith(".probe-artifact-"))
        ):
            swap()
        return real_open(path, flags, mode, dir_fd=dir_fd)

    def racing_mkdir(path, mode=0o777, *, dir_fd=None):
        if stage == "mkdir" and path == "new" and not swapped:
            swap()
        return real_mkdir(path, mode, dir_fd=dir_fd)

    def racing_link(source, target, **kwargs):
        if stage == "link":
            swap()
        return real_link(source, target, **kwargs)

    def interrupted_write(fd):
        swap()
        raise OSError("interrupted after directory swap")

    monkeypatch.setattr(mapper.os, "open", racing_open)
    monkeypatch.setattr(mapper.os, "mkdir", racing_mkdir)
    monkeypatch.setattr(mapper.os, "link", racing_link)
    if stage == "cleanup":
        monkeypatch.setattr(mapper.os, "fsync", interrupted_write)
    with pytest.raises((OSError, mapper.MappingRefused)):
        mapper.publish_artifact(b"complete artifact\n", out, protected_dir=protected)
    assert swapped
    assert [(p.name, p.read_bytes()) for p in protected.iterdir()] == [("manifest.json", b"frozen bytes")]
    assert not list(parked.rglob("*.tmp"))
    assert not list(parked.rglob("mapping.json"))


def test_opened_directory_ancestry_detects_move_into_protected_directory(tmp_path, monkeypatch):
    protected = tmp_path / "frozen"
    protected.mkdir()
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    moved = protected / "moved-experiment"
    real_fsync = os.fsync

    def move_directory(fd):
        real_fsync(fd)
        experiment.rename(moved)

    monkeypatch.setattr(mapper.os, "fsync", move_directory)
    with pytest.raises(mapper.MappingRefused, match="inside the protected directory"):
        mapper.publish_artifact(b"complete artifact\n", experiment / "mapping.json", protected_dir=protected)
    assert not list(moved.iterdir())


def test_shared_artifact_publisher_creates_exact_bytes_with_nested_parent(tmp_path):
    protected = tmp_path / "frozen"
    protected.mkdir()
    out = tmp_path / "experiment/nested/export.json"
    raw = b'{"export":true}\n'
    mapper.publish_artifact(raw, out, protected_dir=protected)
    assert out.read_bytes() == raw
    assert list(out.parent.iterdir()) == [out]


@pytest.mark.parametrize("mode,exit_code", [("complete", 0), ("misses", 1), ("invalid", 2)])
def test_cli_distinguishes_complete_miss_artifact_and_invalid_input(frozen_export, tmp_path, capsys, mode, exit_code):
    version, pages, snapshot, _ = frozen_export
    if mode == "misses":
        snapshot["chunks"] = []
    elif mode == "invalid":
        snapshot["normalization"] = "wrong-version"
    source = tmp_path / "chunks.json"
    source.write_text(json.dumps(snapshot))
    out = tmp_path / "experiment/chunk_mapping.json"
    before = {p.name: p.read_bytes() for p in version.iterdir() if p.is_file()}
    assert mapper.main([str(version), "--pages", str(pages), "--chunks", str(source), "--out", str(out)]) == exit_code
    output = capsys.readouterr()
    if mode == "invalid":
        assert not out.exists() and "REFUSED" in output.err
    else:
        mapping = json.loads(out.read_text())
        assert len(mapping["entries"]) == 72
        assert ("MISS pc-0001-g1" in output.out) == (mode == "misses")
    assert before == {p.name: p.read_bytes() for p in version.iterdir() if p.is_file()}


def test_cli_duplicate_json_keys_are_rejected_without_output(frozen_export, tmp_path, capsys):
    version, pages, _, _ = frozen_export
    source = tmp_path / "chunks.json"
    source.write_text('{"chunks":[],"chunks":[]}')
    out = tmp_path / "experiment/mapping.json"
    assert mapper.main([str(version), "--pages", str(pages), "--chunks", str(source), "--out", str(out)]) == 2
    assert "duplicate JSON" in capsys.readouterr().err
    assert not out.exists()
