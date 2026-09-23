"""Scripted gateway for unit tests: deterministic, offline, zero cost, records every request."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any

from medops.infrastructure.llm.gateway import ModelRequest, ModelResponse, ModelUsage, estimate_tokens


class Truncated:
    """A scripted reply cut off by max_output_tokens (finish_reason=length): `parsed` is None, `truncated` is True."""

    def __init__(self, text: str) -> None:
        self.text = text


Scripted = str | Mapping[str, Any] | BaseException | Truncated


class FakeModelGateway:
    provider = "fake"

    def __init__(
        self, script: Mapping[str, Iterable[Scripted]] | None = None, default: Iterable[Scripted] = ()
    ) -> None:
        """`script` maps a request purpose to the replies (in order); `default` serves purposes not scripted.
        A `BaseException` entry is raised instead of returned, to simulate provider failures."""
        self._script = {k: deque(v) for k, v in (script or {}).items()}
        self._default = deque(default)
        self.calls: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        queue = self._script.get(request.purpose)
        if not queue:
            queue = self._default
        if not queue:
            raise AssertionError(f"FakeModelGateway has no scripted reply for purpose {request.purpose!r}")
        item = queue.popleft()
        if isinstance(item, BaseException):
            raise item
        truncated = isinstance(item, Truncated)
        payload: str | Mapping[str, Any] = item.text if isinstance(item, Truncated) else item
        if isinstance(payload, Mapping):
            text = json.dumps(dict(payload), ensure_ascii=False)
            parsed: dict[str, Any] | None = dict(payload)
        else:
            text = payload
            parsed = None
            if request.json_schema is not None and not truncated:
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError:
                    parsed = None
        usage = ModelUsage(
            input_tokens=estimate_tokens("".join(m.content for m in request.messages)),
            output_tokens=estimate_tokens(text),
        )
        return ModelResponse(
            text=text,
            parsed=parsed,
            usage=usage,
            cost_usd=0.0,
            provider=self.provider,
            model_id=request.model_id,
            response_id=f"fake-{len(self.calls)}",
            system_fingerprint="fake",
            latency_ms=1.0,
            truncated=truncated,
        )
