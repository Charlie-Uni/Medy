"""Admin views over documents (M3-03): metadata, read ACL and audit tail. Runs on the admin role; never returns
chunk content."""

from __future__ import annotations

from typing import Any


class PgDocumentAdminStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    _COLUMNS = (
        "d.doc_id::text, d.document_key, d.family_id::text, d.title, d.doc_type::text, d.owner_dept::text, d.status::text, "
        "d.version, d.effective_from, d.effective_to, d.parse_quality::text, d.language, d.created_at, "
        "coalesce((select array_agg(a.dept::text order by a.dept::text) from document_acl a where a.doc_id = d.doc_id and a.permission = 'read'), '{}')"
    )

    def _row(self, r: Any) -> dict[str, Any]:
        keys = (
            "doc_id",
            "document_key",
            "family_id",
            "title",
            "doc_type",
            "owner_dept",
            "status",
            "version",
            "effective_from",
            "effective_to",
            "parse_quality",
            "language",
            "created_at",
            "read_depts",
        )
        d = dict(zip(keys, r, strict=True))
        d["read_depts"] = tuple(d["read_depts"])
        return d

    def list(
        self, *, dept: str | None = None, status: str | None = None, family_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if dept:
            clauses.append("d.owner_dept = %s::dept")
            params.append(dept)
        if status:
            clauses.append("d.status = %s::doc_status")
            params.append(status)
        if family_id:
            clauses.append("d.family_id = %s::uuid")
            params.append(family_id)
        where = ("where " + " and ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"select {self._COLUMNS} from documents d {where} order by d.owner_dept, d.document_key, d.version limit %s",
            (*params, limit),
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, doc_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            f"select {self._COLUMNS} from documents d where d.doc_id = %s::uuid", (doc_id,)
        ).fetchone()
        if row is None:
            return None
        d = self._row(row)
        d["audit"] = [
            {
                "action": a[0],
                "from_status": a[1],
                "to_status": a[2],
                "actor": a[3],
                "reason": a[4],
                "occurred_at": a[5],
            }
            for a in self._conn.execute(
                "select action, from_status::text, to_status::text, actor, reason, occurred_at from doc_audit "
                "where doc_id = %s::uuid order by occurred_at desc, id desc limit 20",
                (doc_id,),
            ).fetchall()
        ]
        return d

    def document_key(self, doc_id: str) -> str | None:
        row = self._conn.execute("select document_key from documents where doc_id = %s::uuid", (doc_id,)).fetchone()
        return row[0] if row else None
