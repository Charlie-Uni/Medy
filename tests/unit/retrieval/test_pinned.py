"""PinnedThread: one bounded model lane, fail-fast overload, and terminal handling of a stalled call."""

from __future__ import annotations

import threading
import time

import pytest

from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.pinned import PinnedEmbedding, PinnedThread


def test_calls_share_one_thread_and_errors_propagate():
    pinned = PinnedThread(timeout_s=5)
    names = {pinned.call(lambda: threading.current_thread().name) for _ in range(3)}
    assert len(names) == 1 and names != {threading.current_thread().name}

    def boom():
        raise ValueError("inner")

    with pytest.raises(ValueError):
        pinned.call(boom)
    assert pinned.stalled is False


def test_stalled_call_is_a_dependency_timeout_and_marks_the_thread():
    pinned = PinnedThread(timeout_s=0.05)
    with pytest.raises(InfrastructureError) as exc:
        pinned.call(time.sleep, 0.5)
    assert exc.value.code is ErrorCode.dependency_timeout and exc.value.retryable is False and pinned.stalled
    with pytest.raises(InfrastructureError) as unavailable:
        pinned.call(lambda: None)
    assert unavailable.value.code is ErrorCode.dependency_unavailable and unavailable.value.retryable


def test_capacity_bounds_running_and_queued_calls():
    pinned = PinnedThread(timeout_s=2, capacity=1, queue_wait_s=0.01)
    started, release = threading.Event(), threading.Event()

    def occupy():
        pinned.call(lambda: started.set() or release.wait(1))

    caller = threading.Thread(target=occupy)
    caller.start()
    assert started.wait(1)
    with pytest.raises(InfrastructureError) as saturated:
        pinned.call(lambda: None)
    release.set()
    caller.join(1)
    assert saturated.value.code is ErrorCode.dependency_timeout and saturated.value.retryable
    assert not caller.is_alive()


def test_pinned_embedding_forwards_and_keeps_the_spec():
    class Inner:
        spec = "spec-1"

        def embed_query(self, text):
            return [len(text)]

        def embed_documents(self, texts):
            return [[len(t)] for t in texts]

    wrapped = PinnedEmbedding(Inner(), PinnedThread(timeout_s=2))
    assert (
        wrapped.spec == "spec-1"
        and wrapped.embed_query("abc") == [3]
        and wrapped.embed_documents(["a", "bb"]) == [[1], [2]]
    )
