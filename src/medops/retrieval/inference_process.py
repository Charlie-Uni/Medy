"""One bounded, terminable local inference lane for API/worker/MCP.

Only local model configuration and plain text cross this private spawn pipe. Database connections,
gateways, ledgers and trace writers remain in the parent. Loading and inference use the child's main
thread, preserving the Metal constraint. A timeout/crash poisons the lane and reaps its child before
returning; readiness then requires a process restart. No automatic model retry is performed here.
"""

from __future__ import annotations

import atexit
import multiprocessing as mp
import threading
from collections.abc import Callable, Sequence
from typing import Any

from medops.core.deadline import check_deadline, remaining_timeout
from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.pinned import PINNED_CAPACITY, PINNED_QUEUE_WAIT_S
from medops.retrieval.rerank import RerankerSpec
from medops.retrieval.vector.embedding import EmbeddingSpec

STOP_GRACE_S = 0.25  # terminate, then kill; separate bounded cleanup allowance


def _providers(device: str, output: int) -> tuple[Any, Any]:
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

    return BgeM3EmbeddingProvider(device=device), BgeRerankerV2M3(device=device, output=output)


def _serve(conn: Any, device: str, output: int, factory: Callable[..., tuple[Any, Any]]) -> None:
    try:
        embedding, reranker = factory(device, output)
        conn.send(
            {
                "status": "ready",
                "embedding": embedding.spec.model_dump(),
                "reranker": reranker.spec.model_dump(),
                "framework": getattr(reranker, "framework", ""),
            }
        )
        while True:
            message = conn.recv()
            if message["op"] == "close":
                break
            try:
                if message["op"] == "embed_query":
                    value = embedding.embed_query(message["text"])
                elif message["op"] == "embed_documents":
                    value = embedding.embed_documents(message["texts"])
                elif message["op"] == "score":
                    # Output truncation belongs to the parent's immutable view, never to model loading.
                    value = reranker.score(message["query"], message["texts"])
                else:
                    raise ValueError("unsupported inference operation")
                conn.send({"status": "ok", "value": value})
            except Exception as exc:  # noqa: BLE001 - no text, credentials, or exception message leaves the child
                conn.send({"status": "error", "error_type": type(exc).__name__})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:  # noqa: BLE001 - startup failure also contains type only
        try:
            conn.send({"status": "error", "error_type": type(exc).__name__})
        except (BrokenPipeError, OSError):
            pass
    finally:
        conn.close()


