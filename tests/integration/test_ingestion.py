"""Ingestion pipeline (M1-09/10): validation, de-duplication, PII refusal with audited override, chunks with
offsets and hashes, provenance columns, and RLS behaviour of the resulting drafts."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import psycopg
import pytest

from medops.evals.probe import extract
from medops.ingestion import load, pipeline
from medops.ingestion.chunker import CHUNKER_VERSION, chunk_pages
from medops.ingestion.pipeline import DocumentSpec, IngestRefused, ingest_document
from medops.retrieval.lexical.normalization import normalize_text
from tests.integration.pdf_factory import make_pdf

SENTENCE = "Adults: 500 mg orally twice daily for seven days. "
PAGES = ["".join(SENTENCE for _ in range(40)), "Do not use in patients with known hypersensitivity. " * 12]


def spec_for(data: bytes, key: str = "test-label-a", version: str = "2026-01", dept: str = "MA") -> DocumentSpec:
    return DocumentSpec(
        document_key=key,
        title="Synthetic label A",
        doc_type="label",
        owner_dept=dept,
        language="en",
        version_label=version,
        source_hash=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        source_url="https://example.invalid/label-a.pdf",
        publisher="Synthetic publisher",
        retrieved_at=date(2026, 9, 17),
        terms_url="https://example.invalid/terms",
        license_name="CC BY 4.0 (synthetic)",
        attribution_text="Synthetic publisher",
    )


def write_pdf(tmp_path: Path, name: str, pages: list[str]) -> tuple[Path, bytes]:
    data = make_pdf(pages)
    path = tmp_path / name
    path.write_bytes(data)
    return path, data


def counts(conn: psycopg.Connection, doc_id) -> dict[str, int]:
    return {
        table: conn.execute(f"select count(*) from {table} where doc_id = %s", (doc_id,)).fetchone()[0]
        for table in ("chunks", "document_acl", "doc_audit", "ingestion_jobs")
    }


@pytest.fixture
def admin(migrated):
    with psycopg.connect(migrated) as conn:
        yield conn
        conn.rollback()


def test_ingest_writes_every_table_with_offsets_hashes_and_provenance(admin, tmp_path):
    pdf, data = write_pdf(tmp_path, "a.pdf", PAGES)
    spec = spec_for(data)
    result = ingest_document(admin, spec, pdf, actor="ingest-01")
    assert result.status == "ingested" and result.parse_quality == "trusted" and result.pii_hits == ()

    texts, warnings = extract.extract_pages(data)
    assert warnings == 0 and len(texts) == 2
    expected = chunk_pages(texts)
    assert result.chunk_count == len(expected) >= 4

    src = admin.execute(
        "select source_hash, byte_size, mime, integrity_status from source_objects where source_object_id = %s",
        (result.source_object_id,),
    ).fetchone()
    assert src == (spec.source_hash, len(data), "application/pdf", "verified")
    job = admin.execute(
        "select status, parse_quality, parser_version, extraction_params_hash, extractor_warnings, empty_pages, doc_id from ingestion_jobs where job_id = %s",
        (result.job_id,),
    ).fetchone()
    assert job == (
        "succeeded",
        "trusted",
        f"pypdf {extract.EXTRACTOR_VERSION}",
        extract.PARAMS_HASH,
        0,
        0,
        result.doc_id,
    )
    doc = admin.execute(
        "select status, document_key, version, owner_dept, language, source_url, publisher, retrieved_at, license_name, terms_url, attribution_text, parse_quality, active_ingestion_job_id from documents where doc_id = %s",
        (result.doc_id,),
    ).fetchone()
    assert doc == (
        "draft",
        "test-label-a",
        "2026-01",
        "MA",
        "en",
        spec.source_url,
        spec.publisher,
        spec.retrieved_at,
        spec.license_name,
        spec.terms_url,
        spec.attribution_text,
        "trusted",
        result.job_id,
    )
    rows = admin.execute(
        """select c.seq, c.page, c.content, c.chunk_content_hash, s.page, s.char_start, s.char_end
           from chunks c join chunk_spans s on s.chunk_id = c.chunk_id where c.doc_id = %s order by c.seq, s.ordinal""",
        (result.doc_id,),
    ).fetchall()
    assert len(rows) == len(expected)
    normalised = [normalize_text(t) for t in texts]
    for (seq, page, content, digest, span_page, start, end), chunk in zip(rows, expected, strict=True):
        assert (seq, page, content, digest) == (chunk.seq, chunk.page, chunk.content, chunk.content_hash)
        assert span_page == page and content == normalised[page - 1][start:end]
        assert digest == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert counts(admin, result.doc_id) == {
        "chunks": len(expected),
        "document_acl": 1,
        "doc_audit": 1,
        "ingestion_jobs": 1,
    }
    acl = admin.execute(
        "select dept, permission, granted_by from document_acl where doc_id = %s", (result.doc_id,)
    ).fetchone()
    assert acl == ("MA", "read", "ingest-01")
    audit = admin.execute("select action, actor, details from doc_audit where doc_id = %s", (result.doc_id,)).fetchone()
    assert audit[0] == "ingest" and audit[1] == "ingest-01"
    assert (
        audit[2]["chunks"] == len(expected)
        and audit[2]["chunker_version"] == CHUNKER_VERSION
        and audit[2]["pii_hits"] == 0
    )


def test_reingest_is_idempotent_and_a_second_document_on_the_same_source_is_refused(admin, tmp_path):
    pdf, data = write_pdf(tmp_path, "a.pdf", PAGES)
    first = ingest_document(admin, spec_for(data), pdf, actor="ingest-01")
    again = ingest_document(admin, spec_for(data), pdf, actor="ingest-01")
    assert again.status == "exists" and again.doc_id == first.doc_id and again.chunk_count == first.chunk_count
    assert counts(admin, first.doc_id)["doc_audit"] == 1
    with pytest.raises(IngestRefused, match="administrator confirmation"):
        ingest_document(admin, spec_for(data, key="test-label-a", version="2026-02"), pdf, actor="ingest-01")
    with pytest.raises(IngestRefused, match="administrator confirmation"):
        ingest_document(admin, spec_for(data, key="another-key"), pdf, actor="ingest-01")


def test_file_validation_refuses_before_any_write(admin, tmp_path, monkeypatch):
    pdf, data = write_pdf(tmp_path, "a.pdf", PAGES)
    before = admin.execute("select count(*) from source_objects").fetchone()[0]
    spec = spec_for(data)
    wrong_hash = DocumentSpec(**{**spec.__dict__, "source_hash": "0" * 64})
    with pytest.raises(IngestRefused, match="source_hash"):
        ingest_document(admin, wrong_hash, pdf, actor="x")
    wrong_size = DocumentSpec(**{**spec.__dict__, "byte_size": len(data) + 1})
    with pytest.raises(IngestRefused, match="byte_size"):
        ingest_document(admin, wrong_size, pdf, actor="x")
    not_pdf = tmp_path / "b.pdf"
    not_pdf.write_bytes(b"%!PS-Adobe not a pdf")
    with pytest.raises(IngestRefused, match="not a PDF"):
        ingest_document(admin, spec_for(not_pdf.read_bytes()), not_pdf, actor="x")
    monkeypatch.setattr(pipeline, "MAX_PDF_BYTES", 10)
    with pytest.raises(IngestRefused, match="exceeds"):
        ingest_document(admin, spec, pdf, actor="x")
    assert admin.execute("select count(*) from source_objects").fetchone()[0] == before


def test_pii_hits_refuse_by_default_and_override_is_audited(admin, tmp_path):
    pdf, data = write_pdf(tmp_path, "c.pdf", ["Questions: contact safety.desk@example.org for details. " * 10])
    spec = spec_for(data, key="test-guideline-c")
    with pytest.raises(IngestRefused, match="pii-rules-v1") as exc:
        ingest_document(admin, spec, pdf, actor="ingest-01")
    assert "safety.desk@example.org" in str(exc.value)
    assert (
        admin.execute("select count(*) from documents where document_key = %s", (spec.document_key,)).fetchone()[0] == 0
    )

    result = ingest_document(
        admin, spec, pdf, actor="reviewer-01", pii_override_reason="organisational mailbox, not personal data"
    )
    assert result.status == "ingested" and result.pii_hits == (("email", "safety.desk@example.org"),)
    audit = admin.execute(
        "select action, actor, reason, details from doc_audit where doc_id = %s order by id", (result.doc_id,)
    ).fetchall()
    assert [a[0] for a in audit] == ["ingest", "pii_review_override"]
    assert audit[1][1:3] == ("reviewer-01", "organisational mailbox, not personal data")
    assert audit[1][3]["hits"] == [["email", "safety.desk@example.org"]]


def test_stored_page_texts_must_match_the_extraction(admin, tmp_path):
    pdf, data = write_pdf(tmp_path, "d.pdf", PAGES)
    pages_dir = tmp_path / "pages"
    extract.write_pages(pdf, pages_dir)
    spec = spec_for(data, key="test-label-d")
    (pages_dir / spec.source_hash / "2.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(IngestRefused, match="extraction drift"):
        ingest_document(admin, spec, pdf, actor="x", pages_dir=pages_dir)
    (pages_dir / spec.source_hash / "2.txt").write_text(extract.extract_pages(data)[0][1], encoding="utf-8")
    assert ingest_document(admin, spec, pdf, actor="x", pages_dir=pages_dir).status == "ingested"


def test_image_only_pdf_is_refused(admin, tmp_path):
    pdf, data = write_pdf(tmp_path, "e.pdf", ["", ""])
    with pytest.raises(IngestRefused, match="no text layer"):
        ingest_document(admin, spec_for(data, key="test-scan-e"), pdf, actor="x")


def test_ingested_drafts_are_invisible_to_app_and_readonly_but_visible_to_admin(admin, login_users, tmp_path):
    pdf, data = write_pdf(tmp_path, "f.pdf", PAGES)
    result = ingest_document(admin, spec_for(data, key="test-label-f", dept="PV"), pdf, actor="ingest-01")
    admin.commit()  # the session database is dropped at the end; ingested drafts carry audit rows and are kept
    for kind in ("app", "readonly"):
        with psycopg.connect(login_users[kind]["dsn"]) as conn, conn.transaction():
            conn.execute("select set_config('medops.dept', 'PV', true)")
            assert conn.execute("select count(*) from documents where doc_id = %s", (result.doc_id,)).fetchone()[0] == 0
            assert conn.execute("select count(*) from chunks where doc_id = %s", (result.doc_id,)).fetchone()[0] == 0
    with psycopg.connect(login_users["admin"]["dsn"]) as conn:
        assert (
            conn.execute("select count(*) from chunks where doc_id = %s", (result.doc_id,)).fetchone()[0]
            == result.chunk_count
        )


def test_batch_loader_reports_each_document_and_exit_code(migrated, tmp_path, capsys):
    sources = tmp_path / "sources"
    sources.mkdir()
    clean = make_pdf(
        [PAGES[0] + " Batch variant.", PAGES[1]]
    )  # distinct bytes: same-source documents are refused by design
    dirty = make_pdf(["Write to helpdesk@example.org for the form. " * 8])
    docs = []
    for key, data in (("batch-clean", clean), ("batch-dirty", dirty)):
        digest = hashlib.sha256(data).hexdigest()
        (sources / f"{digest}.pdf").write_bytes(data)
        docs.append(
            {
                "document_key": key,
                "title": key,
                "doc_type": "guideline",
                "owner_dept": "CO",
                "language": "en",
                "source_url": "https://example.invalid/x.pdf",
                "publisher": "Synthetic",
                "license_status": "eligible",
                "license_or_terms": {"name_or_summary": "CC BY 4.0 (synthetic)", "attribution_text": "Synthetic"},
                "terms_url": "https://example.invalid/terms",
                "retrieved_at": "2026-09-17",
                "version_label": "v1",
                "source_hash": digest,
                "byte_size": len(data),
                "mime": "application/pdf",
                "pages": 1,
                "notes": "",
            }
        )
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"dataset_version": "v1", "documents": docs}), encoding="utf-8")
    base = ["--corpus", str(corpus), "--sources-dir", str(sources), "--actor", "loader-01", "--admin-url", migrated]

    assert load.main(base) == 1
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert {(line["document_key"], line["status"]) for line in lines} == {
        ("batch-clean", "ingested"),
        ("batch-dirty", "refused"),
    }
    assert load.main([*base, "--accept-pii", "batch-dirty=organisational mailbox"]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert {(line["document_key"], line["status"]) for line in lines} == {
        ("batch-clean", "exists"),
        ("batch-dirty", "ingested"),
    }
    assert load.main([*base, "--accept-pii", "broken"]) == 2


def test_extractor_warnings_give_low_trust_unless_a_reviewer_override_is_audited(admin, tmp_path, monkeypatch):
    pdf, data = write_pdf(tmp_path, "w.pdf", [PAGES[0] + " First synthetic warning file.", PAGES[1]])
    real = pipeline.extract_and_check

    def with_warnings(data, source_hash, pages_dir):
        texts, _ = real(data, source_hash, pages_dir)
        return texts, ["fontTools is required to fully parse the encoding of a CFF Type1 font"] * 3

    monkeypatch.setattr(pipeline, "extract_and_check", with_warnings)
    low = ingest_document(admin, spec_for(data, key="test-warn-low"), pdf, actor="ingest-01")
    assert low.parse_quality == "low_trust"
    job = admin.execute(
        "select parse_quality, extractor_warnings from ingestion_jobs where job_id = %s", (low.job_id,)
    ).fetchone()
    assert job == ("low_trust", 3)
    details = admin.execute(
        "select details from doc_audit where doc_id = %s and action = 'ingest'", (low.doc_id,)
    ).fetchone()[0]
    assert details["extractor_warning_messages"] == [
        {"message": "fontTools is required to fully parse the encoding of a CFF Type1 font", "count": 3}
    ]
    assert details["quality_review_override"] is False

    pdf2, data2 = write_pdf(tmp_path, "w2.pdf", [PAGES[0] + " Second synthetic file.", PAGES[1]])
    ok = ingest_document(
        admin,
        spec_for(data2, key="test-warn-ok"),
        pdf2,
        actor="reviewer-01",
        quality_override_reason="page texts verified against the frozen pages; warnings are skipped CFF font encoding only",
    )
    assert ok.parse_quality == "trusted"
    assert admin.execute("select parse_quality from documents where doc_id = %s", (ok.doc_id,)).fetchone() == (
        "trusted",
    )
    audit = admin.execute(
        "select action, actor, reason, details from doc_audit where doc_id = %s order by id", (ok.doc_id,)
    ).fetchall()
    assert [a[0] for a in audit] == ["ingest", "quality_review_override"]
    assert audit[1][1] == "reviewer-01" and audit[1][2].startswith("page texts verified")
    assert (
        audit[1][3]["from"] == "low_trust" and audit[1][3]["to"] == "trusted" and audit[1][3]["extractor_warnings"] == 3
    )
    # an override without warnings is a no-op (no audit row, no upgrade needed)
    monkeypatch.setattr(pipeline, "extract_and_check", real)
    pdf3, data3 = write_pdf(tmp_path, "w3.pdf", [PAGES[0] + " Third synthetic file.", PAGES[1]])
    clean = ingest_document(
        admin, spec_for(data3, key="test-warn-clean"), pdf3, actor="reviewer-01", quality_override_reason="unused"
    )
    assert clean.parse_quality == "trusted"
    assert admin.execute(
        "select count(*) from doc_audit where doc_id = %s and action = 'quality_review_override'", (clean.doc_id,)
    ).fetchone() == (0,)
