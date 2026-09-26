"""Released glossary files (record 93): `glossary-none` means no glossary; any other version must exist under the
configured directory, declare the same version and hash to the digest in its name — otherwise the runtime fails
closed with a dependency error instead of rewriting queries with a glossary nobody released."""

from __future__ import annotations

import json

import pytest

from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.glossary_store import (
    glossary_version_for,
    load_versioned_glossary,
    valid_glossary_version,
)
from medops.retrieval.rewrite import Glossary, GlossaryEntry

ENTRIES = (
    GlossaryEntry(term="职业暴露", synonyms=("occupational exposure",), kind="concept"),
    GlossaryEntry(term="PSUR", synonyms=("periodic safety update report",), kind="abbreviation"),
)


def _write(tmp_path, version: str, entries=ENTRIES, declared: str | None = None):
    g = Glossary(version=declared or version, entries=entries)
    (tmp_path / f"{version}.json").write_text(
        json.dumps(g.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8"
    )
    return version


def test_version_format_and_digest_naming():
    v = glossary_version_for(ENTRIES, "20260926")
    assert valid_glossary_version(v) and v.startswith("glossary-20260926-") and len(v) == len("glossary-20260926-") + 12
    assert valid_glossary_version("glossary-none")
    assert not valid_glossary_version("glossary-2026-abc") and not valid_glossary_version("v1")


def test_none_needs_no_directory_and_a_good_file_loads(tmp_path):
    assert load_versioned_glossary(None, "glossary-none") is None
    v = _write(tmp_path, glossary_version_for(ENTRIES, "20260926"))
    g = load_versioned_glossary(tmp_path, v)
    assert g is not None and g.version == v and len(g.entries) == 2


def _detail(fn, *args) -> str:
    with pytest.raises(InfrastructureError) as info:
        fn(*args)
    assert info.value.code is ErrorCode.dependency_unavailable
    return str(info.value.detail)


def test_missing_directory_file_version_or_digest_fail_closed(tmp_path):
    v = glossary_version_for(ENTRIES, "20260926")
    assert "GLOSSARY_DIR" in _detail(load_versioned_glossary, None, v)
    assert "missing" in _detail(load_versioned_glossary, tmp_path, v)
    _write(tmp_path, v, declared="glossary-20260926-000000000000")
    assert "declares version" in _detail(load_versioned_glossary, tmp_path, v)
    bad = "glossary-20260926-" + "0" * 12
    _write(tmp_path, bad)
    assert "does not match" in _detail(load_versioned_glossary, tmp_path, bad)
    assert "invalid glossary version" in _detail(load_versioned_glossary, tmp_path, "glossary-latest")
