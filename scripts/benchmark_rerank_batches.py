"""Local PERF-01D burst experiment; never a production service or a hosted-model caller.

Capture rechecked candidates once, then measure identical pairs through one spawned, pinned model lane.
FIFO and merge-2/4 differ only in CrossEncoder.predict grouping (batch size remains 8). Completion times
model a ready backlog of four requests in one department, not an HTTP arrival process or a batch timer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import statistics
import time
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash

SAMPLES = (
    "pc-0001",
    "pc-0013",
    "pc-0020",
    "pc-0026",
    "pc-0031",
    "pc-0044",
    "pc-0076",
    "pc-0089",
    "pc-0060",
    "pc-0068",
    "pc-0093",
    "pc-0100",
)
ARMS = {"fifo": 1, "merge2": 2, "merge4": 4}
ROOT = Path(__file__).resolve().parents[1]


def _save(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def validate_cases(cases: Sequence[dict]) -> None:
    if not 1 <= len(cases) <= 4 or len({c["dept"] for c in cases}) != 1:
        raise ValueError("a burst needs 1..4 cases in the same department")
    if len({c["sample_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate request identifiers")
    for case in cases:
        chunks = case["chunks"]
        if not case["query"] or not 1 <= len(chunks) <= 20:
            raise ValueError("each request needs a query and 1..20 candidates")
        if len({c["chunk_id"] for c in chunks}) != len(chunks):
            raise ValueError("duplicate candidate identifiers")
        if any(not c["text"] for c in chunks):
            raise ValueError("empty candidate text")


def score_burst(predict: Callable, cases: Sequence[dict], group_size: int) -> list[dict]:
    """Partition flat model results back into their request; fail on malformed scores before returning."""
    from medops.retrieval.lexical.normalization import normalize_text

    validate_cases(cases)
    if group_size not in (1, 2, 4):
        raise ValueError("unsupported group size")
    rows = []
    started = time.perf_counter()
    for offset in range(0, len(cases), group_size):
        group = cases[offset : offset + group_size]
        pairs = [(normalize_text(c["query"]), normalize_text(t["text"])) for c in group for t in c["chunks"]]
        group_started = time.perf_counter()
        scores = [float(x) for x in predict(pairs)]
        if len(scores) != len(pairs) or any(not math.isfinite(x) for x in scores):
            raise ValueError("invalid score vector")
        completion_ms = (time.perf_counter() - started) * 1000
        execution_ms = (time.perf_counter() - group_started) * 1000
        cursor = 0
        for case in group:
            count = len(case["chunks"])
            rows.append(
                {
                    "sample_id": case["sample_id"],
                    "scores": scores[cursor : cursor + count],
                    "completion_ms": completion_ms,
                    "group_execution_ms": execution_ms,
                    "group_requests": len(group),
                }
            )
            cursor += count
    return rows


def ordered_ids(case: dict, scores: Sequence[float]) -> list[str]:
    if len(scores) != len(case["chunks"]) or any(not math.isfinite(s) for s in scores):
        raise ValueError("invalid score vector")
    return [
        c["chunk_id"]
        for c, _ in sorted(zip(case["chunks"], scores, strict=True), key=lambda x: (-x[1], x[0]["chunk_id"]))
    ]


def capture(output: Path, device: str, as_of: date) -> None:
    import psycopg

    from medops.core.config import Settings
    from medops.evals.run_conditions import environment_snapshot, fact_snapshot_from_dsn, source_snapshot
    from medops.retrieval.hybrid import retrieve_evidence
    from medops.retrieval.integrity import inspect_readiness
    from medops.retrieval.pinned import PinnedEmbedding, PinnedThread
    from medops.retrieval.production import (
        PRODUCTION_RETRIEVAL_VERSION,
        production_hybrid_config,
        production_lexical_retriever,
        production_lexical_versions,
        production_vector_retriever,
    )
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    settings = Settings()
    app_dsn = settings.database_url.get_secret_value()
    admin_dsn = (settings.database_admin_url or settings.database_url).get_secret_value()
    before = fact_snapshot_from_dsn(admin_dsn)
    lane = PinnedThread()
    provider = PinnedEmbedding(lane.call(lambda: BgeM3EmbeddingProvider(device=device)), lane)
    readiness = inspect_readiness(admin_dsn, embedding=provider.spec)
    if not readiness["ready"]:
        raise ValueError("retrieval not ready")
    dataset = ROOT / "evals/probe/precise_clause/v4"
    samples = {r["sample_id"]: r for r in map(json.loads, (dataset / "samples.jsonl").read_text().splitlines())}
    cases = []
    with psycopg.connect(app_dsn, connect_timeout=5) as conn:
        for sample_id in SAMPLES:
            sample = samples[sample_id]
            with conn.transaction():
                conn.execute("select set_config('medops.dept', %s, true)", (sample["dept"],))
                lexical = production_lexical_retriever(conn, as_of=as_of)
                vector = production_vector_retriever(conn, provider, as_of=as_of)
                hybrid, checked = retrieve_evidence(
                    conn,
                    lexical,
                    vector,
                    sample["query"],
                    config=production_hybrid_config(),
                    lexical_expected=production_lexical_versions(),
                    vector_expected=vector.versions,
                    as_of=as_of,
                )
                if checked.rejected or not checked.evidence:
                    raise ValueError(f"candidate recheck failed for {sample_id}")
                cases.append(
                    {
                        "sample_id": sample_id,
                        "dept": sample["dept"],
                        "language": sample["language"],
                        "query": sample["query"],
                        "lexical_ids": [c.chunk_id for c in hybrid.lexical.candidates],
                        "vector_ids": [c.chunk_id for c in hybrid.vector.candidates],
                        "chunks": [
                            {
                                "chunk_id": e.citation.chunk_id,
                                "doc_id": e.citation.doc_id,
                                "text_hash": e.chunk_content_hash,
                                "text": e.text,
                            }
                            for e in checked.evidence
                        ],
                    }
                )
    after = fact_snapshot_from_dsn(admin_dsn)
    if before != after:
        raise ValueError("fact snapshot changed during capture")
    for dept in ("MA", "PV", "CO"):
        validate_cases([c for c in cases if c["dept"] == dept])
    _save(
        output,
        {
            "format": "rerank-burst-workload-v1",
            "cases": cases,
            "facts": before,
            "readiness": readiness,
            "dataset_hash": json.loads((dataset / "manifest.json").read_text())["dataset_hash"],
            "as_of": str(as_of),
            "production_base_version": PRODUCTION_RETRIEVAL_VERSION,
            "capture_source": source_snapshot(ROOT, Path(__file__)),
            "environment": environment_snapshot(),
            "scope": "raw query BM25 + custom vector + RRF + ordinary-role recheck; no translation, focus or hosted LLM",
        },
    )


def _model_worker(conn: Any, device: str) -> None:
    # Do not fork a process that already initialized Metal; only this spawned child loads the reranker.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from medops.retrieval.pinned import PinnedThread
    from medops.retrieval.rerank import BgeRerankerV2M3

    lane = PinnedThread()
    model = lane.call(lambda: BgeRerankerV2M3(device=device, batch_size=8))
    conn.send(
        {
            "status": "ready",
            "spec": model.spec.model_dump(),
            "framework": model.framework,
            "dtype": str(next(model._model.parameters()).dtype),
        }
    )

    def predict(pairs):
        return lane.call(model._model.predict, pairs, batch_size=8, show_progress_bar=False)

    while True:
        message = conn.recv()
        if message["op"] == "close":
            break
        if message["op"] == "crash":
            os._exit(86)
        if message["op"] == "hang":
            time.sleep(600)  # injected blocked worker, not a claim to reproduce a Metal driver wedge
        started = time.perf_counter()
        try:
            rows = score_burst(predict, message["cases"], message["group_size"])
            conn.send({"status": "ok", "rows": rows, "worker_ms": (time.perf_counter() - started) * 1000})
        except Exception as exc:  # noqa: BLE001 - preserve type only; no document/query body in error frames
            conn.send({"status": "error", "error_type": type(exc).__name__})
    conn.close()


class ChildWorker:
    """One outstanding IPC call; terminate on EOF/timeout and discard its private pipe before restart."""

    def __init__(self, device: str, *, target: Callable = _model_worker, startup_s: float = 120):
        ctx = mp.get_context("spawn")
        self.conn, child_conn = ctx.Pipe()
        self.process = ctx.Process(target=target, args=(child_conn, device), daemon=True)
        started = time.perf_counter()
        self.process.start()
        child_conn.close()
        try:
            self.ready = self._receive(startup_s)
            if self.ready.get("status") != "ready":
                raise RuntimeError("worker startup failed")
        except Exception:
            self.close()
            raise
        self.startup_ms = (time.perf_counter() - started) * 1000

    def _receive(self, timeout_s: float) -> dict:
        try:
            if not self.conn.poll(timeout_s):
                raise TimeoutError("worker deadline exceeded")
            return self.conn.recv()
        except (TimeoutError, EOFError, OSError):
            self.close()
            raise RuntimeError("worker unavailable; request failed closed") from None

    def call(self, message: dict, *, timeout_s: float = 120) -> dict:
        started = time.perf_counter()
        if not self.process.is_alive():
            self.close()
            raise RuntimeError("worker unavailable; request failed closed")
        try:
            self.conn.send(message)
        except (BrokenPipeError, EOFError, OSError):
            self.close()
            raise RuntimeError("worker unavailable; request failed closed") from None
        result = self._receive(timeout_s)
        if result.get("status") != "ok":
            raise RuntimeError("worker inference failed")
        result["round_trip_ms"] = (time.perf_counter() - started) * 1000
        return result

    def close(self) -> None:
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
        self.process.join(timeout=5)
        self.conn.close()


def _fault(worker: ChildWorker, op: str) -> dict:
    started = time.perf_counter()
    try:
        worker.call({"op": op}, timeout_s=0.25)
    except RuntimeError:
        return {
            "op": op,
            "failed_closed": True,
            "worker_stopped": not worker.process.is_alive(),
            "parent_alive": True,
            "detection_and_cleanup_ms": (time.perf_counter() - started) * 1000,
        }
    raise RuntimeError("fault injection unexpectedly returned a result")


def _percentile(values: Sequence[float], percentile: int) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * percentile / 100) - 1)]


def run(workload_path: Path, output: Path, device: str, rounds: int) -> None:
    from medops.evals.run_conditions import environment_snapshot, source_snapshot

    if rounds < 1 or output.exists():
        raise ValueError("positive rounds and a new output directory required")
    workload = json.loads(workload_path.read_text())
    if workload.get("format") != "rerank-burst-workload-v1":
        raise ValueError("unsupported workload format")
    cases = workload["cases"]
    if len({c["sample_id"] for c in cases}) != len(cases) or {c["dept"] for c in cases} != {"MA", "PV", "CO"}:
        raise ValueError("unique requests in all three departments required")
    for case in cases:
        for chunk in case["chunks"]:
            if hashlib.sha256(chunk["text"].encode()).hexdigest() != chunk["text_hash"]:
                raise ValueError("workload text hash mismatch")
    bursts = [[c for c in cases if c["dept"] == d] for d in ("MA", "PV", "CO")]
    for burst in bursts:
        validate_cases(burst)
    metadata = {
        **workload,
        "cases": [{**c, "chunks": [{k: v for k, v in t.items() if k != "text"} for t in c["chunks"]]} for c in cases],
    }
    output.mkdir(parents=True)
    _save(output / "inputs.json", metadata)
    plan = {
        "format": "rerank-burst-run-v1",
        "inputs_hash": canonical_hash(metadata),
        "workload_hash_with_text": canonical_hash(workload),
        "source": source_snapshot(ROOT, Path(__file__)),
        "environment": environment_snapshot(),
        "device": device,
        "rounds": rounds,
        "batch_size": 8,
        "warmup": "one complete burst per department and arm; FIFO also supplies the reference",
        "arms": ARMS,
        "formal_gate": False,
        "hosted_model_calls": 0,
        "api_cost_usd": 0,
        "scope": "ready backlog burst; no timer/arrival simulation or HTTP service; cold start excluded from warm metrics",
        "adopt_if": "zero Top8 and full-ranking changes; >=20% throughput gain; no dept burst P95 regression; follow with larger quality audit",
    }
    _save(output / "plan.json", plan)
    rows, references, faults, starts = [], {}, [], []
    worker = ChildWorker(device)
    try:
        starts.append(worker.startup_ms)
        _save(output / "model.json", worker.ready)
        # Reference scores also warm every input before measured, interleaved arms.
        for burst in bursts:
            response = worker.call({"op": "score", "cases": burst, "group_size": 1})
            references.update({r["sample_id"]: r["scores"] for r in response["rows"]})
        _save(output / "reference_scores.json", references)
        for group_size in (2, 4):
            for burst in bursts:
                worker.call({"op": "score", "cases": burst, "group_size": group_size})
        with (output / "rows.jsonl").open("w", encoding="utf-8") as handle:
            for round_no in range(rounds):
                for burst_no, burst in enumerate(bursts):
                    names = list(ARMS)
                    shift = (round_no + burst_no) % len(names)
                    for arm in names[shift:] + names[:shift]:
                        response = worker.call({"op": "score", "cases": burst, "group_size": ARMS[arm]})
                        for r, case in zip(response["rows"], burst, strict=True):
                            reference = references[case["sample_id"]]
                            order = ordered_ids(case, r["scores"])
                            expected_order = ordered_ids(case, reference)
                            row = {
                                **r,
                                "arm": arm,
                                "round": round_no,
                                "dept": case["dept"],
                                "ranked_ids": order,
                                "full_order_same": order == expected_order,
                                "top8_order_same": order[:8] == expected_order[:8],
                                "max_score_delta": max(abs(a - b) for a, b in zip(r["scores"], reference, strict=True)),
                                "burst_worker_ms": response["worker_ms"],
                                "burst_round_trip_ms": response["round_trip_ms"],
                                "burst_requests": len(burst),
                            }
                            rows.append(row)
                            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        handle.flush()
                        print(
                            f"round={round_no + 1} dept={burst[0]['dept']} arm={arm} ms={response['worker_ms']:.1f}",
                            flush=True,
                        )
        faults.append(_fault(worker, "crash"))
        worker = ChildWorker(device)
        starts.append(worker.startup_ms)
        recovery = worker.call({"op": "score", "cases": bursts[0][:1], "group_size": 1})
        recovery_case = bursts[0][0]
        faults[-1]["recovered_order_same"] = ordered_ids(recovery_case, recovery["rows"][0]["scores"]) == ordered_ids(
            recovery_case, references[recovery_case["sample_id"]]
        )
        faults.append(_fault(worker, "hang"))
        worker = ChildWorker(device)
        starts.append(worker.startup_ms)
        recovery = worker.call({"op": "score", "cases": bursts[0][:1], "group_size": 1})
        faults[-1]["recovered_order_same"] = ordered_ids(recovery_case, recovery["rows"][0]["scores"]) == ordered_ids(
            recovery_case, references[recovery_case["sample_id"]]
        )
    finally:
        worker.close()
    summaries = {}
    for arm in ARMS:
        selected = [r for r in rows if r["arm"] == arm]
        # Account for each burst once, not once per returned request.
        total_ms = sum(r["burst_round_trip_ms"] / r["burst_requests"] for r in selected)
        summaries[arm] = {
            "requests": len(selected),
            "requests_per_second": len(selected) / (total_ms / 1000),
            "completion_p50_ms": statistics.median(r["completion_ms"] for r in selected),
            "completion_p95_ms": _percentile([r["completion_ms"] for r in selected], 95),
            "full_order_changes": sum(not r["full_order_same"] for r in selected),
            "top8_order_changes": sum(not r["top8_order_same"] for r in selected),
            "max_score_delta": max(r["max_score_delta"] for r in selected),
            "mean_burst_ipc_overhead_ms": statistics.mean(
                r["burst_round_trip_ms"] - r["burst_worker_ms"] for r in selected
            ),
            "department_completion_p95_ms": {
                d: _percentile([r["completion_ms"] for r in selected if r["dept"] == d], 95) for d in ("MA", "PV", "CO")
            },
        }
    _save(
        output / "results.json",
        {
            "arms": summaries,
            "faults": faults,
            "startup_ms": starts,
            "formal_gate": False,
            "hosted_model_calls": 0,
            "api_cost_usd": 0,
        },
    )
    print(json.dumps(summaries, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--out", type=Path, required=True)
    cap.add_argument("--as-of", type=date.fromisoformat, required=True)
    bench = sub.add_parser("run")
    bench.add_argument("--workload", type=Path, required=True)
    bench.add_argument("--out", type=Path, required=True)
    bench.add_argument("--rounds", type=int, default=3)
    for command in (cap, bench):
        command.add_argument("--device", choices=("cpu", "mps"), default="mps")
    args = parser.parse_args()
    if args.command == "capture":
        if args.out.exists():
            parser.error("capture output must be new")
        capture(args.out, args.device, args.as_of)
    else:
        run(args.workload, args.out, args.device, args.rounds)


if __name__ == "__main__":
    main()
