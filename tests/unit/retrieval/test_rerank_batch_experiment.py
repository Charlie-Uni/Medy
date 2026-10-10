"""PERF-01D: request partitioning, bad scores, and real spawned-worker failure/restart boundaries."""

import time

import pytest
from scripts.benchmark_rerank_batches import ChildWorker, ordered_ids, score_burst


def _case(name, dept="MA", count=2):
    return {
        "sample_id": name,
        "dept": dept,
        "query": name,
        "chunks": [{"chunk_id": f"{name}-{i}", "text": str(i)} for i in range(count)],
    }


def _fake_worker(conn, device):
    conn.send({"status": "ready"})
    while True:
        message = conn.recv()
        if message["op"] == "crash":
            conn.close()
            return
        if message["op"] == "hang":
            time.sleep(30)
        conn.send({"status": "ok", "value": device})


def test_merged_scores_return_to_the_correct_request_and_keep_its_own_ranking():
    cases = [_case("first", count=2), _case("second", count=3)]
    rows = score_burst(lambda pairs: [float(text) + (10 if q == "second" else 0) for q, text in pairs], cases, 2)
    assert rows[0]["scores"] == [0, 1]
    assert rows[1]["scores"] == [10, 11, 12]
    assert ordered_ids(cases[1], rows[1]["scores"]) == ["second-2", "second-1", "second-0"]
    assert rows[0]["completion_ms"] == rows[1]["completion_ms"]
    tied = _case("ties")
    tied["chunks"].reverse()
    assert ordered_ids(tied, [1, 1]) == ["ties-0", "ties-1"]


@pytest.mark.parametrize("scores", [[1], [1, float("nan")], [1, float("inf")]])
def test_bad_score_vectors_fail_closed(scores):
    with pytest.raises(ValueError, match="score vector"):
        score_burst(lambda pairs: scores, [_case("one")], 1)


@pytest.mark.parametrize(
    "cases",
    [
        [_case("a"), _case("b", "PV")],
        [_case("a"), _case("a")],
        [_case("a", count=21)],
    ],
)
def test_mixed_departments_duplicate_requests_and_unbounded_candidates_are_refused(cases):
    with pytest.raises(ValueError):
        score_burst(lambda pairs: [], cases, 2)


@pytest.mark.parametrize("op", ["crash", "hang"])
def test_child_failure_stops_the_worker_and_a_fresh_pipe_recovers(op):
    worker = ChildWorker("echo", target=_fake_worker, startup_s=5)
    try:
        with pytest.raises(RuntimeError, match="failed closed"):
            worker.call({"op": op}, timeout_s=0.02)
        assert not worker.process.is_alive()
        with pytest.raises(RuntimeError, match="failed closed"):
            worker.call({"op": "score"})
    finally:
        worker.close()
    recovered = ChildWorker("recovered", target=_fake_worker, startup_s=5)
    try:
        assert recovered.call({"op": "score"})["value"] == "recovered"
    finally:
        recovered.close()
