"""Draft-only canonical JSONL rewrite (M1-01 companion tool): repairs representation, preserves records,
refuses frozen directories and anything that is not a representation problem."""

import hashlib
import json
from pathlib import Path

import pytest

from medops.core.canonical import canonical_json
from medops.evals.probe.canonicalize import (
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_VALIDATION_FAILED,
    RefusedError,
    canonicalize,
    main,
)
from tests.unit.evals.fixture_builder import build

REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals" / "probe" / "precise_clause" / "schema"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(version: Path) -> dict[str, str]:
    return {p.relative_to(version).as_posix(): _sha(p) for p in version.rglob("*") if p.is_file()}


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").split("\n")
        if line.strip()
    ]


def _messy(records: list[dict]) -> bytes:
    """Everything the tool may repair and nothing it may not: reversed record order, reversed key
    order, ASCII escapes, spaces after separators, CRLF, blank lines, a BOM."""
    lines = [
        json.dumps(dict(reversed(list(r.items()))), ensure_ascii=True, separators=(", ", ": "))
        for r in reversed(records)
    ]
    return b"\xef\xbb\xbf" + ("\r\n\r\n".join(lines) + "\r\n").encode("utf-8")


def _cli(version: Path, pages: Path, *extra: str) -> int:
    return main([str(version), "--schema-dir", str(SCHEMA_DIR), "--pages", str(pages), *extra])


@pytest.fixture
def draft(tmp_path):
    pages = tmp_path / "pages"
    version = build(tmp_path / "data", pages)
    (version / "SHA256SUMS").unlink()
    manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(status="draft", frozen_at=None, dataset_hash=None)
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return version, pages


def test_rewrites_messy_draft_to_canonical_bytes_and_validator_passes(draft):
    version, pages = draft
    samples = version / "samples.jsonl"
    canonical = samples.read_bytes()  # the fixture writes the canonical form
    records = _records(samples)
    samples.write_bytes(_messy(records))
    assert samples.read_bytes() != canonical
    others_before = {k: v for k, v in _snapshot(version).items() if k != "samples.jsonl"}

    assert _cli(version, pages) == EXIT_OK
    assert samples.read_bytes() == canonical
    assert _records(samples) == sorted(records, key=lambda r: r["sample_id"])
    assert {k: v for k, v in _snapshot(version).items() if k != "samples.jsonl"} == others_before
    assert not list(version.glob(".samples.jsonl.*")), "temporary file left behind"


def test_second_run_is_a_no_op(draft):
    version, pages = draft
    samples = version / "samples.jsonl"
    samples.write_bytes(_messy(_records(samples)))
    assert _cli(version, pages) == EXIT_OK
    after_first = _snapshot(version)
    results = canonicalize(version)
    assert [(r.name, r.changed, r.reordered) for r in results] == [("samples.jsonl", False, False)]
    assert _snapshot(version) == after_first


def test_check_mode_writes_nothing_and_signals_pending_changes(draft):
    version, pages = draft
    samples = version / "samples.jsonl"
    samples.write_bytes(_messy(_records(samples)))
    before = _snapshot(version)
    assert _cli(version, pages, "--check") == EXIT_VALIDATION_FAILED
    assert _snapshot(version) == before
    assert _cli(version, pages) == EXIT_OK
    assert _cli(version, pages, "--check") == EXIT_OK


