"""Write evals/safety_set/acl_targets.json: for every active production document, its source hash, owner dept, title
and version, read from medops_v2 (spec-s1 §5: C/D/F classes use the production corpus unchanged). The C1/D2/F
authoring modules read this file so that forbidden hashes and must_cite keys are never typed by hand."""

from __future__ import annotations

import json
import pathlib
import sys

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from medops.evals.safety_data import PRODUCTION_DB, SAFETY, admin_dsn  # noqa: E402

OUT = SAFETY / "acl_targets.json"


def main() -> int:
    with psycopg.connect(admin_dsn(PRODUCTION_DB)) as conn:
        rows = conn.execute(
            """select d.document_key, d.title, d.owner_dept::text, d.status::text, d.version, d.effective_from::text, d.effective_to::text, d.family_id::text,
                      so.source_hash, (select string_agg(a.dept::text, ',' order by a.dept::text) from document_acl a where a.doc_id = d.doc_id and a.permission = 'read')
               from documents d join source_objects so on so.source_object_id = d.source_object_id
               order by d.owner_dept, d.document_key, d.version"""
        ).fetchall()
    docs = [
        dict(
            zip(
                (
                    "document_key",
                    "title",
                    "owner_dept",
                    "status",
                    "version",
                    "effective_from",
                    "effective_to",
                    "family_id",
                    "source_hash",
                    "acl_read",
                ),
                r,
                strict=True,
            )
        )
        for r in rows
    ]
    OUT.write_text(
        json.dumps({"database": PRODUCTION_DB, "documents": docs}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{len(docs)} documents -> {OUT.relative_to(SAFETY.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
