"""Shared model gateway test support; no collected test cases."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai

from medops.infrastructure.llm.gateway import (
    Message,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)


def req(model="gpt-6-luna", purpose="answer", schema=None, text="hello"):
    return ModelRequest(
        purpose=purpose,
        model_id=model,
        messages=(Message(role="system", content="sys"), Message(role="user", content=text)),
        max_output_tokens=100,
        json_schema=schema,
    )


class _FixedCost:
    provider = "stub"

    def __init__(self, cost):
        self.cost = cost
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        return ModelResponse(
            text="ok",
            usage=ModelUsage(input_tokens=10, output_tokens=5),
            cost_usd=self.cost,
            provider="stub",
            model_id=request.model_id,
            latency_ms=1,
        )


class _StubClient:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result, error, None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


def _completion(content, finish="stop", prompt=120, completion=30, cached=0):
    usage = SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=SimpleNamespace(cached_tokens=cached)
    )
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)
    return SimpleNamespace(
        choices=[choice], usage=usage, id="chatcmpl-1", model="gpt-6-luna-2026-09", system_fingerprint="fp_1"
    )


class _TemperatureRejectingClient:
    """First call with `temperature` fails like a reasoning-tier model; the resend without it succeeds."""

    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if "temperature" in kwargs:
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            body = {"error": {"param": "temperature", "code": "unsupported_value", "message": "unsupported"}}
            raise openai.BadRequestError("bad", response=httpx.Response(400, request=request), body=body)
        return _completion("ok")