def test_acl_probes_are_ordered_and_canonicalized_too(draft):
    version, pages = draft
    corpus = json.loads((version / "corpus.json").read_text(encoding="utf-8"))
    forbidden = corpus["documents"][0]["source_hash"]
    probes = [
        {
            "probe_id": "acl-0002",
            "requesting_dept": "PV",
            "query": "示意文档1第0条的用法是什么",
            "forbidden_source_hashes": [forbidden],
            "derived_from_sample": "pc-0001",
            "notes": "",
        },
        {
            "probe_id": "acl-0001",
            "requesting_dept": "CO",
            "query": "示意文档1第0条的用法是什么",
            "forbidden_source_hashes": [forbidden],
            "derived_from_sample": "pc-0001",
            "notes": "",
        },
    ]
    acl = version / "acl_probes.jsonl"
    acl.write_bytes(_messy(list(reversed(probes))))  # _messy reverses again: file order is acl-0002 first
    assert _records(acl)[0]["probe_id"] == "acl-0002"

    results = canonicalize(version)
    assert [(r.name, r.records, r.changed, r.reordered) for r in results] == [
        ("samples.jsonl", 72, False, False),
        ("acl_probes.jsonl", 2, True, True),
    ]
    assert acl.read_bytes() == "".join(
        canonical_json(p) + "\n" for p in sorted(probes, key=lambda p: p["probe_id"])
    ).encode("utf-8")
    assert _cli(version, pages) == EXIT_OK


@pytest.mark.parametrize("make_not_draft", ["status", "frozen_at", "sums"])
def test_refuses_anything_that_is_not_a_draft(draft, make_not_draft):
    version, pages = draft
    samples = version / "samples.jsonl"
    samples.write_bytes(_messy(_records(samples)))
    manifest_path = version / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if make_not_draft == "status":
        manifest["status"] = "frozen"
    elif make_not_draft == "frozen_at":
        manifest["frozen_at"] = "2026-09-02"
    else:
        (version / "SHA256SUMS").write_bytes(b"")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    before = _snapshot(version)

    assert _cli(version, pages) == EXIT_REFUSED
    with pytest.raises(RefusedError):
        canonicalize(version)
    assert _snapshot(version) == before, "a refused run must not write anything"


@pytest.mark.parametrize(
    "bad_line",
    [
        "[1]",  # not an object
        '{"probe_id": "acl-0001"',  # invalid JSON
        '{"probe_id": "acl-0001", "probe_id": "acl-0002"}',  # duplicate key: json.loads would silently keep the last
        '{"probe_id": "acl-0001", "x": NaN}',  # non-finite: json.loads would silently accept
        '{"requesting_dept": "MA"}',  # no id: cannot be ordered
        '{"probe_id": "acl-0001"}\n{"probe_id": "acl-0001"}',  # duplicate ids
    ],
)
def test_refuses_bad_content_and_leaves_every_file_untouched(draft, bad_line):
    version, pages = draft
    samples = version / "samples.jsonl"
    samples.write_bytes(_messy(_records(samples)))  # repairable on its own ...
    (version / "acl_probes.jsonl").write_text(bad_line + "\n", encoding="utf-8")  # ... but the second file is not
    before = _snapshot(version)
    assert _cli(version, pages) == EXIT_REFUSED
    assert _snapshot(version) == before, "all files are checked before the first write"


def test_content_problems_are_reported_by_the_validator_not_repaired(draft):
    version, pages = draft
    samples = version / "samples.jsonl"
    records = _records(samples)
    records[5]["dept"] = "XX"  # schema violation: not a representation problem
    samples.write_bytes(_messy(records))
    assert _cli(version, pages) == EXIT_VALIDATION_FAILED
    rewritten = _records(samples)
    assert rewritten == sorted(records, key=lambda r: r["sample_id"])
    assert rewritten[5]["dept"] == "XX"
    assert samples.read_bytes() == "".join(canonical_json(r) + "\n" for r in rewritten).encode("utf-8")


def test_unicode_line_separator_inside_a_string_is_not_a_line_break(draft):
    version, _ = draft
    samples = version / "samples.jsonl"
    records = _records(samples)
    records[0]["notes"] = "第一行\u2028第二行 \u0085 end"
    samples.write_bytes(_messy(records))
    results = canonicalize(version)
    assert results[0].records == 72
    assert _records(samples)[0]["notes"] == "第一行\u2028第二行 \u0085 end"