class InferenceProcess:
    def __init__(
        self,
        *,
        device: str = "cpu",
        output: int = 8,
        timeout_s: float = 120.0,
        capacity: int = PINNED_CAPACITY,
        queue_wait_s: float = PINNED_QUEUE_WAIT_S,
        factory: Callable[..., tuple[Any, Any]] = _providers,
    ) -> None:
        if timeout_s <= 0 or capacity < 1 or queue_wait_s <= 0 or not 1 <= output <= 20:
            raise ValueError("invalid inference lane configuration")
        self._timeout, self._queue_wait = timeout_s, queue_wait_s
        self._slots = threading.BoundedSemaphore(capacity)
        self._call_lock, self._close_lock = threading.Lock(), threading.Lock()
        self.stalled = False
        self._ready = False
        ctx = mp.get_context("spawn")  # never fork a live PG connection, HTTP client, or initialized torch runtime
        self._conn, child = ctx.Pipe()
        self.process = ctx.Process(target=_serve, args=(child, device, output, factory), daemon=True)
        try:
            self.process.start()
            child.close()
            ready = self._receive(timeout_s)
            if ready["status"] != "ready":
                raise self._error("local model startup failed")
            self.embedding_spec = EmbeddingSpec.model_validate(ready["embedding"])
            self.reranker_spec = RerankerSpec.model_validate(ready["reranker"])
            self.framework = ready["framework"]
            self._ready = True
            atexit.register(self.close)
        except BaseException:
            child.close()
            self.close()
            raise

    @staticmethod
    def _error(detail: str, *, timeout: bool = False) -> InfrastructureError:
        return InfrastructureError(
            ErrorCode.dependency_timeout if timeout else ErrorCode.dependency_unavailable,
            detail=detail,
            retryable=False,
        )

    def _receive(self, timeout_s: float) -> dict[str, Any]:
        try:
            if not self._conn.poll(timeout_s):
                self.close(graceful=False)
                raise self._error("local inference deadline exceeded; child stopped", timeout=True)
            return self._conn.recv()
        except (EOFError, OSError):
            self.close(graceful=False)
            raise self._error("local inference child exited") from None

    def call(self, message: dict[str, Any]) -> Any:
        check_deadline()
        if self.stalled:
            raise self._error("local inference lane stopped; supervisor restart required")
        if not self._slots.acquire(timeout=remaining_timeout(self._queue_wait)):
            raise self._error("local inference queue saturated", timeout=True)
        acquired = False
        sent, received = False, False
        try:
            # Both queueing and inference use one call limit and the enclosing execution deadline.
            from medops.core.deadline import deadline_scope

            with deadline_scope(remaining_timeout(self._timeout)):
                acquired = self._call_lock.acquire(timeout=remaining_timeout(self._timeout))
                if not acquired:
                    raise self._error("local inference queue deadline exceeded", timeout=True)
                check_deadline()
                if self.stalled or not self.process.is_alive():
                    self.close()
                    raise self._error("local inference lane unavailable")
                try:
                    sent = True
                    self._conn.send(message)
                except (OSError, EOFError):
                    self.close()
                    raise self._error("local inference pipe unavailable") from None
                response = self._receive(remaining_timeout(self._timeout))
                received = True
                check_deadline()
                if response["status"] != "ok":
                    raise self._error(f"local inference error: {response.get('error_type', 'invalid_reply')}")
                return response["value"]
        except BaseException:
            if sent and not received:
                self.close(graceful=False)  # expiry/cancellation after dispatch must reap the active inference
            raise
        finally:
            if acquired:
                self._call_lock.release()
            self._slots.release()

    @property
    def available(self) -> bool:
        return not self.stalled and self.process.is_alive()

    def close(self, *, graceful: bool = True) -> None:
        atexit.unregister(self.close)
        with self._close_lock:
            self.stalled = True
            if self.process.pid is not None:
                # An idle healthy child can exit normally and unlink torch's named semaphores.
                idle = graceful and self._ready and self._call_lock.acquire(blocking=False)
                if idle:
                    try:
                        if self.process.is_alive():
                            try:
                                self._conn.send({"op": "close"})
                            except (OSError, EOFError):
                                pass
                            self.process.join(2.0)
                    finally:
                        self._call_lock.release()
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(STOP_GRACE_S)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(STOP_GRACE_S)
                if self.process.is_alive():
                    raise self._error("local inference child could not be reaped")
                self.process.join(0)
            self._conn.close()


class ProcessEmbedding:
    def __init__(self, lane: InferenceProcess) -> None:
        self._lane = lane
        self.spec = lane.embedding_spec

    def embed_query(self, text: str) -> list[float]:
        return self._lane.call({"op": "embed_query", "text": text})

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._lane.call({"op": "embed_documents", "texts": list(texts)})


class ProcessReranker:
    def __init__(self, lane: InferenceProcess, *, output: int) -> None:
        if type(output) is not int or not 1 <= output <= lane.reranker_spec.max_input:
            raise ValueError("invalid reranker output")
        self._lane = lane
        self._spec = lane.reranker_spec.model_copy(update={"output": output})
        self.framework = lane.framework

    @property
    def spec(self) -> RerankerSpec:
        return self._spec

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        return self._lane.call({"op": "score", "query": query, "texts": list(texts)})
