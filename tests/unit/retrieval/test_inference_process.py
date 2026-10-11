"""Real spawn boundaries: normal forwarding, crash/hang cleanup, overload and shutdown."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from medops.core.deadline import deadline_scope
from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.inference_process import InferenceProcess, ProcessEmbedding, ProcessReranker
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


def test_process_preserves_embedding_and_reranking_results_and_close_is_idempotent():
    lane = InferenceProcess(factory=_factory, timeout_s=5)
    try:
        embedding, reranker = ProcessEmbedding(lane), ProcessReranker(lane, output=8)
        direct = _FaultEmbedding(dimension=8)
        assert embedding.spec == direct.spec
        assert embedding.embed_query("audit critical") == direct.embed_query("audit critical")
        assert embedding.embed_documents(["major", "minor"]) == direct.embed_documents(["major", "minor"])
        assert reranker.score("critical audit", ["critical", "minor"]) == [0.5, 0]
    finally:
        lane.close()
        lane.close()
    assert not lane.process.is_alive() and not lane.available


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
