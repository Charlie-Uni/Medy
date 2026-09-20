"""Ingestion into the fact plane (M1-09 validation and de-duplication, M1-10 chunks with offsets and hashes).

One document per call, everything inside the caller's transaction (an admin-role connection):

1. validate the file: PDF magic, size limit, SHA-256 equal to the declared `source_hash`;
2. extract page texts with the locked extractor (pypdf, extraction-v1) and, when a pages directory is
   given, require them to be byte-identical to the stored `<pages>/<sha256>/<n>.txt` files;
3. scan the normalised page texts with `pii-rules-v1`; any hit refuses the document (INV-DATA-01) unless
   the caller passes a review reason, which is then written to doc_audit as `pii_review_override`;
4. chunk with `chunker-v1`;
5. write source_objects (re-used when the hash exists), ingestion_jobs, documents (status draft),
   chunks, chunk_spans, document_acl (owner department, read) and a doc_audit `ingest` row.

parse_quality is `trusted` only when the extractor raised no warnings; otherwise `low_trust`, which the
database will not let become active (INV-DATA-05). A second document on the same source object is
refused (baseline 3.3: needs administrator confirmation) except when it is the same document_key and
version, which returns the existing row instead of writing.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from medops.evals.probe import extract
from medops.evals.probe.pii import PII_RULESET_VERSION, find_pii_matches
from medops.ingestion.chunker import CHUNKER_VERSION, Chunk, chunk_pages
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

MAX_PDF_BYTES = 50 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
MIME_PDF = "application/pdf"


def _first(cursor: Any) -> Any:
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("query returned no row")
    return row[0]


class IngestRefused(Exception):
    """The document was not written; the message says which rule refused it."""


@dataclass(frozen=True)
class DocumentSpec:
    document_key: str
    title: str
    doc_type: str
    owner_dept: str
    language: str
    version_label: str
    source_hash: str
    byte_size: int
    source_url: str
    publisher: str
    retrieved_at: date
    terms_url: str
    license_name: str
    attribution_text: str
    notes: str = ""

    @classmethod
    def from_corpus_record(cls, record: Mapping[str, Any]) -> DocumentSpec:
        terms = record["license_or_terms"]
        return cls(
            document_key=record["document_key"],
            title=record["title"],
            doc_type=record["doc_type"],
            owner_dept=record["owner_dept"],
            language=record["language"],
            version_label=record["version_label"],
            source_hash=record["source_hash"],
            byte_size=int(record["byte_size"]),
            source_url=record["source_url"],
            publisher=record["publisher"],
            retrieved_at=date.fromisoformat(record["retrieved_at"]),
            terms_url=record["terms_url"],
            license_name=terms["name_or_summary"],
            attribution_text=terms.get("attribution_text") or "",
            notes=record.get("notes") or "",
        )


@dataclass(frozen=True)
class IngestResult:
    status: str  # "ingested" | "exists"
    doc_id: uuid.UUID
    source_object_id: uuid.UUID
    job_id: uuid.UUID | None
    chunk_count: int
    parse_quality: str
    pii_hits: tuple[tuple[str, str], ...]


def validate_pdf(data: bytes, spec: DocumentSpec) -> str:
    if not data.startswith(PDF_MAGIC):
        raise IngestRefused("file is not a PDF (magic bytes)")
    if len(data) > MAX_PDF_BYTES:
        raise IngestRefused(f"file exceeds {MAX_PDF_BYTES} bytes")
    if len(data) != spec.byte_size:
        raise IngestRefused(f"byte_size {len(data)} does not match declared {spec.byte_size}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != spec.source_hash:
        raise IngestRefused("sha256 does not match declared source_hash")
    return digest


def extract_and_check(data: bytes, source_hash: str, pages_dir: Path | None) -> tuple[list[str], list[str]]:
    texts, warnings = extract.extract_pages_detailed(data)
    if pages_dir is not None:
        stored = Path(pages_dir) / source_hash
        if stored.is_dir():
            for i, text in enumerate(texts, start=1):
                path = stored / f"{i}.txt"
                if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
                    raise IngestRefused(f"extracted page {i} differs from stored page text {path}; extraction drift")
    if not any(t.strip() for t in texts):
        raise IngestRefused("no text layer: scanned or image-only PDF is not ingested (M1-10; OCR is P1)")
    return texts, warnings


def scan_pii(texts: list[str]) -> tuple[tuple[str, str], ...]:
    hits: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text in texts:
        for rule, match in find_pii_matches(normalize_text(text)):
            if (rule, match) not in seen:
                seen.add((rule, match))
                hits.append((rule, match))
    return tuple(hits)


def _message_counts(messages: list[str]) -> list[dict[str, object]]:
    """Distinct warning texts with their counts, in first-occurrence order."""
    counts: dict[str, int] = {}
    for m in messages:
        counts[m] = counts.get(m, 0) + 1
    return [{"message": m, "count": n} for m, n in counts.items()]


def _existing_document(conn: psycopg.Connection, source_hash: str) -> list[tuple[uuid.UUID, str, str, uuid.UUID]]:
    return conn.execute(
        """select d.doc_id, d.document_key, d.version, s.source_object_id
           from source_objects s left join documents d on d.source_object_id = s.source_object_id
           where s.source_hash = %s""",
        (source_hash,),
    ).fetchall()


def ingest_document(
    conn: psycopg.Connection,
    spec: DocumentSpec,
    pdf_path: Path,
    *,
    actor: str,
    pages_dir: Path | None = None,
    pii_override_reason: str | None = None,
    quality_override_reason: str | None = None,
    storage_uri: str | None = None,
    family_id: uuid.UUID | None = None,
    supersedes: uuid.UUID | None = None,
) -> IngestResult:
    """Ingest one PDF as a draft document. `quality_override_reason` is the audited reviewer decision that
    upgrades an extraction with pypdf warnings from `low_trust` to `trusted` (INV-DATA-05 stays the default);
    it is only meaningful when the stored page texts were verified (extraction drift check) and is written to
    doc_audit as `quality_review_override` together with the warning messages."""
    data = Path(pdf_path).read_bytes()
    source_hash = validate_pdf(data, spec)
    if supersedes is not None:
        # a new version joins the superseded document's family (M1-11); the chain is fixed at insert time
        # because documents.supersedes is an immutable identity column (INV-DATA-04)
        prev = conn.execute("select family_id, status::text from documents where doc_id = %s", (supersedes,)).fetchone()
        if prev is None:
            raise IngestRefused(f"supersedes {supersedes} does not exist")
        if prev[1] == "withdrawn":
            raise IngestRefused("a withdrawn document cannot be superseded")
        if family_id is not None and family_id != prev[0]:
            raise IngestRefused("family_id differs from the superseded document's family")
        family_id = prev[0]

    rows = _existing_document(conn, source_hash)
    source_object_id = rows[0][3] if rows else None
    for doc_id, key, version, _ in rows:
        if doc_id is None:
            continue
        if key == spec.document_key and version == spec.version_label:
            assert source_object_id is not None
            quality = _first(conn.execute("select parse_quality from documents where doc_id = %s", (doc_id,)))
            count = _first(conn.execute("select count(*) from chunks where doc_id = %s", (doc_id,)))
            return IngestResult("exists", doc_id, source_object_id, None, count, quality, ())
        raise IngestRefused(
            f"source {source_hash[:12]} already backs document {key} {version}; a second document on the same "
            "source object needs administrator confirmation (baseline 3.3)"
        )

    texts, warning_messages = extract_and_check(data, source_hash, pages_dir)
    warnings = len(warning_messages)
    hits = scan_pii(texts)
    if hits and not pii_override_reason:
        summary = "; ".join(f"{rule}: {match}" for rule, match in hits[:5])
        raise IngestRefused(f"PII rules ({PII_RULESET_VERSION}) matched, refused by default (INV-DATA-01): {summary}")
    chunks = chunk_pages(texts)
    if not chunks:
        raise IngestRefused("chunker produced no chunks")
    quality_overridden = warnings > 0 and bool(quality_override_reason)
    parse_quality = "trusted" if warnings == 0 or quality_overridden else "low_trust"
    empty_pages = sum(1 for t in texts if not t.strip())

    if source_object_id is None:
        source_object_id = _first(
            conn.execute(
                """insert into source_objects (source_hash, storage_uri, byte_size, mime, integrity_status, last_verified_at, created_by)
               values (%s, %s, %s, %s, 'verified', now(), %s) returning source_object_id""",
                (source_hash, storage_uri or Path(pdf_path).resolve().as_uri(), len(data), MIME_PDF, actor),
            )
        )
    job_id = _first(
        conn.execute(
            """insert into ingestion_jobs (source_object_id, status, attempt, parser_version, extraction_params_hash, parse_quality,
                                       quality_score, extractor_warnings, empty_pages, started_at, finished_at)
           values (%s, 'succeeded', 1, %s, %s, %s, %s, %s, %s, now(), now()) returning job_id""",
            (
                source_object_id,
                f"{extract.EXTRACTOR} {extract.EXTRACTOR_VERSION}",
                extract.PARAMS_HASH,
                parse_quality,
                round(1 - empty_pages / len(texts), 4),
                warnings,
                empty_pages,
            ),
        )
    )
    doc_id = _first(
        conn.execute(
            """insert into documents (family_id, document_key, title, doc_type, version, status, source_object_id, active_ingestion_job_id,
                                  parse_quality, owner_dept, language, source_url, publisher, retrieved_at, license_name, terms_url,
                                  attribution_text, created_by, supersedes)
           values (%s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning doc_id""",
            (
                family_id or uuid.uuid4(),
                spec.document_key,
                spec.title,
                spec.doc_type,
                spec.version_label,
                source_object_id,
                job_id,
                parse_quality,
                spec.owner_dept,
                spec.language,
                spec.source_url,
                spec.publisher,
                spec.retrieved_at,
                spec.license_name,
                spec.terms_url,
                spec.attribution_text or None,
                actor,
                supersedes,
            ),
        )
    )
    conn.execute("update ingestion_jobs set doc_id = %s where job_id = %s", (doc_id, job_id))
    _insert_chunks(conn, doc_id, chunks)
    conn.execute(
        "insert into document_acl (doc_id, dept, permission, granted_by) values (%s, %s, 'read', %s)",
        (doc_id, spec.owner_dept, actor),
    )
    details = {
        "document_key": spec.document_key,
        "pages": len(texts),
        "empty_pages": empty_pages,
        "chunks": len(chunks),
        "chunker_version": CHUNKER_VERSION,
        "normalization": NORMALIZATION_VERSION,
        "extractor_warnings": warnings,
        "extractor_warning_messages": _message_counts(warning_messages),
        "parse_quality": parse_quality,
        "quality_review_override": quality_overridden,
        "pii_ruleset": PII_RULESET_VERSION,
        "pii_hits": len(hits),
    }
    conn.execute(
        "insert into doc_audit (doc_id, action, actor, details) values (%s, 'ingest', %s, %s::jsonb)",
        (doc_id, actor, json.dumps(details, ensure_ascii=False)),
    )
    if quality_overridden:
        conn.execute(
            "insert into doc_audit (doc_id, action, actor, reason, details) values (%s, 'quality_review_override', %s, %s, %s::jsonb)",
            (
                doc_id,
                actor,
                quality_override_reason,
                json.dumps(
                    {
                        "extractor_warnings": warnings,
                        "messages": _message_counts(warning_messages),
                        "from": "low_trust",
                        "to": "trusted",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    if hits:
        conn.execute(
            "insert into doc_audit (doc_id, action, actor, reason, details) values (%s, 'pii_review_override', %s, %s, %s::jsonb)",
            (
                doc_id,
                actor,
                pii_override_reason,
                json.dumps({"ruleset": PII_RULESET_VERSION, "hits": hits}, ensure_ascii=False),
            ),
        )
    return IngestResult("ingested", doc_id, source_object_id, job_id, len(chunks), parse_quality, hits)


def _insert_chunks(conn: psycopg.Connection, doc_id: uuid.UUID, chunks: list[Chunk]) -> None:
    with conn.cursor() as cur:
        for chunk in chunks:
            chunk_id = _first(
                cur.execute(
                    "insert into chunks (doc_id, seq, page, section, content, chunk_content_hash) values (%s, %s, %s, %s, %s, %s) returning chunk_id",
                    (doc_id, chunk.seq, chunk.page, chunk.section, chunk.content, chunk.content_hash),
                )
            )
            for ordinal, span in enumerate(chunk.spans):
                cur.execute(
                    "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, %s, %s, %s, %s)",
                    (chunk_id, ordinal, span.page, span.char_start, span.char_end),
                )
