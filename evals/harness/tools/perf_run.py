"""Performance gate run (M3-11; baseline 5.11 / 5.12): the real API process under fixed concurrency levels on a
fixed question set, then the worker over a batch of Skill tasks, with server-side attribution from OpenTelemetry.

    python evals/harness/tools/perf_run.py --out evals/harness/runs/<run> --queries <queries.json> \
        --api-cmd "python -m medops.api.serve --port 8010 --device mps" \
        --worker-cmd "python -m medops.worker.serve --device mps" \
        --issuer-pem <pem> --kid <kid> --issuer <iss> --audience <aud> --sub <subject> [--tasks 8] [--otlp-port 4319]

What it measures and how:
- the tool starts an OTLP/HTTP receiver, then the API with `OTEL_EXPORTER_OTLP_ENDPOINT` pointing at it, so every
  request's spans (http.request, harness.node, retrieval.fact_plane, retrieval.rerank, llm.call) arrive here and
  are joined to the request by `medops.trace_id`; nothing else is instrumented or changed in the service;
- each level in the queries file (`{"name", "concurrency", "queries": [{"id", "query", "expect"}]}`) is submitted
  with a thread pool of that size; the client wall time per request is the number the gate is judged on;
- levels are meant to use disjoint questions; a final `warm` level may repeat an earlier one to show the effect of
  process / OS / database caches (the API has no candidate cache in front of retrieval);
- after the ask levels, `--tasks` Skill tasks are created through the API, the API is stopped, and one worker
  processes them (one Metal device per host, record 54 §3.0); the Skill latency is the attempt's execution time
  from `task_attempts` (queue wait is reported separately because it depends on the worker count, not the Skill);
- a request counts as a failure when the HTTP status is not 200 or the outcome is an escalation whose reason codes
  contain `system_failure` (dependency timeout / unavailable); refusals and evidence-based escalations are normal
  outcomes and count towards the latency population, not the failure rate.

Percentiles are nearest-rank (the P95 of n values is the ceil(0.95 n)-th smallest). Secrets (DSNs, tokens, keys)
stay in the process environment; the report holds environment facts, counts, latencies and trace ids only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import math
import os
import pathlib
import platform
import re
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import jwt
import psycopg

# ------------------------------------------------------------------------------------------ OTLP receiver


class SpanSink:
    """Collects OTLP/HTTP protobuf spans as plain dicts (name, ids, times, attributes)."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []  # one entry per export request (size, span count or error)
        self.lock = threading.Lock()
        self.last_at = 0.0

    def ingest(self, body: bytes) -> None:
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

        req = ExportTraceServiceRequest()
        req.ParseFromString(body)
        out: list[dict[str, Any]] = []
        for rs in req.resource_spans:
            for ss in rs.scope_spans:
                for s in ss.spans:
                    attrs: dict[str, Any] = {}
                    for kv in s.attributes:
                        v = kv.value
                        which = v.WhichOneof("value")
                        attrs[kv.key] = getattr(v, which) if which else None
                    out.append(
                        {
                            "name": s.name,
                            "otel_trace": s.trace_id.hex(),
                            "span": s.span_id.hex(),
                            "parent": s.parent_span_id.hex(),
                            "start_ns": s.start_time_unix_nano,
                            "end_ns": s.end_time_unix_nano,
                            "ms": (s.end_time_unix_nano - s.start_time_unix_nano) / 1e6,
                            "attrs": attrs,
                        }
                    )
        with self.lock:
            self.spans.extend(out)
            self.events.append(
                {"at": time.time(), "bytes": len(body), "spans": len(out), "names": sorted({o["name"] for o in out})}
            )
            self.last_at = time.monotonic()

    def settle(self, quiet_s: float = 6.0, max_s: float = 40.0) -> int:
        """Wait until no export has arrived for `quiet_s` (the BatchSpanProcessor flushes every 5 s)."""
        deadline = time.monotonic() + max_s
        while time.monotonic() < deadline:
            with self.lock:
                idle = time.monotonic() - self.last_at if self.last_at else quiet_s
                n = len(self.spans)
            if idle >= quiet_s and n:
                return n
            time.sleep(0.5)
        with self.lock:
            return len(self.spans)

    def by_trace(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        with self.lock:
            for s in self.spans:
                tid = s["attrs"].get("medops.trace_id")
                if tid:
                    out.setdefault(tid, []).append(s)
        return out


def start_receiver(sink: SpanSink, port: int) -> ThreadingHTTPServer:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n)
            status = 200
            try:
                if self.path.endswith("/v1/traces"):
                    sink.ingest(body)
                else:
                    status = 404
            except Exception as exc:  # noqa: BLE001 - a bad export must not stop the run
                status = 400
                with sink.lock:
                    sink.events.append({"at": time.time(), "bytes": len(body), "error": repr(exc)[:300]})
            payload = ExportTraceServiceResponse().SerializeToString()
            self.send_response(status)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_: Any) -> None:  # silent
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, name="otlp-receiver", daemon=True).start()
    return server


