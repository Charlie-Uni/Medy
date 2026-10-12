"""Process-level fault drill (M3-13 second slice; baseline 5.10 / 5.12, record 61 done the same cases with in-process
fakes). Real processes on a real database: the API and worker binaries, a local model-provider proxy that can be
switched between pass-through and three fault modes, a database trigger that breaks the audit store, a paused
database container, a SIGKILLed worker and two competing workers.

    python evals/harness/tools/chaos_run.py --out evals/harness/runs/<run> \
        --api-cmd "python -m medops.api.serve --port 8012 --device mps" \
        --worker-cmd "python -m medops.worker.serve --device mps --poll 0.5 --lease 15" \
        --issuer-pem <pem> --kid <kid> --issuer <iss> --audience <aud> --sub <subject> \
        [--pg-container medops-postgres] [--skip model_timeout,...]

Each scenario records three facts, the same three as record 61: locatable (which rows say what failed: trace spans
with error codes, task attempts, escalations), recoverable (the same request succeeds after the fault is lifted,
in the same processes) and safety chain intact (no claims in a failed response, refusals still happen before any
model call, no unaudited answer, a task executes once). The proxy forwards to the real provider in pass mode and
never logs headers or bodies; secrets stay in process environments. Cost: a handful of real answers (~0.1 USD).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shlex
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import psycopg

from medops.evals.api_client import issue_demo_token as token

UPSTREAM = "https://api.openai.com"
HIGH_RISK = "我最近血压 150/95，我应该每天吃多少 losartan？"
ANSWERABLE = "瑪爾胰(glimepiride)每日最高建議劑量是多少?"
TASK = {
    "skill_name": "label_query",
    "skill_version": "1.0.0",
    "input": {"product": "Losacar", "question": "治療高血壓的一般起始劑量及維持劑量是多少？"},
}


# ------------------------------------------------------------------------------------------ provider proxy


class ProviderProxy:
    """`mode` is one of pass | blackhole | http_503 | http_429. Pass mode forwards the request unchanged to the
    upstream (the SDK's Authorization header travels through this process's memory only)."""

    def __init__(self, port: int) -> None:
        self.mode = "pass"
        self.calls: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        proxy = self
        client = httpx.Client(base_url=UPSTREAM, timeout=120)

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n)
                mode = proxy.mode
                with proxy.lock:
                    proxy.calls.append({"at": time.time(), "mode": mode, "path": self.path})
                if mode == "blackhole":
                    time.sleep(150)  # longer than any node timeout; the client gives up first
                    return
                if mode in ("http_503", "http_429"):
                    status = 503 if mode == "http_503" else 429
                    payload = json.dumps(
                        {
                            "error": {
                                "message": "chaos drill: provider unavailable"
                                if status == 503
                                else "chaos drill: insufficient_quota",
                                "type": "server_error" if status == 503 else "insufficient_quota",
                                "code": None if status == 503 else "insufficient_quota",
                            }
                        }
                    ).encode()
                    self._reply(status, payload, {"Content-Type": "application/json"})
                    return
                headers = {
                    k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "connection")
                }
                try:
                    r = client.post(self.path, content=body, headers=headers)
                    passthrough = {k: v for k, v in r.headers.items() if k.lower() in ("content-type",)}
                    self._reply(r.status_code, r.content, passthrough)
                except Exception:  # noqa: BLE001 - upstream trouble surfaces to the SDK as a 502
                    self._reply(
                        502, b'{"error":{"message":"proxy upstream failure"}}', {"Content-Type": "application/json"}
                    )

            def _reply(self, status: int, payload: bytes, headers: dict[str, str]) -> None:
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_: Any) -> None:
                return

            def handle(
                self,
            ) -> None:  # a client that gives up (blackhole mode) resets the keep-alive socket: not an error
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, name="provider-proxy", daemon=True).start()

    def calls_since(self, t: float) -> int:
        with self.lock:
            return sum(1 for c in self.calls if c["at"] >= t)


# ------------------------------------------------------------------------------------------ helpers


def wait_ready(base: str, timeout_s: float = 300.0, want: int = 200) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/readyz", timeout=3).status_code == want:
                return True
        except Exception:  # noqa: BLE001
            if want != 200:
                return True
        time.sleep(1.0)
    return False


class Db:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def q(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        with psycopg.connect(self.dsn) as conn:
            return conn.execute(sql, params).fetchall()

    def x(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            conn.execute(sql, params)

    def spans(self, trace_id: str) -> list[dict[str, Any]]:
        return [
            {"node": n, "attempt": a, "outcome": o, "error_code": e, "ms": round(ms or 0)}
            for n, a, o, e, ms in self.q(
                "select node, attempt, outcome, error_code, duration_ms from trace_spans where trace_id = %s order by started_at",
                (trace_id,),
            )
        ]

    def trace(self, trace_id: str) -> dict[str, Any] | None:
        rows = self.q(
            "select outcome, reason_codes, model_calls, cost_usd from traces where trace_id = %s", (trace_id,)
        )
        if not rows:
            return None
        o, codes, calls, cost = rows[0]
        return {"outcome": o, "reason_codes": list(codes or []), "model_calls": calls, "cost_usd": float(cost or 0)}

    def escalation(self, trace_id: str) -> dict[str, Any] | None:
        rows = self.q("select status, reason_codes from escalations where trace_id = %s", (trace_id,))
        return {"status": rows[0][0], "reason_codes": list(rows[0][1] or [])} if rows else None


def ask(client: httpx.Client, headers: dict[str, str], query: str, timeout: float = 240.0) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        r = client.post("/v1/ask", json={"query": query}, headers=headers, timeout=timeout)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        status: int | None = r.status_code
        error = None
    except Exception as exc:  # noqa: BLE001
        status, body, error = None, {}, type(exc).__name__
    payload = body.get("escalation") or body.get("refusal") or {}
    return {
        "status": status,
        "error": error,
        "outcome": body.get("outcome"),
        "code": body.get("code"),
        "reason_codes": list(payload.get("reason_codes") or []),
        "claims": len(((body.get("answer") or {}).get("claims")) or []),
        "retryable": body.get("retryable"),
        "trace_id": body.get("trace_id"),
        "latency_s": round(time.perf_counter() - t0, 2),
    }


# ------------------------------------------------------------------------------------------ scenarios


class Drill:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.out = pathlib.Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.db = Db(os.environ[args.admin_dsn_env])
        self.proxy = ProviderProxy(args.proxy_port)
        pem = pathlib.Path(args.issuer_pem).read_bytes()
        self.headers = {
            "Authorization": "Bearer "
            + token(pem, kid=args.kid, issuer=args.issuer, audience=args.audience, sub=args.sub)
        }
        self.env = {**os.environ, "OPENAI_BASE_URL": f"http://127.0.0.1:{args.proxy_port}/v1"}
        for k in ("DEBUG", "PYTHONPATH", "OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.env.pop(k, None)
        self.client = httpx.Client(base_url=args.base_url, timeout=240)
        self.results: list[dict[str, Any]] = []
        self.api: subprocess.Popen[bytes] | None = None
        self.api_log: Any = None

    # -- processes
    def start_api(self) -> bool:
        self.api_log = open(self.out / "api.log", "a", encoding="utf-8")  # noqa: SIM115
        self.api = subprocess.Popen(
            shlex.split(self.args.api_cmd), env=self.env, stdout=self.api_log, stderr=subprocess.STDOUT
        )
        return wait_ready(self.args.base_url)

    def stop_api(self) -> None:
        if self.api is None:
            return
        self.api.send_signal(signal.SIGTERM)
        try:
            self.api.wait(timeout=90)
        except subprocess.TimeoutExpired:
            self.api.kill()
        self.api_log.close()
        self.api = None

    def start_worker(self, name: str, extra: list[str] | None = None) -> subprocess.Popen[bytes]:
        log = open(self.out / f"worker-{name}.log", "a", encoding="utf-8")  # noqa: SIM115
        return subprocess.Popen(
            shlex.split(self.args.worker_cmd) + (extra or []), env=self.env, stdout=log, stderr=subprocess.STDOUT
        )

    def record(self, name: str, **facts: Any) -> None:
        ok = bool(facts.pop("ok"))
        self.results.append({"scenario": name, "ok": ok, **facts})
        print(
            ("OK  " if ok else "FAIL"),
            name,
            json.dumps({k: (str(v)[:120]) for k, v in facts.items()}, ensure_ascii=False)[:600],
            flush=True,
        )

    def create_task(self, tag: str) -> str:
        r = self.client.post(
            "/v1/tasks", json=TASK, headers={**self.headers, "Idempotency-Key": f"chaos-{tag}-{uuid.uuid4().hex[:8]}"}
        )
        r.raise_for_status()
        return r.json()["task_id"]

    def task_state(self, task_id: str) -> tuple[Any, ...]:
        rows = self.db.q("select status, attempts, lease_owner from tasks where task_id = %s", (task_id,))
        return rows[0] if rows else (None, None, None)

    def attempts(self, task_id: str) -> list[dict[str, Any]]:
        return [
            {"attempt": a, "worker": w, "outcome": o, "error_code": e}
            for a, w, o, e in self.db.q(
                "select attempt, worker, outcome, error_code from task_attempts where task_id = %s order by attempt",
                (task_id,),
            )
        ]

    # -- S0 baseline through the proxy
    def s_baseline(self) -> None:
        t = time.time()
        a = ask(self.client, self.headers, ANSWERABLE)
        self.record(
            "baseline_pass_through",
            ok=a["status"] == 200 and a["outcome"] == "answered" and a["claims"] >= 1,
            ask=a,
            provider_calls=self.proxy.calls_since(t),
        )

    # -- S1 real model timeout (blackhole provider), refusal during the outage, recovery in the same process
    def s_model_timeout(self) -> None:
        self.proxy.mode = "blackhole"
        t = time.time()
        r = ask(self.client, self.headers, HIGH_RISK, timeout=60)
        refused_ok = r["status"] == 200 and r["outcome"] == "refused" and self.proxy.calls_since(t) == 0
        a = ask(self.client, self.headers, ANSWERABLE, timeout=400)
        spans = self.db.spans(a["trace_id"]) if a["trace_id"] else []
        codes = [s for s in spans if s["error_code"]]
        calls_during = self.proxy.calls_since(t)
        self.proxy.mode = "pass"
        rec = ask(self.client, self.headers, ANSWERABLE)
        self.record(
            "model_timeout_blackhole",
            ok=a["status"] == 200
            and a["outcome"] == "escalated"
            and "system_failure" in a["reason_codes"]
            and a["claims"] == 0
            and any(s["error_code"] == "dependency_timeout" for s in spans)
            and refused_ok
            and rec["outcome"] == "answered",
            during=a,
            refusal_during_outage=r,
            error_spans=codes,
            escalation=self.db.escalation(a["trace_id"]) if a["trace_id"] else None,
            provider_calls_during=calls_during,
            recovered=rec,
        )

    # -- S2/S3 provider 503 and 429 with real HTTP, recovery
    def s_provider_status(self, mode: str) -> None:
        self.proxy.mode = mode
        t = time.time()
        a = ask(self.client, self.headers, ANSWERABLE, timeout=120)
        spans = self.db.spans(a["trace_id"]) if a["trace_id"] else []
        calls_during = self.proxy.calls_since(t)
        self.proxy.mode = "pass"
        rec = ask(self.client, self.headers, ANSWERABLE)
        self.record(
            f"provider_{mode}",
            ok=a["status"] == 200
            and a["outcome"] == "escalated"
            and "system_failure" in a["reason_codes"]
            and a["claims"] == 0
            and any(s["error_code"] == "dependency_unavailable" for s in spans)
            and rec["outcome"] == "answered",
            during=a,
            error_spans=[s for s in spans if s["error_code"]],
            provider_calls_during=calls_during,
            recovered=rec,
        )

    # -- S4 audit store broken by a trigger: answer computed, nothing returned, nothing recorded; recovery
    def s_audit_trigger(self) -> None:
        self.db.x(
            "create or replace function chaos_fail_audit() returns trigger language plpgsql as $$ begin raise exception 'chaos drill: audit store down'; end $$"
        )
        self.db.x(
            "create trigger chaos_traces_down before insert on traces for each row execute function chaos_fail_audit()"
        )
        try:
            t = time.time()
            a = ask(self.client, self.headers, ANSWERABLE)
            calls = self.proxy.calls_since(t)
            recorded = self.db.trace(a["trace_id"]) if a["trace_id"] else None
        finally:
            self.db.x("drop trigger if exists chaos_traces_down on traces")
            self.db.x("drop function if exists chaos_fail_audit()")
        rec = ask(self.client, self.headers, ANSWERABLE)
        self.record(
            "audit_store_down",
            ok=a["status"] == 503
            and a["code"] == "audit_unavailable"
            and a["claims"] == 0
            and a["retryable"] is True
            and recorded is None
            and rec["outcome"] == "answered"
            and calls >= 1,
            during=a,
            provider_calls_during=calls,
            trace_row_written=recorded is not None,
            recovered=rec,
            trigger_left=bool(self.db.q("select 1 from pg_trigger where tgname = 'chaos_traces_down'")),
        )

    # -- S5 database paused (container), readiness and request behaviour, recovery
    def s_db_pause(self) -> None:
        if not self.args.pg_container:
            self.record("db_pause", ok=False, skipped="no --pg-container")
            return
        subprocess.run(["docker", "pause", self.args.pg_container], check=True, capture_output=True)
        try:
            not_ready = wait_ready(self.args.base_url, timeout_s=20, want=503)
            t = time.time()
            a = ask(self.client, self.headers, ANSWERABLE, timeout=self.args.db_pause_timeout)
            calls = self.proxy.calls_since(t)
        finally:
            subprocess.run(["docker", "unpause", self.args.pg_container], check=True, capture_output=True)
        ready_again = wait_ready(self.args.base_url, timeout_s=60)
        rec = ask(self.client, self.headers, ANSWERABLE)
        self.record(
            "db_pause",
            ok=not_ready
            and a["status"] == 503
            and a["code"] in ("dependency_unavailable", "audit_unavailable", "dependency_timeout")
            and a["retryable"] is True
            and a["claims"] == 0
            and calls == 0
            and ready_again
            and rec["outcome"] == "answered",
            readyz_503_while_paused=not_ready,
            during=a,
            provider_calls_during=calls,
            readyz_200_after=ready_again,
            recovered=rec,
        )

    # -- S6 worker SIGKILLed mid-task, another worker takes over after the lease
    def s_worker_kill(self) -> None:
        task_id = self.create_task("kill")
        w1 = self.start_worker("kill-1")
        deadline = time.monotonic() + 240
        owner = None
        while time.monotonic() < deadline:
            status, attempts, owner = self.task_state(task_id)
            if status == "running":
                break
            time.sleep(0.5)
        time.sleep(3.0)  # into the execution (retrieval / model call in flight)
        w1.kill()
        w1.wait(timeout=30)
        killed_at = time.time()
        w2 = self.start_worker("kill-2")
        final = None
        deadline = time.monotonic() + 400
        while time.monotonic() < deadline:
            status, attempts, _ = self.task_state(task_id)
            if status in ("completed", "failed", "dead"):
                final = status
                break
            time.sleep(1.0)
        w2.send_signal(signal.SIGTERM)
        w2.wait(timeout=60)
        att = self.attempts(task_id)
        traces = self.db.q("select count(*) from traces where task_id = %s", (task_id,))[0][0]
        self.record(
            "worker_sigkill_takeover",
            ok=final == "completed"
            and len(att) == 2
            and att[0]["outcome"] == "lost"
            and att[1]["outcome"] == "completed"
            and att[0]["worker"] != att[1]["worker"]
            and att[0]["worker"] == owner
            and traces == 1,
            first_owner=owner,
            attempts=att,
            final_status=final,
            task_traces=traces,
            takeover_after_s=round(time.time() - killed_at, 1),
        )

    # -- S7 two workers over one queue: every task runs exactly once
    def s_dup_consumers(self, n: int = 4) -> None:
        ids = [self.create_task(f"dup{i}") for i in range(n)]
        # two model processes on one Metal device at once is what record 54 §3.0 avoids: the pair runs on cpu
        # and the lease must exceed a CPU execution (~20 s): run 1 used 15 s and turned this into a lease-expiry drill
        extra = ["--device", "cpu", "--lease", "180"]
        w1, w2 = self.start_worker("dup-1", extra), self.start_worker("dup-2", extra)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            states = [self.task_state(i)[0] for i in ids]
            if all(s in ("completed", "failed", "dead") for s in states):
                break
            time.sleep(1.0)
        for w in (w1, w2):
            w.send_signal(signal.SIGTERM)
        for w in (w1, w2):
            w.wait(timeout=60)
        att = {i: self.attempts(i) for i in ids}
        workers = {a["worker"] for al in att.values() for a in al}
        self.record(
            "two_workers_exactly_once",
            ok=all(len(al) == 1 and al[0]["outcome"] == "completed" for al in att.values())
            and all(self.task_state(i)[0] == "completed" for i in ids),
            attempts_per_task=[len(al) for al in att.values()],
            workers_seen=len(workers),
            statuses=[self.task_state(i)[0] for i in ids],
        )

    # -- run
    def run(self) -> int:
        started = dt.datetime.now(dt.UTC)
        skip = set(filter(None, (self.args.skip or "").split(",")))
        if not self.start_api():
            print("api not ready", flush=True)
            return 1
        try:
            self.s_baseline()
            if "model_timeout" not in skip:
                self.s_model_timeout()
            if "provider_503" not in skip:
                self.s_provider_status("http_503")
            if "provider_429" not in skip:
                self.s_provider_status("http_429")
            if "audit" not in skip:
                self.s_audit_trigger()
            if "db_pause" not in skip:
                self.s_db_pause()
            if "worker_kill" not in skip:
                self.s_worker_kill()
            if "dup" not in skip:
                self.s_dup_consumers()
        finally:
            self.stop_api()
            self.proxy.server.shutdown()
        cost = 0.0
        ids = [
            r.get(k, {}).get("trace_id")
            for r in self.results
            for k in ("ask", "during", "recovered", "refusal_during_outage")
            if isinstance(r.get(k), dict)
        ]
        ids = [i for i in ids if i]
        if ids:
            cost += float(
                self.db.q("select coalesce(sum(cost_usd), 0) from traces where trace_id = any(%s)", (ids,))[0][0]
            )
        cost += float(
            self.db.q(
                "select coalesce(sum(t.cost_usd), 0) from traces t join tasks k on k.task_id = t.task_id where k.created_at >= %s",
                (started,),
            )[0][0]
            or 0
        )
        report = {
            "started_at": started.isoformat(),
            "finished_at": dt.datetime.now(dt.UTC).isoformat(),
            "ok": all(r["ok"] for r in self.results),
            "cost_usd": round(cost, 4),
            "results": self.results,
        }
        (self.out / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            f"# Process-level fault drill ({started.date()})",
            "",
            f"cost {report['cost_usd']} USD; all ok: {report['ok']}",
            "",
            "| scenario | ok | facts |",
            "| --- | --- | --- |",
        ]
        for r in self.results:
            facts = ", ".join(
                f"{k}={json.dumps(v, ensure_ascii=False, default=str)[:160]}"
                for k, v in r.items()
                if k not in ("scenario", "ok")
            )
            lines.append(f"| {r['scenario']} | {'✓' if r['ok'] else '✗'} | {facts} |")
        (self.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("ALL OK" if report["ok"] else "SOME SCENARIOS FAILED", f"cost={report['cost_usd']}", flush=True)
        return 0 if report["ok"] else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--api-cmd", required=True)
    ap.add_argument("--worker-cmd", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8012")
    ap.add_argument("--proxy-port", type=int, default=4400)
    ap.add_argument("--issuer-pem", required=True)
    ap.add_argument("--kid", required=True)
    ap.add_argument("--issuer", required=True)
    ap.add_argument("--audience", required=True)
    ap.add_argument("--sub", required=True)
    ap.add_argument("--admin-dsn-env", default="DATABASE_ADMIN_URL")
    ap.add_argument("--pg-container", default=None)
    ap.add_argument("--db-pause-timeout", type=float, default=45.0)
    ap.add_argument("--skip", default="")
    return Drill(ap.parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
