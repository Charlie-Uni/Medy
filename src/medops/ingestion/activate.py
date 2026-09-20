"""Draft -> active activation of ingested documents (the first slice of M1-11).

`activate_document` performs exactly one transition inside the caller's transaction with the audited
identity (`medops.actor`) and reason (`medops.reason`) injected transaction-locally, so the database
triggers of migrations 0001/0004 record the change in `doc_audit`. It refuses, with a readable reason,
what the constraints would reject anyway (INV-DATA-05: only `trusted` parses become active; active
documents need a succeeded ingestion job and an `effective_from`) and one thing the constraints do not
express yet: activating a second version of a family (supersession + archiving is the rest of M1-11 and
is not silently approximated here).

`apply_plan` activates a list of documents all-or-nothing in one transaction, so a partially applied
experiment corpus cannot exist. The CLI runs against the admin DSN (`medops_admin_role` may update
documents; the app roles may not).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg


class ActivationRefused(ValueError):
    """The document cannot be activated as requested; nothing was changed."""


@dataclass(frozen=True)
class Activation:
    document_key: str
    doc_id: str
    effective_from: date
    actor: str


def activate_document(
    conn: psycopg.Connection[Any], document_key: str, effective_from: date, *, actor: str, reason: str
) -> Activation:
    if not actor or not reason:
        raise ActivationRefused("actor and reason are required (audit)")
    with conn.transaction():
        conn.execute("select set_config('medops.actor', %s, true)", (actor,))
        conn.execute("select set_config('medops.reason', %s, true)", (reason,))
        row = conn.execute(
            "select doc_id, family_id, status::text, parse_quality::text, active_ingestion_job_id "
            "from documents where document_key = %s for update",
            (document_key,),
        ).fetchone()
        if row is None:
            raise ActivationRefused(f"{document_key}: unknown document_key")
        doc_id, family_id, status, quality, job_id = row
        if status != "draft":
            raise ActivationRefused(f"{document_key}: status is {status}, only draft documents can be activated")
        if quality != "trusted":
            raise ActivationRefused(
                f"{document_key}: parse_quality is {quality}; INV-DATA-05 allows only trusted parses"
            )
        if job_id is None:
            raise ActivationRefused(f"{document_key}: no active_ingestion_job_id")
        other = conn.execute(
            "select document_key from documents where family_id = %s and status = 'active' and doc_id <> %s",
            (family_id, doc_id),
        ).fetchone()
        if other is not None:
            raise ActivationRefused(
                f"{document_key}: family already has an active version ({other[0]}); supersession is M1-11, not this tool"
            )
        conn.execute(
            "update documents set status = 'active', effective_from = %s where doc_id = %s", (effective_from, doc_id)
        )
    return Activation(document_key=document_key, doc_id=str(doc_id), effective_from=effective_from, actor=actor)


def apply_plan(conn: psycopg.Connection[Any], plan: Sequence[dict[str, Any]], *, actor: str) -> list[Activation]:
    """Activate every entry with a non-null `effective_from`, all-or-nothing. Entries with
    `effective_from: null` are skipped (they must carry a `flag` explaining why)."""
    done: list[Activation] = []
    with conn.transaction():
        for entry in plan:
            when = entry.get("effective_from")
            if when is None:
                if not entry.get("flag") and not entry.get("tier") == "blocked":
                    raise ActivationRefused(f"{entry.get('document_key')}: null effective_from without a flag")
                continue
            reason = f"{entry.get('tier', 'unspecified')}: {entry.get('source', '')}".strip()
            done.append(
                activate_document(conn, entry["document_key"], date.fromisoformat(when), actor=actor, reason=reason)
            )
    return done


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Activate draft documents (draft -> active) with an audited reason")
    parser.add_argument("--admin-url", required=True, help="admin DSN (medops_admin_role member or superuser)")
    parser.add_argument("--actor", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--plan", type=Path, help="JSON with a `documents` list (document_key, effective_from, tier, source)"
    )
    group.add_argument("--document-key")
    parser.add_argument("--effective-from", type=date.fromisoformat)
    parser.add_argument("--reason")
    args = parser.parse_args(argv)
    try:
        with psycopg.connect(args.admin_url) as conn:
            if args.plan:
                entries = json.loads(args.plan.read_text(encoding="utf-8"))["documents"]
                done = apply_plan(conn, entries, actor=args.actor)
            else:
                if not args.effective_from or not args.reason:
                    parser.error("--effective-from and --reason are required with --document-key")
                done = [
                    activate_document(
                        conn, args.document_key, args.effective_from, actor=args.actor, reason=args.reason
                    )
                ]
            conn.commit()
    except ActivationRefused as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {"status": "activated", "count": len(done), "documents": [a.document_key for a in done]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
