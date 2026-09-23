"""OpenAI adapter (ADR-0010). The SDK client is injected so unit tests use a stub; `from_settings` builds the
real client with retries disabled (the node policy owns retries) and the per-call timeout from the request.

Data boundary (ADR-0010 §3): the adapter forwards exactly the request messages; it adds no user identity, no
document beyond the evidence blocks the node built, and no metadata besides the model id and output schema.
"""

from __future__ import annotations

import json
import time
from typing import Any

import openai

from medops.core.config import Settings
from medops.infrastructure.llm.gateway import (
    OPENAI_PRICES,
    ModelOutputInvalid,
    ModelRequest,
    ModelResponse,
    ModelTimeout,
    ModelUnavailable,
    ModelUsage,
    PriceTable,
)

SCHEMA_NAME = "medops_output"


class OpenAIModelGateway:
    provider = "openai"

    def __init__(self, client: Any, *, prices: PriceTable | None = None) -> None:
        self._client = client
        self._prices = prices or PriceTable(OPENAI_PRICES)

    @classmethod
    def from_settings(cls, settings: Settings, *, prices: PriceTable | None = None) -> OpenAIModelGateway:
        if settings.openai_api_key is None:
            raise ModelUnavailable("OPENAI_API_KEY is not configured (ADR-0010)", retryable=False)
        client = openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0)
        return cls(client, prices=prices)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._prices.require(request.model_id)  # refuse unpriced models before spending anything
        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_completion_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "timeout": request.timeout_s,
        }
        if request.json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "schema": request.json_schema, "strict": True},
            }
        started = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except openai.APITimeoutError as exc:
            raise ModelTimeout(f"openai timeout after {request.timeout_s}s") from exc
        except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError) as exc:
            raise ModelUnavailable(f"openai transient failure: {type(exc).__name__}") from exc
        except openai.APIStatusError as exc:  # 4xx other than rate limit: configuration or request problem
            raise ModelUnavailable(f"openai rejected the call: {type(exc).__name__}", retryable=False) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        choice = completion.choices[0]
        text = choice.message.content or ""
        finish = getattr(choice, "finish_reason", None)
        usage_obj = completion.usage
        details = getattr(usage_obj, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
        usage = ModelUsage(
            input_tokens=int(usage_obj.prompt_tokens),
            output_tokens=int(usage_obj.completion_tokens),
            cached_input_tokens=cached,
        )
        parsed: dict[str, Any] | None = None
        if request.json_schema is not None:
            if finish == "length":
                raise ModelOutputInvalid("structured output truncated by max_output_tokens")
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ModelOutputInvalid("structured output is not valid JSON") from exc
            if not isinstance(loaded, dict):
                raise ModelOutputInvalid("structured output is not a JSON object")
            parsed = loaded
        return ModelResponse(
            text=text,
            parsed=parsed,
            usage=usage,
            cost_usd=self._prices.cost_usd(request.model_id, usage),
            provider=self.provider,
            model_id=str(getattr(completion, "model", request.model_id)),
            response_id=getattr(completion, "id", None),
            system_fingerprint=getattr(completion, "system_fingerprint", None),
            latency_ms=latency_ms,
            truncated=finish == "length",
        )
