"""Pin every model call of a process to one long-lived thread (record 54 §3.0).

Driving the Metal/MPS backend from short-lived worker threads (one per node attempt) wedged the GPU driver
once and no node timeout could unblock the process. `PinnedThread` runs callables on a single daemon thread
with a wait timeout: a wedged call becomes a `dependency_timeout` and the process can be restarted by its
supervisor instead of hanging. `pin_embedding` / `pin_reranker` wrap the production providers."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from medops.core.errors import ErrorCode, InfrastructureError

T = TypeVar("T")


class PinnedThread:
    def __init__(self, timeout_s: float = 120.0, name: str = "model-pinned") -> None:
        self._q: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any], list[Any], threading.Event]] = (
            queue.Queue()
        )
        self._timeout = timeout_s
        self.stalled = False
        threading.Thread(target=self._loop, name=name, daemon=True).start()

    def _loop(self) -> None:
        while True:
            fn, args, kwargs, box, done = self._q.get()
            try:
                box.append(("ok", fn(*args, **kwargs)))
            except BaseException as exc:  # noqa: BLE001 - re-raised in the calling thread
                box.append(("err", exc))
            done.set()

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        box: list[Any] = []
        done = threading.Event()
        self._q.put((fn, args, kwargs, box, done))
        if not done.wait(self._timeout):
            self.stalled = True
            raise InfrastructureError(
                ErrorCode.dependency_timeout,
                detail=f"pinned model call {getattr(fn, '__name__', fn)} exceeded {self._timeout}s",
                retryable=False,
            )
        kind, value = box[0]
        if kind == "err":
            raise value
        return value


class PinnedEmbedding:
    def __init__(self, inner: Any, pinned: PinnedThread) -> None:
        self._inner, self._pinned = inner, pinned
        self.spec = inner.spec

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._pinned.call(self._inner.embed_documents, texts)

    def embed_query(self, text: str) -> list[float]:
        return self._pinned.call(self._inner.embed_query, text)


class PinnedReranker:
    def __init__(self, inner: Any, pinned: PinnedThread) -> None:
        self._inner, self._pinned = inner, pinned
        self.spec = inner.spec
        self.framework = getattr(inner, "framework", "")

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        return self._pinned.call(self._inner.score, query, texts)
