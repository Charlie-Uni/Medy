"""Actual locked AsyncOpenAI + mock HTTP transport, no hosted calls or credentials."""

import asyncio
import threading
from types import SimpleNamespace

import httpx
import openai
import pytest

from medops.harness.contracts import NodeFailure, NodeSpec, run_node
from medops.infrastructure.llm.async_transport import AsyncChatTransport
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.gateway import OPENAI_PRICES, Message, ModelRequest, PriceTable
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway


def test_total_timeout_cancels_http_and_settles_budget_before_node_failure():
    entered, settled = threading.Event(), threading.Event()

    async def handler(request):
        if b"warmup" in request.content:
            return httpx.Response(
                200,
                json={
                    "id": "warmup",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "gpt-6-luna",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )
        entered.set()
        try:
            await asyncio.sleep(60)
            raise AssertionError("cancelled HTTP continued")
        finally:
            settled.set()

    client = openai.AsyncOpenAI(
        api_key="offline-test-only",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    provider = OpenAIModelGateway(client, asynchronous=True)
    ledger = InMemorySpendLedger()
    gateway = BudgetedGateway(provider, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=1)
    request = ModelRequest(
        purpose="proof", model_id="gpt-6-luna", messages=(Message(role="user", content="q"),), max_output_tokens=10
    )
    try:
        # Separate SDK lazy initialization from the assertion about in-flight HTTP cancellation.
        provider.complete(request.model_copy(update={"messages": (Message(role="user", content="warmup"),)}))
        with pytest.raises(NodeFailure) as exc:
            run_node(NodeSpec(name="n", timeout_s=0.5), "k", lambda: gateway.complete(request))
        assert entered.is_set() and settled.is_set()
        assert len(exc.value.attempts) == 1
        assert len(ledger._reservations) == 1 and all(v[2] is not None for v in ledger._reservations.values())
        assert not provider._transport._tasks
    finally:
        gateway.close()
    assert not provider._transport._thread.is_alive()


def test_transport_shutdown_cancels_and_joins_an_accepted_request():
    entered, settled = threading.Event(), threading.Event()
    failures = []

    async def create(**kwargs):
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            settled.set()

    async def close():
        assert settled.is_set()

    transport = AsyncChatTransport(
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=close)
    )

    def caller():
        try:
            transport.create({"timeout": 10})
        except Exception as exc:  # noqa: BLE001 - the assertion concerns settlement, not cancellation's public mapping
            failures.append(type(exc).__name__)

    thread = threading.Thread(target=caller)
    thread.start()
    assert entered.wait(1)
    transport.close()
    thread.join(1)
    transport.close()
    assert settled.is_set() and not thread.is_alive() and not transport._thread.is_alive() and failures
