"""Per-request metering of gateway calls (INV-OBS-01: calls, tokens and cost per trace)."""

from __future__ import annotations

from medops.core.telemetry import annotate, span
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
        # the `gen_ai.*` names are the OpenTelemetry GenAI conventions, which trace viewers for model calls read
        # (model, token counts); still structure only — never the prompt or the reply (INV-OBS-03)
        with span(
            "llm.call",
            purpose=request.purpose,
            model_id=request.model_id,
            **{"gen_ai.operation.name": "chat", "gen_ai.request.model": request.model_id},
        ) as current:
            before_accounted = getattr(self._inner, "run_accounted_cost_usd", None)
            try:
                response = self._inner.complete(request)
            except Exception:
                after_accounted = getattr(self._inner, "run_accounted_cost_usd", None)
                if isinstance(before_accounted, (int, float)) and isinstance(after_accounted, (int, float)):
                    charged = max(0.0, float(after_accounted) - float(before_accounted))
                    if charged:
                        self.calls += 1
                        self.cost_usd += charged
                raise
            annotate(
                current,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=response.cost_usd,
                truncated=response.truncated,
                **{
                    "gen_ai.response.model": response.model_id,
                    "gen_ai.usage.input_tokens": response.usage.input_tokens,
                    "gen_ai.usage.output_tokens": response.usage.output_tokens,
                    "gen_ai.usage.cost": response.cost_usd,
                },
            )
        self.calls += 1
        self.tokens += response.usage.total_tokens
        self.cost_usd += response.cost_usd
        return response
