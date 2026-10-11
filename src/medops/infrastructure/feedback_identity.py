"""Destination-local, immutable feedback namespace bindings for pre-UUID score queues.

Legacy score IDs and metadata cannot be rewritten. An operator binds the old runtime
hash explicitly to a persistent UUID; future events keep that namespace while scans
use the UUID. Back up this small mapping together with the delivery queue.
"""

from __future__ import annotations

import json
import re
import sqlite3

from medops.infrastructure.db.fact_plane import canonical_fact_plane_id


def feedback_namespace(conn: sqlite3.Connection, source: str, *, legacy_source: str | None = None) -> str:
    canonical_fact_plane_id(source)
    if legacy_source is not None and not re.fullmatch(r"[0-9a-f]{64}", legacy_source):
        raise ValueError("legacy feedback source must be an explicit runtime hash")
    if conn.in_transaction:
        raise ValueError("feedback binding requires a completed queue transaction")
    with conn:
        conn.execute("begin immediate")  # Serialize claims by different source collectors.
        row = conn.execute("select namespace from feedback_sources where source=?", (source,)).fetchone()
        if row:
            if legacy_source is not None and row[0] != legacy_source:
                raise ValueError("feedback source binding is immutable")
            return str(row[0])
        namespace = legacy_source or source
        if conn.execute("select 1 from feedback_sources where namespace=?", (namespace,)).fetchone():
            raise ValueError("feedback namespace already belongs to another fact plane")
        if legacy_source is None:
            claimed = {r[0] for r in conn.execute("select namespace from feedback_sources")}
            legacy = {r[0] for r in conn.execute("select source from scans") if re.fullmatch(r"[0-9a-f]{64}", r[0])}
            # A crash can leave durable scores before the first cursor write. Look only at controlled metadata.
            for (payload,) in conn.execute(
                "select payload from scores where instr(payload,'authenticated_user_feedback') > 0"
            ):
                meta = json.loads(payload)["body"]["metadata"]
                old = meta.get("fact_plane", "")
                if meta.get("source") == "authenticated_user_feedback" and re.fullmatch(r"[0-9a-f]{64}", old):
                    legacy.add(old)
            if legacy - claimed:
                raise ValueError("legacy feedback requires an explicit source binding before collection")
        conn.execute("insert into feedback_sources(source,namespace) values (?,?)", (source, namespace))
        # Start a full sweep. Existing payloads/remote IDs deduplicate; never trust an old volatile cursor.
        return namespace
