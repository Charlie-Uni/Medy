"""Export validated source coordinates from one consistent frozen/page view."""

import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from medops.evals.probe import chunk_mapping
from medops.ingestion.chunker import CHUNKER_VERSION, chunk_pages
from tests.unit.evals.fixture_builder import build


@pytest.fixture
def exporter(monkeypatch):
    tooling = Path(__file__).resolve().parents[3] / "evals/experiments/lexical/tools"
    monkeypatch.syspath_prepend(str(tooling))
    return importlib.import_module("export_chunk_snapshot")


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class _Connection:
    """Only the export's documented read queries are supported; no real database is used."""

    def __init__(self, version, pages):
        manifest = json.loads((version / "manifest.json").read_bytes())
        corpus = json.loads((version / "corpus.json").read_bytes())
        self.documents = {}
        self.rows = {}
        self.queries = []
        self.connects = 0
        for doc in corpus["documents"]:
            key = doc["document_key"]
            self.documents[(doc["source_hash"], key)] = {
                "doc_id": key,
                "version": doc["version_label"],
                "status": "draft",
                "parse_quality": "trusted",
                "owner_dept": doc["owner_dept"],
                "parser_version": "fixture 1",
                "extraction_params_hash": manifest["extraction"]["params_hash"],
            }
            raw = [
                (pages / doc["source_hash"] / f"{page}.txt").read_text(encoding="utf-8")
                for page in range(1, doc["pages"] + 1)
            ]
            self.rows[key] = [
                {
                    "chunk_id": f"{key}-{chunk.seq}",
                    "seq": chunk.seq,
                    "content": chunk.content,
                    "chunk_content_hash": chunk.content_hash,
                    "spans": [
                        {"page": span.page, "char_start": span.char_start, "char_end": span.char_end}
                        for span in chunk.spans
                    ],
                }
                for chunk in chunk_pages(raw)
            ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def connect(self, *args, **kwargs):
        self.connects += 1
        return self

    def execute(self, query, params=()):
        self.queries.append(query)
        if query == "set transaction isolation level repeatable read, read only":
            return _Result([])
        if query == "show server_version":
            return _Result([{"server_version": "synthetic-postgres"}])
        if query == "select version_num from alembic_version":
            return _Result([{"version_num": "synthetic-migration"}])
        if "from documents d" in query:
            return _Result([self.documents[params]])
        if "from doc_audit" in query:
            return _Result([{"details": {"chunker_version": CHUNKER_VERSION, "normalization": "norm-v1"}}])
        if "from chunks c" in query:
            return _Result(self.rows[params[0]])
        if "select count(*)" in query:
            return _Result([{"n": len(self.rows[params[0]])}])
        raise AssertionError("unexpected database query")


@pytest.fixture
def frozen(exporter, monkeypatch, tmp_path):
    pages = tmp_path / "pages"
    version = build(tmp_path / "data", pages)
    conn = _Connection(version, pages)
    monkeypatch.setattr(exporter.psycopg, "connect", conn.connect)
    settings = SimpleNamespace(
        database_admin_url=SimpleNamespace(get_secret_value=lambda: "synthetic-test-dsn"),
        database_url=None,
    )
    monkeypatch.setattr(exporter, "Settings", lambda: settings)
    return version, pages, tmp_path / "experiment/chunks.json", conn


def test_valid_export_is_read_only_and_excludes_text(exporter, frozen):
    version, pages, out, conn = frozen
    result = exporter.export(version, pages, out)
    raw = out.read_bytes()
    payload = json.loads(raw)
    assert conn.queries[0] == "set transaction isolation level repeatable read, read only"
    assert result["chunks"] == len(payload["chunks"]) == 24
    assert result["regenerated_chunks_match"] is True
    assert result["mode"] == "read_only_admin_export_not_retrieval"
    assert result["snapshot_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["manifest_sha256"] == hashlib.sha256((version / "manifest.json").read_bytes()).hexdigest()
    assert all(set(row) == {"chunk_id", "source_hash", "version_label", "spans"} for row in payload["chunks"])
    assert "synthetic-test-dsn" not in raw.decode()
    assert not list(out.parent.glob(".probe-artifact-*.tmp"))


@pytest.mark.parametrize("name", ["manifest.json", "corpus.json", "samples.jsonl", "SHA256SUMS"])
def test_input_changed_during_validation_is_refused_without_output(exporter, frozen, monkeypatch, name):
    version, pages, out, conn = frozen
    validate = exporter.ProbeSetValidator.validate

    def mutate_after_validation(self, *args, **kwargs):
        report = validate(self, *args, **kwargs)
        assert report.passed
        path = version / name
        path.write_bytes(path.read_bytes() + b" ")
        return report

    monkeypatch.setattr(exporter.ProbeSetValidator, "validate", mutate_after_validation)
    with pytest.raises(ValueError, match="changed during validation"):
        exporter.export(version, pages, out)
    assert conn.connects == 0
    assert not out.exists()
    assert not out.parent.exists()


def test_validation_and_regeneration_reuse_raw_pages(exporter, frozen, monkeypatch):
    version, pages, out, conn = frozen
    page = next(pages.glob("*/1.txt"))
    original = page.read_text(encoding="utf-8")
    read_text = Path.read_text
    reads = []
    validate = exporter.ProbeSetValidator.validate

    def tracked_read(path, *args, **kwargs):
        if path == page:
            reads.append(path)
        return read_text(path, *args, **kwargs)

    def replace_page_after_validation(self, *args, **kwargs):
        report = validate(self, *args, **kwargs)
        assert report.passed
        page.write_text("This later page view must not replace validated text.", encoding="utf-8")
        return report

    monkeypatch.setattr(Path, "read_text", tracked_read)
    monkeypatch.setattr(exporter.ProbeSetValidator, "validate", replace_page_after_validation)
    result = exporter.export(version, pages, out)
    assert result["regenerated_chunks_match"] is True
    assert reads == [page]
    assert conn.connects == 1
    assert original != read_text(page, encoding="utf-8")


def test_missing_cached_page_cannot_appear_later(exporter, tmp_path):
    cache = exporter._CachedRawPages(tmp_path)
    assert cache.page_text("synthetic", 1) is None
    (tmp_path / "synthetic").mkdir()
    (tmp_path / "synthetic/1.txt").write_text("later text", encoding="utf-8")
    with pytest.raises(ValueError, match="page text is missing"):
        cache.document_pages("synthetic", 1)


def test_invalid_frozen_data_is_refused_before_database(exporter, frozen):
    version, pages, out, conn = frozen
    (version / "SHA256SUMS").write_text("invalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frozen input validation failed"):
        exporter.export(version, pages, out)
    assert conn.connects == 0
    assert not out.exists()


def test_stored_content_mismatch_does_not_publish(exporter, frozen):
    version, pages, out, conn = frozen
    next(iter(conn.rows.values()))[0]["content"] = "Different database text"
    with pytest.raises(ValueError, match="differs from regenerated chunks"):
        exporter.export(version, pages, out)
    assert not out.exists()
    assert not out.parent.exists()


@pytest.mark.parametrize("kind", ["existing", "dangling_symlink", "inside_frozen", "symlink_to_frozen"])
def test_output_guards_run_before_database(exporter, frozen, kind):
    version, pages, out, conn = frozen
    if kind == "existing":
        out.parent.mkdir()
        out.write_bytes(b"original\n")
    elif kind == "dangling_symlink":
        out.parent.mkdir()
        out.symlink_to(out.parent / "missing-target")
    elif kind == "inside_frozen":
        out = version / "snapshot.json"
    else:
        out.parent.symlink_to(version, target_is_directory=True)
    before = {path.relative_to(version): path.read_bytes() for path in version.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="output"):
        exporter.export(version, pages, out)
    assert conn.connects == 0
    assert {path.relative_to(version): path.read_bytes() for path in version.rglob("*") if path.is_file()} == before
    if kind == "existing":
        assert out.read_bytes() == b"original\n"
    elif kind == "dangling_symlink":
        assert out.is_symlink()
        assert not out.resolve().exists()
    else:
        assert not out.exists()


def test_racing_output_is_preserved_and_temporary_is_removed(exporter, frozen, monkeypatch):
    version, pages, out, _ = frozen
    link = chunk_mapping.os.link

    def competing_publish(source, destination, **kwargs):
        assert destination == out.name
        out.write_bytes(b"concurrent writer\n")
        return link(source, destination, **kwargs)

    monkeypatch.setattr(chunk_mapping.os, "link", competing_publish)
    with pytest.raises(FileExistsError):
        exporter.export(version, pages, out)
    assert out.read_bytes() == b"concurrent writer\n"
    assert not list(out.parent.glob(".probe-artifact-*.tmp"))


def test_export_delegates_parent_swap_protection_to_shared_publisher(exporter, frozen, monkeypatch):
    version, pages, out, _ = frozen
    out.parent.mkdir()
    parked = out.parent.with_name("original-experiment")
    before = {path.relative_to(version): path.read_bytes() for path in version.rglob("*") if path.is_file()}
    link = chunk_mapping.os.link
    calls = []

    def shared_publish(raw, target, *, protected_dir):
        assert target == out
        assert protected_dir == version
        assert len(json.loads(raw)["chunks"]) == 24
        calls.append((target, protected_dir))
        return chunk_mapping.publish_artifact(raw, target, protected_dir=protected_dir)

    def replace_parent_before_link(source, destination, **kwargs):
        out.parent.rename(parked)
        out.parent.symlink_to(version, target_is_directory=True)
        return link(source, destination, **kwargs)

    monkeypatch.setattr(exporter, "publish_artifact", shared_publish)
    monkeypatch.setattr(chunk_mapping.os, "link", replace_parent_before_link)
    with pytest.raises(chunk_mapping.MappingRefused, match="parent path changed"):
        exporter.export(version, pages, out)
    assert calls == [(out, version)]
    assert {path.relative_to(version): path.read_bytes() for path in version.rglob("*") if path.is_file()} == before
    assert not out.exists()
    assert list(parked.iterdir()) == []
