"""Per-request metering of gateway calls (INV-OBS-01: calls, tokens and cost per trace)."""

from __future__ import annotations

from medops.infrastructure.llm.gateway import ModelGateway, ModelRequest, ModelResponse


class MeteredGateway:
    def __init__(self, inner: ModelGateway) -> None:
        self._inner = inner
        self.calls = 0
        self.tokens = 0
        self.cost_usd = 0.0

    @property
    def provider(self) -> str:
        return self._inner.provider

    def complete(self, request: ModelRequest) -> ModelResponse:
        response = self._inner.complete(request)
        self.calls += 1
        self.tokens += response.usage.total_tokens
        self.cost_usd += response.cost_usd
        return response
