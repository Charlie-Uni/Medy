"""Batch loader: ingest the documents of a probe corpus.json into the fact plane.

    python -m medops.ingestion.load --corpus <corpus.json> --sources-dir <dir> --pages-dir <dir> --actor <id>
                                    [--only key,key] [--accept-pii key=reason ...] [--accept-quality key=reason ...] [--admin-url <dsn>]

Runs as the admin role (MEDOPS_MIGRATION_URL, else Settings DATABASE_ADMIN_URL / DATABASE_URL). One
transaction per document; a refusal leaves that document untouched and is reported, the run continues
and exits 1 at the end when anything was refused. Documents already present (same key and version)
are reported as `exists`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

from medops.ingestion.av import ClamdScanner
from medops.ingestion.pipeline import DocumentSpec, IngestRefused, SharedSourceApproval, ingest_document


def _source_file(sources_dir: Path, source_hash: str) -> Path:
    """`<hash>.pdf` or `<hash>.docx` (the pipeline decides the format by signature, not by extension)."""
    for ext in ("pdf", "docx"):
        candidate = sources_dir / f"{source_hash}.{ext}"
        if candidate.is_file():
            return candidate
    return sources_dir / f"{source_hash}.pdf"  # reported as missing by the pipeline


def _scanner() -> ClamdScanner | None:
    from medops.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    return ClamdScanner(settings.clamd_address) if settings.clamd_address else None


def _admin_url() -> str:
    explicit = os.environ.get("MEDOPS_MIGRATION_URL")
    if explicit:
        return explicit
    from medops.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    return (settings.database_admin_url or settings.database_url).get_secret_value()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medops.ingestion.load")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True, help="directory holding <source_hash>.pdf files")
    parser.add_argument(
        "--pages-dir", type=Path, default=None, help="stored page texts to cross-check extraction against"
    )
    parser.add_argument("--actor", required=True, help="surrogate id written to doc_audit")
    parser.add_argument("--only", default=None, help="comma-separated document_key list")
    parser.add_argument(
        "--accept-pii",
        action="append",
        default=[],
        metavar="KEY=REASON",
        help="override a PII refusal for one document, with the review reason",
    )
    parser.add_argument(
        "--accept-quality",
        action="append",
        default=[],
        metavar="KEY=REASON",
        help="reviewer decision that upgrades a document with pypdf warnings from low_trust to trusted (audited)",
    )
    parser.add_argument(
        "--supersedes",
        action="append",
        default=[],
        metavar="NEWKEY=OLDKEY",
        help="ingest NEWKEY as the next version of OLDKEY's family (M1-11 publish chain)",
    )
    parser.add_argument(
        "--share-source",
        action="append",
        default=[],
        metavar="KEY=ADMIN:REASON",
        help="administrator confirmation that KEY may reference a source object already backing another document (audited)",
    )
    parser.add_argument("--admin-url", default=None)
    parser.add_argument(
        "--no-av",
        action="store_true",
        help="skip the clamd scan even if CLAMD_ADDRESS is set (dev only; audited as skipped)",
    )
    args = parser.parse_args(argv)
    shared: dict[str, SharedSourceApproval] = {}
    for item in args.share_source:
        key, _, decision = item.partition("=")
        approver, _, reason = decision.partition(":")
        if not key or not approver.strip() or not reason.strip():
            print(f"--share-source needs KEY=ADMIN:REASON, got {item!r}")
            return 2
        shared[key] = SharedSourceApproval(approved_by=approver.strip(), reason=reason.strip())
    supersedes_keys: dict[str, str] = {}
    for item in args.supersedes:
        new_key, _, old_key = item.partition("=")
        if not new_key or not old_key.strip():
            print(f"--supersedes needs NEWKEY=OLDKEY, got {item!r}")
            return 2
        supersedes_keys[new_key] = old_key.strip()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    only = set(args.only.split(",")) if args.only else None
    overrides: dict[str, str] = {}
    for item in args.accept_pii:
        key, _, reason = item.partition("=")
        if not key or not reason.strip():
            print(f"--accept-pii needs KEY=REASON, got {item!r}")
            return 2
        overrides[key] = reason.strip()
    quality_overrides: dict[str, str] = {}
    for item in args.accept_quality:
        key, _, reason = item.partition("=")
        if not key or not reason.strip():
            print(f"--accept-quality needs KEY=REASON, got {item!r}")
            return 2
        quality_overrides[key] = reason.strip()

    refused = 0
    scanner = None if args.no_av else _scanner()
    with psycopg.connect(args.admin_url or _admin_url()) as conn:
        for record in corpus["documents"]:
            spec = DocumentSpec.from_corpus_record(record)
            if only is not None and spec.document_key not in only:
                continue
            pdf = _source_file(args.sources_dir, spec.source_hash)
            line: dict[str, object] = {"document_key": spec.document_key}
            try:
                with conn.transaction():
                    supersedes_id = None
                    if spec.document_key in supersedes_keys:
                        row = conn.execute(
                            "select doc_id from documents where document_key = %s",
                            (supersedes_keys[spec.document_key],),
                        ).fetchone()
                        if row is None:
                            raise IngestRefused(f"--supersedes target {supersedes_keys[spec.document_key]} not found")
                        supersedes_id = row[0]
                    result = ingest_document(
                        conn,
                        spec,
                        pdf,
                        actor=args.actor,
                        pages_dir=args.pages_dir,
                        pii_override_reason=overrides.get(spec.document_key),
                        quality_override_reason=quality_overrides.get(spec.document_key),
                        supersedes=supersedes_id,
                        shared_source=shared.get(spec.document_key),
                        scanner=scanner,
                    )
                line.update(
                    status=result.status,
                    doc_id=str(result.doc_id),
                    chunks=result.chunk_count,
                    parse_quality=result.parse_quality,
                    pii_hits=len(result.pii_hits),
                )
            except (IngestRefused, FileNotFoundError) as exc:
                refused += 1
                line.update(status="refused", reason=str(exc))
            print(json.dumps(line, ensure_ascii=False))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