# ------------------------------------------------------------------------------------------ helpers


def pctl(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    return xs[max(0, math.ceil(p * len(xs)) - 1)]


def summary(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50": pctl(values, 0.5),
        "p90": pctl(values, 0.9),
        "p95": pctl(values, 0.95),
        "p99": pctl(values, 0.99),
        "max": max(values) if values else None,
        "mean": round(statistics.fmean(values), 3) if values else None,
    }


def token(pem: bytes, *, kid: str, issuer: str, audience: str, sub: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "iss": issuer, "aud": audience, "iat": now, "exp": now + 3600},
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def wait_ready(base: str, timeout_s: float = 300.0) -> bool:
    """Poll /readyz on the loopback API. `trust_env=False`: a proxy configured in the shell (HTTP(S)_PROXY) must never
    carry loopback traffic — on 2026-09-30 the API was up but every probe went through the proxy and timed out. The
    last failure is printed when the deadline passes so the cause is visible."""
    deadline = time.monotonic() + timeout_s
    last = "no attempt"
    while time.monotonic() < deadline:
        try:
            status = httpx.get(base + "/readyz", timeout=2, trust_env=False).status_code
            if status == 200:
                return True
            last = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 - not up yet
            last = f"{type(exc).__name__}: {str(exc)[:80]}"
        time.sleep(1.0)
    print(f"readiness probe last result: {last}", flush=True)
    return False


def sysctl(name: str) -> str | None:
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001 - not macOS
        return None


def environment(admin_dsn: str | None, device_hint: str) -> dict[str, Any]:
    env: dict[str, Any] = {
        "platform": platform.platform(),
        "chip": sysctl("machdep.cpu.brand_string") or platform.processor(),
        "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30, 1) or None,
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "device": device_hint,
        "packages": {},
    }
    for pkg in ("torch", "sentence-transformers", "uvicorn", "fastapi", "psycopg", "openai", "httpx"):
        try:
            env["packages"][pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            env["packages"][pkg] = None
    try:
        from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL
        from medops.retrieval.production import RERANK_OUTPUT, production_hybrid_config
        from medops.verification.verifier import VERIFIER_VERSION

        cfg = production_hybrid_config()
        env["models"] = {
            "answer": PRODUCTION_ANSWER_MODEL,
            "judge": PRODUCTION_JUDGE_MODEL,
            "verifier": VERIFIER_VERSION,
        }
        env["retrieval"] = {
            "k_lexical": cfg.k_lexical,
            "k_vector": cfg.k_vector,
            "rrf_k": cfg.rrf_k,
            "fused_limit": cfg.limit,
            "rerank_output": RERANK_OUTPUT,
        }
    except Exception as exc:  # noqa: BLE001 - environment facts are best effort
        env["models_error"] = type(exc).__name__
    if admin_dsn:
        try:
            with psycopg.connect(admin_dsn) as conn:
                env["postgres"] = {
                    "server_version": conn.execute("show server_version").fetchone()[0],
                    "shared_buffers": conn.execute("show shared_buffers").fetchone()[0],
                    "max_connections": conn.execute("show max_connections").fetchone()[0],
                    "documents": dict(conn.execute("select status, count(*) from documents group by 1").fetchall()),
                    "chunks": conn.execute("select count(*) from chunks").fetchone()[0],
                    "database": conn.info.dbname,
                }
        except Exception as exc:  # noqa: BLE001
            env["postgres_error"] = type(exc).__name__
    return env


def node_breakdown(spans: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, float] = {}
    llm: list[dict[str, Any]] = []
    sub: dict[str, float] = {}
    http_ms = None
    for s in spans:
        if s["name"] == "harness.node":
            key = str(s["attrs"].get("node"))
            nodes[key] = round(nodes.get(key, 0.0) + s["ms"], 1)
        elif s["name"] == "llm.call":
            llm.append({"purpose": s["attrs"].get("purpose"), "ms": round(s["ms"], 1)})
        elif s["name"].startswith("retrieval."):
            sub[s["name"]] = round(sub.get(s["name"], 0.0) + s["ms"], 1)
        elif s["name"] == "http.request":
            http_ms = round(s["ms"], 1)
    return {
        "http_ms": http_ms,
        "nodes": nodes,
        "retrieval": sub,
        "llm": llm,
        "llm_ms": round(sum(c["ms"] for c in llm), 1),
    }


# ------------------------------------------------------------------------------------------ ask levels


def run_level(
    client: httpx.Client, level: dict[str, Any], headers: dict[str, str], out_rows: list[dict[str, Any]]
) -> None:
    conc = int(level["concurrency"])
    queries = level["queries"]
    level_started = time.perf_counter()
    level_wall = time.time()

    def one(item: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter()
        w0 = time.time()
        started_at = dt.datetime.now(dt.UTC).isoformat()
        status, body, error = None, {}, None
        try:
            r = client.post("/v1/ask", json={"query": item["query"]}, headers=headers)
            status = r.status_code
            try:
                body = r.json()
            except ValueError:
                body = {}
        except Exception as exc:  # noqa: BLE001 - recorded as a failed request
            error = type(exc).__name__
        latency = time.perf_counter() - t0
        wall = time.time() - w0
        outcome = body.get("outcome")
        codes = list(((body.get("escalation") or body.get("refusal") or {}).get("reason_codes")) or [])
        failed = status != 200 or (outcome == "escalated" and "system_failure" in codes)
        return {
            "level": level["name"],
            "concurrency": conc,
            "id": item.get("id"),
            "expect": item.get("expect"),
            "started_at": started_at,
            "latency_s": round(latency, 3),
            "wall_s": round(wall, 3),
            # macOS perf_counter does not advance while the machine sleeps; a gap between the two clocks means the
            # request straddled a system sleep and its numbers are not a service measurement
            "suspended_s": round(wall - latency, 1) if wall - latency > 5 else 0,
            "status": status,
            "outcome": outcome,
            "reason_codes": codes,
            "claims": len(((body.get("answer") or {}).get("claims")) or []),
            "trace_id": body.get("trace_id"),
            "error": error,
            "failed": failed,
        }

    with ThreadPoolExecutor(max_workers=conc) as pool:
        rows = list(pool.map(one, queries))
    elapsed = time.perf_counter() - level_started
    for i, row in enumerate(rows):
        row["order"] = i
        out_rows.append(row)
    level["_elapsed_s"] = round(elapsed, 2)
    level["_wall_s"] = round(time.time() - level_wall, 2)
    level["_started_at"] = dt.datetime.fromtimestamp(level_wall, dt.UTC).isoformat()
    print(
        f"level {level['name']} c={conc}: n={len(rows)} p95={pctl([r['latency_s'] for r in rows], 0.95)}s "
        f"failed={sum(r['failed'] for r in rows)} elapsed={elapsed:.1f}s",
        flush=True,
    )


def level_summary(level: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    mine = [r for r in rows if r["level"] == level["name"]]
    lat_all = [r["latency_s"] for r in mine]
    lat_ok = [r["latency_s"] for r in mine if not r["failed"]]
    by_outcome = {}
    for o in sorted({str(r["outcome"]) for r in mine}):
        by_outcome[o] = summary([r["latency_s"] for r in mine if str(r["outcome"]) == o])
    node_tot: dict[str, list[float]] = {}
    for r in mine:
        for k, v in (r.get("server") or {}).get("nodes", {}).items():
            node_tot.setdefault(k, []).append(v)
    return {
        "name": level["name"],
        "concurrency": level["concurrency"],
        "requests": len(mine),
        "failed": sum(r["failed"] for r in mine),
        "failure_rate": round(sum(r["failed"] for r in mine) / len(mine), 4) if mine else None,
        "elapsed_s": level.get("_elapsed_s"),
        "wall_s": level.get("_wall_s"),
        "started_at": level.get("_started_at"),
        "suspended_requests": sum(1 for r in mine if r.get("suspended_s")),
        "throughput_rps": round(len(mine) / level["_elapsed_s"], 3) if level.get("_elapsed_s") else None,
        "latency_all": summary(lat_all),
        "latency_ok": summary(lat_ok),
        "by_outcome": by_outcome,
        "node_p95_ms": {k: pctl(v, 0.95) for k, v in sorted(node_tot.items())},
        "node_p50_ms": {k: pctl(v, 0.5) for k, v in sorted(node_tot.items())},
        "gate_p95_le_8s": (pctl(lat_all, 0.95) or 0) <= 8.0 if lat_all else None,
    }


# ------------------------------------------------------------------------------------------ tasks


def create_tasks(client: httpx.Client, headers: dict[str, str], tasks: list[dict[str, Any]], run_tag: str) -> list[str]:
    ids: list[str] = []
    for i, t in enumerate(tasks):
        r = client.post(
            "/v1/tasks",
            json={"skill_name": t["skill_name"], "skill_version": t["skill_version"], "input": t["input"]},
            headers={**headers, "Idempotency-Key": f"perf-{run_tag}-{i}"},
        )
        r.raise_for_status()
        ids.append(r.json()["task_id"])
    return ids


def wait_tasks(admin_dsn: str, ids: list[str], timeout_s: float) -> list[tuple[Any, ...]]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with psycopg.connect(admin_dsn) as conn:
            rows = conn.execute(
                "select task_id::text, status from tasks where task_id = any(%s::uuid[])", (ids,)
            ).fetchall()
        if rows and all(st in ("completed", "failed", "dead") for _, st in rows) and len(rows) == len(ids):
            break
        time.sleep(2.0)
    with psycopg.connect(admin_dsn) as conn:
        return conn.execute(
            """
            select t.task_id::text, t.status, t.created_at, a.attempt, a.started_at, a.finished_at, a.outcome,
                   a.error_code, a.trace_id
              from tasks t left join task_attempts a on a.task_id = t.task_id
             where t.task_id = any(%s::uuid[]) order by t.created_at, a.attempt
            """,
            (ids,),
        ).fetchall()


# ------------------------------------------------------------------------------------------ main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--queries", required=True, help="JSON: {levels: [{name, concurrency, queries: [...]}], tasks: [...]}"
    )
    ap.add_argument("--api-cmd", required=True)
    ap.add_argument("--worker-cmd", default=None)
    ap.add_argument("--base-url", default="http://127.0.0.1:8010")
    ap.add_argument("--otlp-port", type=int, default=4319)
    ap.add_argument("--issuer-pem", required=True)
    ap.add_argument("--kid", required=True)
    ap.add_argument("--issuer", required=True)
    ap.add_argument("--audience", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--tasks", type=int, default=0, help="how many tasks from the queries file to run (0 = none)")
    ap.add_argument("--task-timeout", type=float, default=900.0)
    ap.add_argument("--admin-dsn-env", default="DATABASE_ADMIN_URL")
    ap.add_argument("--device", default="mps", help="recorded in the environment block only")
    ap.add_argument("--label", default="")
    ap.add_argument("--drain-s", type=float, default=6.0)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(pathlib.Path(args.queries).read_text(encoding="utf-8"))
    admin_dsn = os.environ.get(args.admin_dsn_env)
    pem = pathlib.Path(args.issuer_pem).read_bytes()
    headers = {
        "Authorization": "Bearer " + token(pem, kid=args.kid, issuer=args.issuer, audience=args.audience, sub=args.sub)
    }
    run_tag = uuid.uuid4().hex[:8]
    started = dt.datetime.now(dt.UTC)

    sink = SpanSink()
    receiver = start_receiver(sink, args.otlp_port)
    child_env = {**os.environ, "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{args.otlp_port}"}
    for k in ("DEBUG", "PYTHONPATH"):
        child_env.pop(k, None)

    api_log = open(out / "api.log", "w", encoding="utf-8")  # noqa: SIM115 - closed below
    api = subprocess.Popen(shlex.split(args.api_cmd), env=child_env, stdout=api_log, stderr=subprocess.STDOUT)
    t_ready0 = time.perf_counter()
    ready = wait_ready(args.base_url)
    ready_s = round(time.perf_counter() - t_ready0, 1)
    print(f"api ready={ready} after {ready_s}s", flush=True)
    if not ready:
        api.kill()
        receiver.shutdown()
        return 1

    rows: list[dict[str, Any]] = []
    client = httpx.Client(base_url=args.base_url, timeout=300, trust_env=False)  # loopback: never via a shell proxy
    task_ids: list[str] = []
    try:
        for level in spec["levels"]:
            run_level(client, level, headers, rows)
        if args.tasks and spec.get("tasks"):
            task_ids = create_tasks(client, headers, spec["tasks"][: args.tasks], run_tag)
            print(f"created {len(task_ids)} tasks", flush=True)
    finally:
        client.close()
        time.sleep(args.drain_s)  # let the batch exporter tick once more before the stop
        api.send_signal(signal.SIGTERM)
        try:
            api.wait(timeout=90)
        except subprocess.TimeoutExpired:
            api.kill()
        api_log.close()
    print("api stopped", flush=True)

    task_rows: list[tuple[Any, ...]] = []
    worker_rc = None
    if task_ids and args.worker_cmd and admin_dsn:
        worker_log = open(out / "worker.log", "w", encoding="utf-8")  # noqa: SIM115
        worker = subprocess.Popen(
            shlex.split(args.worker_cmd), env=child_env, stdout=worker_log, stderr=subprocess.STDOUT
        )
        try:
            task_rows = wait_tasks(admin_dsn, task_ids, args.task_timeout)
        finally:
            worker.send_signal(signal.SIGTERM)
            try:
                worker_rc = worker.wait(timeout=120)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker_rc = -9
            worker_log.close()
        print(f"worker stopped rc={worker_rc}", flush=True)

    n_spans = sink.settle()
    receiver.shutdown()
    by_trace = sink.by_trace()
    with (out / "spans.jsonl").open("w", encoding="utf-8") as fh:  # raw spans for attribution audits
        for s in sink.spans:
            fh.write(json.dumps(s, ensure_ascii=False, default=str) + "\n")
    (out / "receiver.log").write_text(
        "\n".join(json.dumps(e, default=str) for e in sink.events) + "\n", encoding="utf-8"
    )
    for r in rows:
        if r.get("trace_id") and r["trace_id"] in by_trace:
            r["server"] = node_breakdown(by_trace[r["trace_id"]])

    # server-side ledger facts per trace (duration as the service measured it, model calls, cost)
    cost_total = 0.0
    if admin_dsn:
        ids = [r["trace_id"] for r in rows if r.get("trace_id")]
        with psycopg.connect(admin_dsn) as conn:
            ledger = {
                tid: (dur, calls, tokens, float(cost or 0))
                for tid, dur, calls, tokens, cost in conn.execute(
                    "select trace_id, duration_ms, model_calls, tokens, cost_usd from traces where trace_id = any(%s)",
                    (ids,),
                ).fetchall()
            }
            task_trace_ids = [str(t[8]) for t in task_rows if t[8]]
            task_cost = conn.execute(
                "select coalesce(sum(cost_usd), 0) from traces where trace_id = any(%s)", (task_trace_ids,)
            ).fetchone()[0]
        for r in rows:
            fact = ledger.get(r.get("trace_id") or "")
            if fact:
                r["trace_duration_ms"], r["model_calls"], r["tokens"], r["cost_usd"] = fact
                cost_total += fact[3]
        cost_total += float(task_cost or 0)

    levels = [level_summary(level, rows) for level in spec["levels"]]

    # tasks: execution latency per attempt and end-to-end (queue wait included)
    exec_s: list[float] = []
    e2e_s: list[float] = []
    task_out: list[dict[str, Any]] = []
    for task_id, status, created_at, attempt, started_at, finished_at, outcome, error_code, trace_id in task_rows:
        ex = (finished_at - started_at).total_seconds() if started_at and finished_at else None
        ee = (finished_at - created_at).total_seconds() if finished_at else None
        if ex is not None and outcome == "completed":
            exec_s.append(ex)
        if ee is not None:
            e2e_s.append(ee)
        server = node_breakdown(by_trace.get(str(trace_id), [])) if trace_id else None
        task_out.append(
            {
                "task_id": task_id,
                "status": status,
                "attempt": attempt,
                "outcome": outcome,
                "error_code": error_code,
                "exec_s": round(ex, 3) if ex is not None else None,
                "end_to_end_s": round(ee, 3) if ee is not None else None,
                "trace_id": str(trace_id) if trace_id else None,
                "server": server,
            }
        )
    tasks_summary = {
        "requested": len(task_ids),
        "completed": sum(1 for t in task_out if t["outcome"] == "completed"),
        "failed": sum(1 for t in task_out if t["outcome"] not in (None, "completed")),
        "exec": summary(exec_s),
        "end_to_end": summary(e2e_s),
        "worker_rc": worker_rc,
        "gate_p95_le_15s": (pctl(exec_s, 0.95) or 0) <= 15.0 if exec_s else None,
    }

    results = {
        "label": args.label,
        "started_at": started.isoformat(),
        "finished_at": dt.datetime.now(dt.UTC).isoformat(),
        "api_ready_s": ready_s,
        "spans_received": n_spans,
        "environment": environment(admin_dsn, args.device),
        "levels": levels,
        "tasks": tasks_summary,
        "cost_usd": round(cost_total, 4),
        "gate": {
            "ask_p95_le_8s_all_levels": all(lv["gate_p95_le_8s"] for lv in levels if lv["gate_p95_le_8s"] is not None),
            "skill_p95_le_15s": tasks_summary["gate_p95_le_15s"],
        },
    }
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with (out / "rows.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        for t in task_out:
            fh.write(json.dumps({"level": "tasks", **t}, ensure_ascii=False, default=str) + "\n")
    (out / "report.md").write_text(render(results), encoding="utf-8")
    print(json.dumps(results["gate"]), f"cost={results['cost_usd']}", flush=True)
    return 0


def _f(x: Any) -> str:
    return "—" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def render(res: dict[str, Any]) -> str:
    env = res["environment"]
    pg = env.get("postgres", {})
    lines = [
        f"# Performance gate run {res['label']} ({res['started_at'][:10]})",
        "",
        "## Environment",
        "",
        f"- Host: {env.get('chip')} / {env.get('memory_gb')} GB / {env.get('cpu_count')} CPUs / {env.get('platform')}",
        f"- Python {env.get('python')}; " + ", ".join(f"{k} {v}" for k, v in env.get("packages", {}).items()),
        f"- Device for embedding + reranker: {env.get('device')} (one pinned model thread per process)",
        f"- Models: {json.dumps(env.get('models'), ensure_ascii=False)}; retrieval {json.dumps(env.get('retrieval'))}",
        f"- PostgreSQL {pg.get('server_version')} (shared_buffers {pg.get('shared_buffers')}, max_connections {pg.get('max_connections')}); "
        f"database {pg.get('database')}: documents {json.dumps(pg.get('documents'))}, chunks {pg.get('chunks')}",
        f"- API: one uvicorn process (`{res.get('label')}`), ready after {res['api_ready_s']} s (model load); spans received {res['spans_received']}",
        f"- Cost of this run: {res['cost_usd']} USD",
        "",
        "## Ask levels (client wall time, seconds; nearest-rank percentiles)",
        "",
        "| level | c | n | failed | p50 | p90 | p95 | p99 | max | rps | P95 ≤ 8 s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for lv in res["levels"]:
        la = lv["latency_all"]
        flag = (
            f" (⚠ {lv['suspended_requests']} requests straddled a system sleep)" if lv.get("suspended_requests") else ""
        )
        lines.append(
            f"| {lv['name']}{flag} | {lv['concurrency']} | {lv['requests']} | {lv['failed']} | {_f(la['p50'])} | {_f(la['p90'])} | "
            f"{_f(la['p95'])} | {_f(la['p99'])} | {_f(la['max'])} | {_f(lv['throughput_rps'])} | {'✓' if lv['gate_p95_le_8s'] else '✗'} |"
        )
    lines += [
        "",
        "### By outcome (p50 / p95 / n)",
        "",
        "| level | " + " | ".join(sorted({o for lv in res["levels"] for o in lv["by_outcome"]})) + " |",
    ]
    outs = sorted({o for lv in res["levels"] for o in lv["by_outcome"]})
    lines.append("| --- | " + " | ".join("---" for _ in outs) + " |")
    for lv in res["levels"]:
        cells = []
        for o in outs:
            s = lv["by_outcome"].get(o)
            cells.append(f"{_f(s['p50'])} / {_f(s['p95'])} / {s['n']}" if s else "—")
        lines.append(f"| {lv['name']} | " + " | ".join(cells) + " |")
    lines += ["", "### Server-side node time (ms, p50 / p95 across the level's requests; from OpenTelemetry spans)", ""]
    nodes = sorted({k for lv in res["levels"] for k in lv["node_p95_ms"]})
    lines.append("| level | " + " | ".join(nodes) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in nodes) + " |")
    for lv in res["levels"]:
        lines.append(
            f"| {lv['name']} | "
            + " | ".join(f"{_f(lv['node_p50_ms'].get(n))} / {_f(lv['node_p95_ms'].get(n))}" for n in nodes)
            + " |"
        )
    t = res["tasks"]
    lines += [
        "",
        "## Skill tasks (worker, one process)",
        "",
        f"- requested {t['requested']}, completed {t['completed']}, failed {t['failed']}, worker exit {t['worker_rc']}",
        f"- execution time per attempt: p50 {_f(t['exec']['p50'])} s, p95 {_f(t['exec']['p95'])} s, max {_f(t['exec']['max'])} s (n={t['exec']['n']}); P95 ≤ 15 s: {'✓' if t['gate_p95_le_15s'] else '✗' if t['gate_p95_le_15s'] is not None else '—'}",
        f"- end to end incl. queue wait behind one worker: p50 {_f(t['end_to_end']['p50'])} s, p95 {_f(t['end_to_end']['p95'])} s, max {_f(t['end_to_end']['max'])} s",
        "",
        "## Gate",
        "",
        f"- 普通问答 P95 ≤ 8 s at every level: {'✓' if res['gate']['ask_p95_le_8s_all_levels'] else '✗'}",
        f"- 复杂 Skill P95 ≤ 15 s: {'✓' if res['gate']['skill_p95_le_15s'] else '✗' if res['gate']['skill_p95_le_15s'] is not None else '— (not run)'}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if not re.match(r"^3\.1[1-9]", platform.python_version()):
        print("python 3.11+ required", file=sys.stderr)
    sys.exit(main())
