"""Real spawn boundaries: normal forwarding, crash/hang cleanup, overload and shutdown."""

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from medops.core.deadline import deadline_scope
from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.inference_process import InferenceProcess, ProcessEmbedding, ProcessReranker, _serve
from medops.retrieval.rerank import OverlapReranker
from medops.retrieval.vector.embedding import HashingEmbeddingProvider


class _FaultEmbedding(HashingEmbeddingProvider):
    def embed_query(self, text):
        if text == "hang":
            time.sleep(60)
        if text == "crash":
            os._exit(86)
        if text == "slow":
            time.sleep(0.15)
        return super().embed_query(text)


def _factory(device, output):
    return _FaultEmbedding(dimension=8), OverlapReranker(output=output)


def _hung_startup(device, output):
    time.sleep(60)
    return _factory(device, output)


class _FaultReranker(OverlapReranker):
    def score(self, query, texts):
        if query == "hang":
            time.sleep(60)
        return super().score(query, texts)


def _shared_factory(device, output):
    from medops.retrieval import rerank

    def reject_reload(**kwargs):
        raise AssertionError("output policy attempted another model load")

    # The pre-ARCH-10 child tries this constructor on the first changed output.
    rerank.BgeRerankerV2M3 = reject_reload
    return _FaultEmbedding(dimension=8), _FaultReranker(output=output)


def test_concurrent_outputs_use_one_child_scorer_without_reloading_or_mutating_specs():
    lane = InferenceProcess(factory=_shared_factory, timeout_s=5)
    outputs = (4, 5, 8, 12, 20, 4, 8, 5)
    barrier = threading.Barrier(len(outputs))

    def score(output):
        view = ProcessReranker(lane, output=output)
        barrier.wait(timeout=2)
        return view.spec.output, view.score("critical audit", ["critical", "minor", "audit"])

    try:
        with ThreadPoolExecutor(max_workers=len(outputs)) as pool:
            assert list(pool.map(score, outputs)) == [(o, [0.5, 0, 0.5]) for o in outputs]
        assert lane.reranker_spec.output == 8 and lane.available
        view = ProcessReranker(lane, output=4)
        with pytest.raises(AttributeError):
            view.spec = lane.reranker_spec
    finally:
        lane.close()
    assert not lane.process.is_alive()


def test_timed_out_shared_scorer_stops_all_views_without_reload():
    lane = InferenceProcess(factory=_shared_factory, timeout_s=5)
    try:
        small, normal = ProcessReranker(lane, output=4), ProcessReranker(lane, output=8)
        with deadline_scope(0.05), pytest.raises(InfrastructureError):
            small.score("hang", ["audit"])
        assert lane.stalled and not lane.process.is_alive()
        with pytest.raises(InfrastructureError) as exc:
            normal.score("audit", ["audit"])
        assert not exc.value.retryable
    finally:
        lane.close()


def test_process_preserves_embedding_and_reranking_results_and_close_is_idempotent():
    lane = InferenceProcess(factory=_factory, timeout_s=5)
    try:
        embedding, reranker = ProcessEmbedding(lane), ProcessReranker(lane, output=8)
        direct = _FaultEmbedding(dimension=8)
        assert embedding.spec == direct.spec
        assert embedding.embed_query("audit critical") == direct.embed_query("audit critical")
        assert embedding.embed_documents(["major", "minor"]) == direct.embed_documents(["major", "minor"])
        lane.empty_cache()  # typed child protocol; CPU is a no-op and remains usable afterwards
        assert reranker.score("critical audit", ["critical", "minor"]) == [0.5, 0]
    finally:
        lane.close()
        lane.close()
    assert not lane.process.is_alive() and not lane.available


def test_mps_cache_control_runs_in_the_child_loop_and_keeps_the_protocol_usable(monkeypatch):
    cleared = []
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(mps=SimpleNamespace(empty_cache=lambda: cleared.append(True)))
    )

    class Pipe:
        def __init__(self):
            self.messages = iter(
                [{"op": "empty_cache"}, {"op": "score", "query": "audit", "texts": ["audit"]}, {"op": "close"}]
            )
            self.replies = []
            self.closed = False

        def recv(self):
            return next(self.messages)

        def send(self, reply):
            self.replies.append(reply)

        def close(self):
            self.closed = True

    pipe = Pipe()
    _serve(pipe, "mps", 8, _factory)
    assert cleared == [True]
    assert pipe.replies[1:] == [{"status": "ok", "value": None}, {"status": "ok", "value": [1.0]}]
    assert pipe.closed


@pytest.mark.parametrize("text", ["hang", "crash"])
def test_active_inference_is_reaped_before_return_and_never_reused(text):
    lane = InferenceProcess(factory=_factory, timeout_s=5)
    started = time.monotonic()
    try:
        with deadline_scope(0.05), pytest.raises(InfrastructureError):
            ProcessEmbedding(lane).embed_query(text)
        assert time.monotonic() - started < 1
        assert lane.stalled and not lane.process.is_alive()
        with pytest.raises(InfrastructureError) as exc:
            ProcessEmbedding(lane).embed_query("normal")
        assert exc.value.retryable is False
    finally:
        lane.close()


def test_saturation_refuses_new_work_and_queued_expiry_does_not_poison_active_inference():
    lane = InferenceProcess(factory=_factory, timeout_s=5, capacity=2, queue_wait_s=0.01)
    entered = threading.Event()

    def first():
        entered.set()
        return ProcessEmbedding(lane).embed_query("slow")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first)
        try:
            assert entered.wait(1)
            time.sleep(0.02)
            with deadline_scope(0.02), pytest.raises(InfrastructureError) as exc:
                ProcessEmbedding(lane).embed_query("not dispatched")
            assert exc.value.code is ErrorCode.dependency_timeout
            assert future.result(timeout=1)
            assert lane.available
            assert ProcessEmbedding(lane).embed_query("normal")
        finally:
            lane.close()


def test_startup_timeout_reaps_child_and_reports_infrastructure_error():
    started = time.monotonic()
    with pytest.raises(InfrastructureError):
        InferenceProcess(factory=_hung_startup, timeout_s=0.05)
    assert time.monotonic() - started < 1
