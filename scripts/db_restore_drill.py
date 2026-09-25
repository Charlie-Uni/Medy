"""Restore drill (M5-06, record 87): restore a dump into a scratch database, compare it with the source, drop it.

    python scripts/db_restore_drill.py --dump backups/<db>-<stamp>.dump [--source medops] [--out evals/harness/runs/<run>]

Compares the alembic revision, the set of public tables, per-table row counts, the corpus fingerprint (md5 over the
ordered chunk hashes) and the granted roles between the live source database and the restored copy; writes
report.json / report.md; always drops the scratch database. `pg_restore` runs inside the Postgres container.
Nothing secret leaves the process.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse

import psycopg
from psycopg import sql


def inventory(dsn: str) -> dict:
    with psycopg.connect(dsn) as conn:
        tables = sorted(r[0] for r in conn.execute("select tablename from pg_tables where schemaname = 'public'"))
        counts = {
            t: conn.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(t))).fetchone()[0] for t in tables
        }
        rev = conn.execute("select version_num from alembic_version").fetchone()[0]
        corpus = ""
        if "chunks" in tables:
            corpus = conn.execute(
                "select coalesce(md5(string_agg(chunk_content_hash::text, '' order by chunk_id)), '') from chunks"
            ).fetchone()[0]
        grantees = sorted(
            r[0]
            for r in conn.execute(
                "select distinct grantee from information_schema.role_table_grants where table_schema = 'public' and grantee like 'medops_%'"
            )
        )
    return {"alembic": rev, "tables": tables, "counts": counts, "corpus_md5": corpus, "grantees": grantees}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=pathlib.Path, required=True)
    ap.add_argument("--source", default=None)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--container", default=os.environ.get("MEDOPS_PG_CONTAINER", "medops-postgres"))
    args = ap.parse_args()
    dsn = os.environ.get("DATABASE_ADMIN_URL")
    if not dsn:
        print("DATABASE_ADMIN_URL is required", file=sys.stderr)
        return 2
    u = urllib.parse.urlsplit(dsn)
    source = args.source or u.path.lstrip("/")
    user, password = urllib.parse.unquote(u.username or ""), urllib.parse.unquote(u.password or "")
    scratch = f"{source}_restore_drill"
    source_dsn = re.sub(r"/[^/?]+(\?|$)", f"/{source}\\1", dsn)
    scratch_dsn = re.sub(r"/[^/?]+(\?|$)", f"/{scratch}\\1", dsn)
    maint_dsn = re.sub(r"/[^/?]+(\?|$)", r"/postgres\1", dsn)
    out = args.out or pathlib.Path("evals/harness/runs") / f"{dt.date.today().isoformat()}-backup-drill"
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "dump": args.dump.name,
        "dump_sha256": hashlib.sha256(args.dump.read_bytes()).hexdigest(),
        "dump_bytes": args.dump.stat().st_size,
        "source": source,
        "scratch": scratch,
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    t0 = dt.datetime.now(dt.UTC)
    with psycopg.connect(maint_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(scratch)))
        conn.execute(sql.SQL("create database {}").format(sql.Identifier(scratch)))
    diffs: dict = {}
    src: dict = {}
    try:
        with args.dump.open("rb") as fh:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    "-e",
                    f"PGPASSWORD={password}",
                    args.container,
                    "pg_restore",
                    "-U",
                    user,
                    "-h",
                    "localhost",
                    "-d",
                    scratch,
                    "--no-owner",
                    "--exit-on-error",
                ],
                stdin=fh,
                stderr=subprocess.PIPE,
            )
        report["pg_restore_rc"] = proc.returncode
        report["pg_restore_stderr_tail"] = proc.stderr.decode()[-400:]
        report["restore_seconds"] = round((dt.datetime.now(dt.UTC) - t0).total_seconds(), 1)
        src, dst = inventory(source_dsn), inventory(scratch_dsn)
        diffs = {
            t: (src["counts"].get(t), dst["counts"].get(t))
            for t in set(src["counts"]) | set(dst["counts"])
            if src["counts"].get(t) != dst["counts"].get(t)
        }
        report.update(
            {
                "alembic": src["alembic"],
                "tables": len(src["tables"]),
                "total_rows": sum(src["counts"].values()),
                "row_count_mismatches": diffs,
                "tables_match": src["tables"] == dst["tables"],
                "alembic_match": src["alembic"] == dst["alembic"],
                "corpus_match": src["corpus_md5"] == dst["corpus_md5"],
                "grantees_match": src["grantees"] == dst["grantees"],
            }
        )
        report["ok"] = (
            proc.returncode == 0
            and not diffs
            and report["tables_match"]
            and report["alembic_match"]
            and report["corpus_match"]
            and report["grantees_match"]
        )
    finally:
        with psycopg.connect(maint_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(scratch)))
        report["scratch_dropped"] = True
    report["finished_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    lines = [
        f"# Backup / restore drill ({report['started_at'][:10]})",
        "",
        f"- dump `{args.dump.name}` ({report['dump_bytes']} bytes, sha256 {report['dump_sha256'][:16]}…), source `{source}`, scratch `{scratch}` (dropped afterwards)",
        f"- pg_restore rc {report.get('pg_restore_rc')} in {report.get('restore_seconds')} s; alembic {src.get('alembic')}; {len(src.get('tables', []))} tables; {report.get('total_rows')} rows",
        f"- tables match: {report.get('tables_match')}; alembic match: {report.get('alembic_match')}; corpus md5 match: {report.get('corpus_match')}; grantees match: {report.get('grantees_match')}; row-count mismatches: {diffs or 'none'}",
        f"- **ok: {report.get('ok')}**",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines))
    print(
        "OK" if report.get("ok") else "FAILED",
        json.dumps({k: report.get(k) for k in ("pg_restore_rc", "restore_seconds", "total_rows", "ok")}),
    )
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
