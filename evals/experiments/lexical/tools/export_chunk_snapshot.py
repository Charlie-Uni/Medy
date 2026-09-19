"""Read-only export of the existing development chunks for DEC-001 preparation.

The export contains IDs and provenance spans, never full page/chunk text or credentials.
Every row is compared with chunker-v1 regenerated from the frozen extraction's local pages.
This administrative inspection is not a retrieval/RLS test and does not activate documents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from medops.core.config import Settings
from medops.evals.probe.chunk_mapping import publish_artifact
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from medops.ingestion.chunker import CHUNKER_VERSION, chunk_pages
from medops.retrieval.lexical.normalization import normalize_text


class _CachedRawPages(PageTextProvider):
    """Validation and regeneration share the same raw page view, including missing pages."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._raw: dict[tuple[str, int], str | None] = {}

    def raw_page_text(self, source_hash: str, page: int) -> str | None:
        key = (source_hash, page)
        if key not in self._raw:
            path = self.root / source_hash / f"{page}.txt"
            self._raw[key] = path.read_text(encoding="utf-8") if path.is_file() else None
        return self._raw[key]

    def page_text(self, source_hash: str, page: int) -> str | None:
        raw = self.raw_page_text(source_hash, page)
        return normalize_text(raw) if raw is not None else None

    def document_pages(self, source_hash: str, count: int) -> list[str]:
        result = []
        for page in range(1, count + 1):
            raw = self.raw_page_text(source_hash, page)
            if raw is None:
                raise ValueError("source page text is missing")
            result.append(raw)
        return result


def export(version: Path, pages: Path, out: Path) -> dict:
    if out.resolve().is_relative_to(version.resolve()):
        raise ValueError("output must be outside the frozen dataset")
    if out.exists() or out.is_symlink():
        raise ValueError("output already exists")
    names = ("manifest.json", "corpus.json", "samples.jsonl", "SHA256SUMS")
    before = {name: (version / name).read_bytes() for name in names}
    page_view = _CachedRawPages(pages)
    schema_dir = Path(__file__).resolve().parents[4] / "evals/probe/precise_clause/schema"
    report = ProbeSetValidator(schema_dir, pages=page_view).validate(version, mode="frozen")
    if not report.passed:
        raise ValueError("frozen input validation failed")
    if any((version / name).read_bytes() != raw for name, raw in before.items()):
        raise ValueError("frozen input files changed during validation")
    # Use the validated bytes and cached pages, never a subsequent view of these inputs.
    manifest_bytes = before["manifest.json"]
    manifest = json.loads(manifest_bytes)
    corpus = json.loads(before["corpus.json"])
    extraction = {k: manifest["extraction"][k] for k in ("extractor", "extractor_version", "params_hash")}
    settings = Settings()
    secret = settings.database_admin_url or settings.database_url
    chunks: list[dict] = []
    documents: list[dict] = []
    with psycopg.connect(secret.get_secret_value(), row_factory=dict_row) as conn:
        conn.execute("set transaction isolation level repeatable read, read only")
        db_version = conn.execute("show server_version").fetchone()["server_version"]
        migration = conn.execute("select version_num from alembic_version").fetchone()["version_num"]
        for doc in sorted(corpus["documents"], key=lambda d: d["document_key"]):
            matches = conn.execute(
                """select d.doc_id, d.version, d.status, d.parse_quality, d.owner_dept,
                          j.parser_version, j.extraction_params_hash
                   from documents d join source_objects s using (source_object_id)
                   join ingestion_jobs j on j.job_id=d.active_ingestion_job_id
                   where s.source_hash=%s and d.document_key=%s""",
                (doc["source_hash"], doc["document_key"]),
            ).fetchall()
            if len(matches) != 1:
                raise ValueError("expected exactly one stored document per frozen corpus entry")
            stored = matches[0]
            if stored["version"] != doc["version_label"] or stored["owner_dept"] != doc["owner_dept"]:
                raise ValueError("stored document version/department differs from frozen corpus")
            if stored["parser_version"] != f"{extraction['extractor']} {extraction['extractor_version']}":
                raise ValueError("stored extractor version mismatch")
            if stored["extraction_params_hash"] != extraction["params_hash"]:
                raise ValueError("stored extraction parameters mismatch")
            audits = conn.execute(
                "select details from doc_audit where doc_id=%s and action='ingest' order by id",
                (stored["doc_id"],),
            ).fetchall()
            if len(audits) != 1 or audits[0]["details"].get("chunker_version") != CHUNKER_VERSION:
                raise ValueError("missing or mismatched chunker provenance")
            if audits[0]["details"].get("normalization") != manifest["normalization"]:
                raise ValueError("normalization provenance mismatch")
            raw_pages = page_view.document_pages(doc["source_hash"], doc["pages"])
            generated = chunk_pages(raw_pages)
            rows = conn.execute(
                """select c.chunk_id, c.seq, c.content, c.chunk_content_hash,
                       jsonb_agg(jsonb_build_object('page', s.page, 'char_start', s.char_start,
                                  'char_end', s.char_end) order by s.ordinal) as spans
                   from chunks c join chunk_spans s using (chunk_id)
                   where c.doc_id=%s group by c.chunk_id order by c.seq""",
                (stored["doc_id"],),
            ).fetchall()
            total = conn.execute("select count(*) as n from chunks where doc_id=%s", (stored["doc_id"],)).fetchone()[
                "n"
            ]
            if len(rows) != len(generated) or total != len(rows):
                raise ValueError("stored chunk count or span coverage differs from regenerated chunks")
            for row, expected in zip(rows, generated, strict=True):
                spans = [{"page": s.page, "char_start": s.char_start, "char_end": s.char_end} for s in expected.spans]
                if (row["seq"], row["content"], row["chunk_content_hash"], row["spans"]) != (
                    expected.seq,
                    expected.content,
                    expected.content_hash,
                    spans,
                ):
                    raise ValueError("stored chunk content/provenance differs from regenerated chunks")
                chunks.append(
                    {
                        "chunk_id": str(row["chunk_id"]),
                        "source_hash": doc["source_hash"],
                        "version_label": doc["version_label"],
                        "spans": spans,
                    }
                )
            documents.append(
                {
                    "document_key": doc["document_key"],
                    "source_hash": doc["source_hash"],
                    "status": stored["status"],
                    "parse_quality": stored["parse_quality"],
                    "chunks": len(rows),
                }
            )
    payload = {
        "chunker_version": CHUNKER_VERSION,
        "extraction": extraction,
        "normalization": manifest["normalization"],
        "chunks": sorted(chunks, key=lambda c: c["chunk_id"]),
    }
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    publish_artifact(encoded, out, protected_dir=version)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read_only_admin_export_not_retrieval",
        "dataset_hash": manifest["dataset_hash"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "snapshot_sha256": hashlib.sha256(encoded).hexdigest(),
        "postgresql": db_version,
        "migration": migration,
        "documents": documents,
        "chunks": len(chunks),
        "regenerated_chunks_match": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--pages", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = export(args.dataset, args.pages, args.out)
    except (OSError, ValueError, psycopg.Error) as exc:
        # Do not print exception arguments: a driver/config exception can contain a credential.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
