"""Read-only administrative facts for evaluation judges; never a user retrieval path."""

from __future__ import annotations

from typing import Self

import psycopg

from medops.evals.safety_data import admin_dsn


class FactLookups:
    admin: psycopg.Connection

    def resolve_chunks(self, chunk_ids: list[str]) -> dict[str, dict]:
        ids = sorted({c for c in chunk_ids if c})
        if not ids:
            return {}
        rows = self.admin.execute(
            """select c.chunk_id::text, d.doc_id::text, d.document_key, d.status::text, so.source_hash
               from chunks c join documents d on d.doc_id = c.doc_id
               join source_objects so on so.source_object_id = d.source_object_id
               where c.chunk_id::text = any(%s)""",
            (ids,),
        ).fetchall()
        return {r[0]: {"doc_id": r[1], "document_key": r[2], "status": r[3], "source_hash": r[4]} for r in rows}

    def docs_for_hashes(self, hashes: list[str]) -> dict[str, str]:
        rows = self.admin.execute(
            """select so.source_hash, d.document_key from documents d
               join source_objects so on so.source_object_id = d.source_object_id where so.source_hash = any(%s)""",
            (hashes,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def canary_chunks(self, canary: str) -> list[str]:
        return [
            r[0]
            for r in self.admin.execute(
                "select chunk_id::text from chunks where content like %s", (f"%{canary}%",)
            ).fetchall()
        ]


class AdminPlane(FactLookups):
    def __init__(self, name: str):
        self.name = name
        self.admin = psycopg.connect(admin_dsn(name))
        self.admin.read_only = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.admin.close()
