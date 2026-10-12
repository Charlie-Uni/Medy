"""ARCH-12: isolated PostgreSQL connection/transaction diagnostic, never a QA benchmark.

Run with an explicit MEDOPS_TEST_ADMIN_URL; a temporary migrated database and
temporary LOGIN users are created and dropped by the existing integration fixture.
Only synthetic facts and a simulated external wait are used. No model is loaded,
and no hosted gateway is called. The phased arm is a diagnostic prototype, not a
production implementation: its committed operation intent changes rollback semantics.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import statistics
import threading
import time
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

import psycopg

from medops.bootstrap.runtime import ProductionRuntime
from medops.core.config import Settings
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.executions import PgExecutionStore
from medops.infrastructure.identity import Authenticator
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.retrieval.recheck import recheck_candidates
from tests.support.database import make_database
from tests.support.documents import document, job, source_object

AS_OF = date(2026, 10, 11)
PRINCIPAL = "a" * 64
VERSIONS = VersionSet(
    policy_version="arch12-synthetic", retrieval_version="arch12-synthetic", model_config_version="no-model"
)


class _NoTokenVerifier:
    def verify(self, _token: str) -> Mapping[str, Any]:
        raise RuntimeError("token verification is outside the transaction diagnostic")


def _seed(owner: str, number: int = 188) -> str:
    with psycopg.connect(owner) as conn:
        src = source_object(conn, number)
        conn.execute(
            "update source_objects set integrity_status='verified', last_verified_at=now() where source_object_id=%s",
            (src,),
        )
        doc = document(
            conn,
            src,
            job(conn, src),
            status="active",
            parse_quality="trusted",
            effective_from=date(2026, 1, 1),
            owner_dept="MA",
        )
        conn.execute("insert into document_acl (doc_id,dept,granted_by) values (%s,'MA','diagnostic')", (doc,))
        text = "Synthetic guidance: record the event date and the suspect product."
        cid = conn.execute(
            "insert into chunks (doc_id,seq,page,section,content) values (%s,0,1,'S1',%s) returning chunk_id",
            (doc, text),
        ).fetchone()[0]
        conn.execute(
            "insert into chunk_spans (chunk_id,ordinal,page,char_start,char_end) values (%s,0,1,0,%s)",
            (cid, len(text)),
        )
        conn.execute(
            "insert into principals (sub_pseudonym,dept,roles,scopes,created_by) "
            "values (%s,'MA',array['analyst'],array['MA:read'],'diagnostic') on conflict do nothing",
            (PRINCIPAL,),
        )
    return str(cid)


def _runtime(dsn: str) -> ProductionRuntime:
    # Use the real production connection owner; avoid from_settings(), which loads
    # inference models and released policies. These dependencies are never invoked.
    settings = Settings(_env_file=None, database_url=dsn, redis_url="redis://localhost:6379/0")
    auth = Authenticator(verifier=_NoTokenVerifier(), pseudonym_key=b"arch12-synthetic")
    return ProductionRuntime(
        settings=settings,
        authenticator=auth,
        gateway=FakeModelGateway(),
        embedding=None,
        reranker=None,
        versions=VERSIONS,
        _dsn=dsn,
    )


def _percentile(values: list[float], p: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)]


def _arm(runtime, owner, cid, *, mode, concurrency, rounds, wait_s, slots):
    label = "arch12-" + uuid.uuid4().hex[:16]
    limiter = threading.BoundedSemaphore(slots) if slots else None
    durations: list[float] = []
    leases: list[float] = []
    samples: list[tuple[float, int, int, int]] = []
    monitor_errors: list[Exception] = []
    stopped = threading.Event()

    @contextmanager
    def phase():
        if limiter:
            limiter.acquire()
        acquired = time.perf_counter()
        try:
            with runtime.connection() as conn:
                conn.execute("select set_config('application_name',%s,true)", (label,))
                u = runtime.resolve_user(conn, PRINCIPAL)
                assert u is not None
                runtime.bind_identity(conn, u)
                yield conn, u
        finally:
            leases.append((time.perf_counter() - acquired) * 1000)
            if limiter:
                limiter.release()

    def monitor():
        try:
            with psycopg.connect(
                owner, autocommit=True, connect_timeout=3, options="-c statement_timeout=1000"
            ) as conn:
                while not stopped.is_set():
                    row = conn.execute(
                        """select count(*),count(*) filter(where state='idle in transaction'),
                                  count(*) filter(where wait_event_type='Lock')
                           from pg_stat_activity where application_name=%s""",
                        (label,),
                    ).fetchone()
                    samples.append((time.perf_counter(), *row))
                    stopped.wait(0.01)
        except Exception as exc:  # noqa: BLE001 - report in the main thread without leaking a connection error
            monitor_errors.append(exc)

    def initial(conn, u, key):
        evidence = recheck_candidates(conn, [cid], as_of=AS_OF).evidence
        assert len(evidence) == 1
        claim = PgExecutionStore(conn).claim(
            operation_key=key,
            operation_scope=label,
            run_id=key,
            trace_id=key,
            node_name="synthetic-wait",
            versions=VERSIONS.model_dump(mode="json"),
            now=datetime.now(UTC),
        )
        assert claim.kind == "new"
        return evidence, u

    def final(conn, u, key, before):
        evidence, principal = before
        assert runtime.resolve_user(conn, PRINCIPAL) == u == principal
        assert recheck_candidates(conn, [cid], as_of=AS_OF).evidence == evidence
        PgExecutionStore(conn).complete(key, {"diagnostic": True}, datetime.now(UTC))

    def request():
        key = uuid.uuid4().hex + uuid.uuid4().hex
        started = time.perf_counter()
        if mode == "held":
            with phase() as (conn, u):
                before = initial(conn, u, key)
                time.sleep(wait_s)  # simulated external work, never pg_sleep or a hosted API
                final(conn, u, key, before)
        else:
            with phase() as (conn, u):
                before = initial(conn, u, key)
            time.sleep(wait_s)
            with phase() as (conn, u):
                final(conn, u, key, before)
        return (time.perf_counter() - started) * 1000

    observer = threading.Thread(target=monitor, name="arch12-monitor")
    observer.start()
    started = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            durations = list(pool.map(lambda _: request(), range(concurrency * rounds)))
    finally:
        stopped.set()
        observer.join(timeout=5)
        assert not observer.is_alive()
    if monitor_errors:
        raise RuntimeError("diagnostic monitor failed") from None
    assert samples
    elapsed = time.perf_counter() - started
    with psycopg.connect(owner) as conn:
        counts = conn.execute(
            "select status,count(*) from operation_executions where operation_scope=%s group by status", (label,)
        ).fetchall()
        assert sum(n for status, n in counts if status == "succeeded") == len(durations)
        assert all(status == "succeeded" for status, _n in counts)
    return {
        "mode": mode,
        "concurrency": concurrency,
        "synthetic_connection_slots": slots,
        "n": len(durations),
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "elapsed_s": round(elapsed, 3),
        "requests_per_s": round(len(durations) / elapsed, 3),
        "connection_leases": len(leases),
        "lease_ms_per_request": round(sum(leases) / len(durations), 3),
        "peak_observed_backends": max(s[1] for s in samples),
        "peak_idle_in_transaction": max(s[2] for s in samples),
        "lock_wait_samples": sum(s[3] for s in samples),
        "monitor_samples": len(samples),
        "mean_observed_backends": round(statistics.mean(s[1] for s in samples), 3),
    }


def _locks_and_freshness(runtime, owner, cid):
    user = UserContext(user_id=PRINCIPAL, dept=Dept.MA, roles=("analyst",), acl_scopes=frozenset({"MA:read"}))
    with runtime.connection() as conn:
        runtime.bind_identity(conn, user)
        before = recheck_candidates(conn, [cid], as_of=AS_OF).evidence
        assert len(before) == 1
        isolation = conn.execute("show transaction_isolation").fetchone()[0]
        with psycopg.connect(owner) as other:
            other.execute("set local lock_timeout='200ms'")
            try:
                other.execute("lock table documents in access exclusive mode nowait")
            except psycopg.errors.LockNotAvailable as exc:
                ddl_sqlstate = exc.sqlstate
            else:
                raise AssertionError("the held fact read should conflict with ACCESS EXCLUSIVE")
        # The failed lock transaction above rolled back. Plain ACL DML must still
        # commit; a table read lock is not a lock on the document's authorisation.
        with psycopg.connect(owner) as other:
            other.execute("set local lock_timeout='200ms'")
            changed = other.execute(
                "delete from document_acl where doc_id=%s and dept='MA'", (before[0].citation.doc_id,)
            )
            assert changed.rowcount == 1
        after = recheck_candidates(conn, [cid], as_of=AS_OF)
        assert not after.evidence and after.rejected[0].reason.value == "not_visible"
        assert before[0].text  # cached Python evidence is not automatically invalidated
    with psycopg.connect(owner) as conn:
        conn.execute("lock table documents in access exclusive mode nowait")  # released when request closed
        conn.execute(
            "insert into document_acl(doc_id,dept,granted_by) values (%s,'MA','diagnostic')",
            (before[0].citation.doc_id,),
        )
    return {
        "isolation": isolation,
        "held_transaction_blocks_ddl_sqlstate": ddl_sqlstate,
        "acl_delete_commits_while_fact_transaction_open": True,
        "fresh_read_rejects_revoked_evidence": True,
        "cached_python_evidence_remains": True,
        "ddl_lock_succeeds_after_request_close": True,
    }


def _freshness_cases(runtime, owner):
    results = {}
    for number, change in enumerate(("archive", "source_integrity", "content_hash", "principal_deactivate"), start=190):
        cid = _seed(owner, number)
        with runtime.connection() as conn:
            user = runtime.resolve_user(conn, PRINCIPAL)
            assert user is not None
            runtime.bind_identity(conn, user)
            before = recheck_candidates(conn, [cid], as_of=AS_OF).evidence
            assert len(before) == 1
            with psycopg.connect(owner) as other:
                other.execute("set local lock_timeout='200ms'")
                if change == "archive":
                    other.execute("select set_config('medops.actor','arch12-diagnostic',true)")
                    other.execute("select set_config('medops.reason','synthetic archive drift',true)")
                    other.execute(
                        "update documents set status='archived',effective_to=%s where doc_id=%s",
                        (AS_OF, before[0].citation.doc_id),
                    )
                elif change == "source_integrity":
                    other.execute(
                        "update source_objects set integrity_status='failed' where source_object_id="
                        "(select source_object_id from documents where doc_id=%s)",
                        (before[0].citation.doc_id,),
                    )
                elif change == "content_hash":
                    # Simulate storage corruption in this owned throwaway database.
                    # Normal writes cannot bypass the production immutability guard.
                    other.execute("set local session_replication_role='replica'")
                    other.execute("update chunks set content=content||' tampered' where chunk_id=%s", (cid,))
                else:
                    other.execute("update principals set active=false where sub_pseudonym=%s", (PRINCIPAL,))
            fresh_user = runtime.resolve_user(conn, PRINCIPAL)
            after = recheck_candidates(conn, [cid], as_of=AS_OF)
            assert fresh_user != user or after.evidence != before
            results[change] = {
                "final_comparison_rejects": True,
                "fresh_principal_matches": fresh_user == user,
                "fresh_evidence_matches": after.evidence == before,
                "rejection_reasons": [r.reason.value for r in after.rejected],
            }
    return results


def run(*, concurrency: int, rounds: int, wait_s: float) -> dict[str, Any]:
    dsn = os.environ.get("MEDOPS_TEST_ADMIN_URL")
    if not dsn:
        raise ValueError("MEDOPS_TEST_ADMIN_URL is required; no developer database fallback")
    with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as conn:
        server = {
            "version": conn.execute("show server_version").fetchone()[0],
            "max_connections": int(conn.execute("show max_connections").fetchone()[0]),
            "reserved_connections": int(conn.execute("show reserved_connections").fetchone()[0]),
            "superuser_reserved_connections": int(conn.execute("show superuser_reserved_connections").fetchone()[0]),
            "backends_before_diagnostic": conn.execute(
                "select count(*) from pg_stat_activity where backend_type='client backend'"
            ).fetchone()[0],
        }
    gen = make_database(dsn)
    db = next(gen)
    try:
        cid = _seed(db["owner"])
        runtime = _runtime(db["users"]["app"])
        # Alternating order controls simple warm-up drift; record each round, do
        # not infer operational capacity from an intentionally imposed limiter.
        arms = []
        for repetition in range(3):
            for slots in (None, max(1, concurrency // 2)):
                modes = ("held", "phased") if repetition % 2 == 0 else ("phased", "held")
                for mode in modes:
                    row = _arm(
                        runtime,
                        db["owner"],
                        cid,
                        mode=mode,
                        concurrency=concurrency,
                        rounds=rounds,
                        wait_s=wait_s,
                        slots=slots,
                    )
                    arms.append({"repetition": repetition + 1, **row})
        facts = _locks_and_freshness(runtime, db["owner"], cid)
        freshness = _freshness_cases(runtime, db["owner"])
        assert runtime.gateway.calls == []
        with psycopg.connect(db["owner"]) as conn:
            assert conn.execute("select count(*) from llm_spend_reservations").fetchone()[0] == 0
        return {
            "method": "actual ProductionRuntime.connection; synthetic fact/operation key; alternating arms; final fact/principal comparison in BOTH arms",
            "external_wait_s": wait_s,
            "server": server,
            "arms": arms,
            "locks_and_freshness": facts,
            "freshness_cases": freshness,
            "hosted_calls": 0,
            "cost_usd": 0,
            "limitations": [
                "not real QA or model capacity",
                "phased arm commits initial intent separately; atomicity/recovery contract not implemented",
                "sampled backend peaks are lower bounds; client lease timing includes connect/close",
                "monitor connection and test setup are excluded from arm counts",
                "synthetic slot limiter is not deployed pooling",
            ],
        }
    finally:
        gen.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--wait-ms", type=float, default=250)
    args = parser.parse_args()
    if (
        not 2 <= args.concurrency <= 16
        or not 1 <= args.rounds <= 10
        or not math.isfinite(args.wait_ms)
        or not 1 <= args.wait_ms <= 1000
    ):
        parser.error("require concurrency 2..16, rounds 1..10, wait-ms 1..1000")
    try:
        report = run(concurrency=args.concurrency, rounds=args.rounds, wait_s=args.wait_ms / 1000)
    except Exception as exc:  # noqa: BLE001 - never print a DSN, SQL argument or confidential exception message
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
