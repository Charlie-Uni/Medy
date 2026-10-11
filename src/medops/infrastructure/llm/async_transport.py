"""Synchronous gateway bridge to cancellable async SDK I/O, with a total call deadline.

One daemon event-loop thread per provider client, eight accepted calls, no unbounded submission
queue. Timeout cancels and awaits SDK cleanup before the caller receives its error. This concerns
local transport cancellation; a provider may still bill an already-submitted request.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from typing import Any

from medops.core.deadline import remaining_timeout
from medops.infrastructure.llm.gateway import ModelTimeout, ModelUnavailable


class AsyncChatTransport:
    def __init__(self, client: Any) -> None:
        self._client = client
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="model-http", daemon=True)
        self._slots = threading.BoundedSemaphore(8)
        self._lock = threading.Lock()
        self._closed = False
        self._tasks: set[asyncio.Task[Any]] = set()
        self._thread.start()
        atexit.register(self.close)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _create(self, kwargs: dict[str, Any], timeout_s: float) -> Any:
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            try:
                async with asyncio.timeout(remaining_timeout(timeout_s)):
                    return await self._client.chat.completions.create(**kwargs)
            except TimeoutError:
                raise ModelTimeout("provider transport total deadline exceeded") from None
        finally:
            self._tasks.discard(task)

    def create(self, kwargs: dict[str, Any]) -> Any:
        if not self._slots.acquire(timeout=remaining_timeout(0.25)):
            raise ModelUnavailable("provider transport capacity exhausted", retryable=False)
        try:
            timeout_s = remaining_timeout(float(kwargs["timeout"]))
            with self._lock:
                if self._closed:
                    raise ModelUnavailable("provider transport closed", retryable=False)
                future = asyncio.run_coroutine_threadsafe(self._create(kwargs, timeout_s), self._loop)
            # The coroutine's timeout owns cancellation. Never abandon a running SDK coroutine.
            return future.result()
        finally:
            self._slots.release()

    async def _close(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._client.close()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        atexit.unregister(self.close)
        try:
            asyncio.run_coroutine_threadsafe(self._close(), self._loop).result(timeout=2.0)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=1.0)
        if self._thread.is_alive():
            raise ModelUnavailable("provider transport shutdown did not settle", retryable=False)
