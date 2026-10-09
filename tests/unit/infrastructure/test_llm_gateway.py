"""Model Gateway contract: prices, budgets, the fake, and the OpenAI adapter against a stub client."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import openai
import pytest

from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import (
    OPENAI_PRICES,
    BudgetExceeded,
    Message,
    ModelOutputInvalid,
    ModelRequest,
    ModelResponse,
    ModelTimeout,
    ModelUnavailable,
    ModelUsage,
    PriceTable,
    estimate_tokens,
)
from medops.infrastructure.llm.meter import MeteredGateway
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway

PRICES = PriceTable(OPENAI_PRICES)


def req(model="gpt-6-luna", purpose="answer", schema=None, text="hello"):
    return ModelRequest(
        purpose=purpose,
        model_id=model,
        messages=(Message(role="system", content="sys"), Message(role="user", content=text)),
        max_output_tokens=100,
        json_schema=schema,
    )


def test_token_estimate_counts_cjk_per_character_and_latin_per_four_chars():
    assert estimate_tokens("藥品說明書") == 5
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens("藥品 abcd") == 2 + 2  # 2 CJK + ceil(5/4)


def test_price_table_costs_and_refuses_unpriced_models():
    usage = ModelUsage(input_tokens=1_000_000, output_tokens=100_000, cached_input_tokens=500_000)
    # gpt-6-luna: 0.5M uncached * 0.10 + 0.5M cached * 0.01 + 0.1M * 0.50 = 0.05 + 0.005 + 0.05
    assert PRICES.cost_usd("gpt-6-luna", usage) == pytest.approx(0.105)
    assert PRICES.worst_case_usd(req()) > 0
    with pytest.raises(ModelUnavailable) as exc:
        PRICES.require("gpt-99-unknown")
    assert exc.value.retryable is False


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


def test_budgeted_gateway_stops_at_the_monthly_cap_and_never_downgrades():
    request = req()
    cost = PRICES.worst_case_usd(request)
    inner = _FixedCost(cost)
    ledger = InMemorySpendLedger()
    clock = lambda: datetime(2026, 9, 23, tzinfo=UTC)  # noqa: E731
    gw = BudgetedGateway(inner, prices=PRICES, ledger=ledger, monthly_cap_usd=cost * 3, clock=clock)
    gw.complete(request)
    gw.complete(request)
    gw.complete(request)
    assert ledger.month_total("2026-09") == pytest.approx(cost * 3)
    with pytest.raises(BudgetExceeded):
        gw.complete(request)
    assert inner.calls == 3
    # a new month starts from zero
    gw2 = BudgetedGateway(
        inner,
        prices=PRICES,
        ledger=ledger,
        monthly_cap_usd=cost * 3,
        clock=lambda: datetime(2026, 10, 1, tzinfo=UTC),
    )
    gw2.complete(req())
    assert inner.calls == 4


def test_gateway_assembly_keeps_budget_across_request_meters(monkeypatch):
    request = req()
    cost = PRICES.worst_case_usd(request)
    inner = _FixedCost(cost)
    settings = SimpleNamespace(llm_monthly_budget_usd=cost * 1.5)
    monkeypatch.setattr(OpenAIModelGateway, "from_settings", lambda settings: inner)
    gateway = build_budgeted_gateway(settings, ledger=InMemorySpendLedger())

    first_request = MeteredGateway(gateway)
    first_request.complete(request)
    assert (first_request.calls, first_request.tokens, first_request.cost_usd) == (1, 15, cost)

    # A new API request resets its meter, not the process's spend ledger.
    second_request = MeteredGateway(gateway)
    with pytest.raises(BudgetExceeded):
        second_request.complete(request)
    assert inner.calls == 1
    assert (second_request.calls, second_request.tokens, second_request.cost_usd) == (0, 0, 0.0)

    # The injectable in-memory ledger keeps unit tests isolated; production assembly uses PostgreSQL.
    separate_run = MeteredGateway(build_budgeted_gateway(settings, ledger=InMemorySpendLedger()))
    separate_run.complete(request)
    assert inner.calls == 2
    assert (separate_run.calls, separate_run.tokens, separate_run.cost_usd) == (1, 15, cost)


def test_provider_failure_consumes_the_reservation_fail_closed():
    request = req()
    cost = PRICES.worst_case_usd(request)
    ledger = InMemorySpendLedger()
    inner = FakeModelGateway({"answer": [ModelTimeout()]})
    clock = lambda: datetime(2026, 10, 8, tzinfo=UTC)  # noqa: E731
    gateway = BudgetedGateway(inner, prices=PRICES, ledger=ledger, monthly_cap_usd=cost, clock=clock)
    with pytest.raises(ModelTimeout):
        gateway.complete(request)
    assert ledger.month_total("2026-10") == pytest.approx(cost)
    with pytest.raises(BudgetExceeded):
        gateway.complete(request)


def test_run_cap_reserves_before_call_and_blocks_without_calling_provider():
    request = req()
    cost = PRICES.worst_case_usd(request)
    inner = _FixedCost(cost)
    gateway = BudgetedGateway(
        inner,
        prices=PRICES,
        ledger=InMemorySpendLedger(),
        monthly_cap_usd=10,
        run_cap_usd=cost * 2.5,
    )
    gateway.complete(request)
    gateway.complete(request)
    with pytest.raises(BudgetExceeded, match="run LLM cap"):
        gateway.complete(request)
    assert inner.calls == 2
    assert gateway.run_accounted_cost_usd == pytest.approx(cost * 2)
    assert gateway.run_cap_blocked


def test_failed_provider_call_is_visible_to_the_request_meter_and_run_cap():
    request = req()
    cost = PRICES.worst_case_usd(request)
    budgeted = BudgetedGateway(
        FakeModelGateway({"answer": [ModelTimeout()]}),
        prices=PRICES,
        ledger=InMemorySpendLedger(),
        monthly_cap_usd=10,
        run_cap_usd=cost,
    )
    meter = MeteredGateway(budgeted)
    with pytest.raises(ModelTimeout):
        meter.complete(request)
    assert (meter.calls, meter.tokens, meter.cost_usd) == (1, 0, pytest.approx(cost))
    with pytest.raises(BudgetExceeded, match="run LLM cap"):
        meter.complete(request)
    assert budgeted.run_cap_blocked


def test_fake_gateway_scripts_by_purpose_and_can_raise():
    fake = FakeModelGateway({"answer": [{"claims": []}, ModelTimeout()]}, default=["plain"])
    first = fake.complete(req(schema={"type": "object"}))
    assert first.parsed == {"claims": []} and first.cost_usd == 0.0
    with pytest.raises(ModelTimeout):
        fake.complete(req())
    assert fake.complete(req(purpose="verify")).text == "plain"
    with pytest.raises(AssertionError):
        fake.complete(req(purpose="verify"))
    assert [c.purpose for c in fake.calls] == ["answer", "answer", "verify", "verify"]


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


def test_openai_adapter_forwards_only_the_request_and_prices_the_usage():
    client = _StubClient(_completion(json.dumps({"verdict": "supported", "reason": "r"})))
    gw = OpenAIModelGateway(client)
    schema = {"type": "object", "properties": {"verdict": {"type": "string"}}, "required": ["verdict"]}
    resp = gw.complete(req(schema=schema, text="statement"))
    assert resp.parsed == {"verdict": "supported", "reason": "r"}
    assert resp.usage == ModelUsage(input_tokens=120, output_tokens=30, cached_input_tokens=0)
    assert resp.cost_usd == pytest.approx((120 * 0.10 + 30 * 0.50) / 1_000_000)
    assert (
        resp.response_id == "chatcmpl-1" and resp.system_fingerprint == "fp_1" and resp.model_id == "gpt-6-luna-2026-09"
    )
    sent = client.kwargs
    assert sent["model"] == "gpt-6-luna" and sent["timeout"] == 30.0 and sent["temperature"] == 0.0
    assert sent["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "statement"}]
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert set(sent) == {"model", "messages", "max_completion_tokens", "temperature", "timeout", "response_format"}


def test_openai_adapter_maps_provider_errors_and_rejects_bad_structured_output():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    with pytest.raises(ModelTimeout):
        OpenAIModelGateway(_StubClient(error=openai.APITimeoutError(request=request))).complete(req())
    rate = openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    with pytest.raises(ModelUnavailable) as exc:
        OpenAIModelGateway(_StubClient(error=rate)).complete(req())
    assert exc.value.retryable is True
    auth = openai.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
    with pytest.raises(ModelUnavailable) as exc2:
        OpenAIModelGateway(_StubClient(error=auth)).complete(req())
    assert exc2.value.retryable is False
    schema = {"type": "object"}
    with pytest.raises(ModelOutputInvalid):
        OpenAIModelGateway(_StubClient(_completion("not json"))).complete(req(schema=schema))
    with pytest.raises(ModelOutputInvalid):
        OpenAIModelGateway(_StubClient(_completion('{"a":', finish="length"))).complete(req(schema=schema))
    unpriced = _StubClient(_completion("x"))
    with pytest.raises(ModelUnavailable):
        OpenAIModelGateway(unpriced).complete(req(model="gpt-99"))
    assert unpriced.kwargs is None  # refused before any network call


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


def test_openai_adapter_resends_without_temperature_for_models_that_reject_it_and_remembers():
    client = _TemperatureRejectingClient()
    gw = OpenAIModelGateway(client)
    assert gw.complete(req()).text == "ok"
    assert [("temperature" in c) for c in client.calls] == [True, False]
    gw.complete(req())
    assert len(client.calls) == 3 and "temperature" not in client.calls[2]  # remembered for the model
