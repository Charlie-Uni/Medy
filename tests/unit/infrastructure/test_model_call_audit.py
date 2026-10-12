"""ARCH-07: actual adapter attempts, response receipts, failures and concurrent isolation."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from openai.types.chat import ChatCompletion

from medops.core.canonical import canonical_hash
from medops.core.errors import InfrastructureError
from medops.infrastructure.llm.call_audit import CallJournal
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelOutputInvalid, ModelTimeout
from medops.infrastructure.llm.meter import MeteredGateway
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway
from tests.support.model_gateway import _completion, _StubClient, _TemperatureRejectingClient, req


def test_call_record_contains_actual_sdk_arguments_response_and_receipt():
    client = _StubClient(_completion('{"ok":true}'))
    meter = MeteredGateway(OpenAIModelGateway(client))
    response = meter.complete(req(schema={"type": "object"}, text="private prompt"))
    (row,) = meter.call_journal.snapshot()
    assert row["request"]["messages"][1]["content"] == "private prompt"
    assert row["request_sha256"] == canonical_hash(row["request"])
    assert row["provider_attempts"][0]["arguments"] == client.kwargs
    assert row["provider_attempts"][0]["sha256"] == canonical_hash(client.kwargs)
    assert row["response"]["text"] == '{"ok":true}'
    assert row["provider_attempts"][0]["response"]["choices"][0]["message"]["content"] == '{"ok":true}'
    assert row["provider_attempts"][0]["response_scope"] == "offline_stub_selected_fields"
    assert row["response"]["system_fingerprint"] == response.system_fingerprint
    assert row["receipt"] == response.call_receipt.model_dump(mode="json")
    assert row["receipt"]["call"]["call_id"] == row["call_id"]
    row["request"]["messages"][1]["content"] = "mutated"
    assert meter.call_journal.snapshot()[0]["request"]["messages"][1]["content"] == "private prompt"


def test_real_sdk_completion_json_keeps_refusal_finish_reason_and_usage():
    completion = ChatCompletion.model_validate(
        {
            "id": "offline-completion",
            "created": 1,
            "object": "chat.completion",
            "model": "gpt-6-luna-test",
            "system_fingerprint": "offline-fp",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "", "refusal": "offline refusal"},
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }
    )
    meter = MeteredGateway(OpenAIModelGateway(_StubClient(completion)))
    meter.complete(req())
    (row,) = meter.call_journal.snapshot()
    (attempt,) = row["provider_attempts"]
    assert attempt["response_scope"] == "sdk_completion_json"
    assert attempt["response"] == completion.model_dump(mode="json")
    assert attempt["response"]["choices"][0]["message"]["refusal"] == "offline refusal"
    assert attempt["response"]["usage"]["total_tokens"] == 5


def test_compatibility_resend_is_two_provider_attempts_of_one_logical_call():
    meter = MeteredGateway(OpenAIModelGateway(_TemperatureRejectingClient()))
    meter.complete(req())
    (row,) = meter.call_journal.snapshot()
    first, second = row["provider_attempts"]
    assert "temperature" in first["arguments"] and "temperature" not in second["arguments"]
    assert first["error_type"] == "BadRequestError" and second["error_type"] is None
    assert meter.calls == 1 and len(meter.receipts) == 1


def test_invalid_json_keeps_raw_reply_and_usage_without_exception_message():
    meter = MeteredGateway(OpenAIModelGateway(_StubClient(_completion("private invalid body"))))
    with pytest.raises(ModelOutputInvalid):
        meter.complete(req(schema={"type": "object"}))
    (row,) = meter.call_journal.snapshot()
    assert row["response"]["text"] == "private invalid body"
    assert row["receipt"]["usage"]["input_tokens"] + row["receipt"]["usage"]["output_tokens"] > 0
    assert row["error_type"] == "ModelOutputInvalid"
    assert "error_message" not in row


def test_unknown_failure_keeps_request_and_receipt_but_does_not_invent_a_response():
    meter = MeteredGateway(FakeModelGateway({"answer": [ModelTimeout("private error detail")]}))
    with pytest.raises(ModelTimeout):
        meter.complete(req())
    (row,) = meter.call_journal.snapshot()
    assert row["response"] is None and row["receipt"]["provider_started"]
    assert row["error_type"] == "ModelTimeout" and "private error detail" not in str(row)


def test_parallel_calls_have_distinct_detached_records_and_capacity_refuses_before_provider():
    fake = FakeModelGateway({"answer": ["ok"] * 20})
    meter = MeteredGateway(fake)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n: meter.complete(req(text=f"input-{n}")), range(20)))
    rows = meter.call_journal.snapshot()
    assert len(rows) == len({r["call_id"] for r in rows}) == meter.calls == 20
    assert {r["request"]["messages"][1]["content"] for r in rows} == {f"input-{i}" for i in range(20)}
    meter.call_journal = CallJournal(max_calls=1)
    fake._script["answer"].extend(["ok", "never"])
    meter.complete(req())
    before = len(fake.calls)
    with pytest.raises(InfrastructureError, match="audit_unavailable"):
        meter.complete(req())
    assert len(fake.calls) == before and len(meter.call_journal.snapshot()) == 1


def test_byte_capacity_refuses_before_provider_and_retains_accounting_after_large_return():
    fake = FakeModelGateway({"answer": ["large reply" * 2000]})
    meter = MeteredGateway(fake)
    meter.call_journal = CallJournal(max_bytes=1)
    with pytest.raises(InfrastructureError):
        meter.complete(req())
    assert fake.calls == [] and meter.calls == 0
    meter.call_journal = CallJournal(max_bytes=1600)
    with pytest.raises(InfrastructureError):
        meter.complete(req())
    assert len(fake.calls) == meter.calls == 1
    assert not meter.call_journal.complete and len(meter.call_journal.snapshot()) == 1
    assert meter.receipts[0].response_id == "fake-1" and meter.receipts[0].usage.output_tokens > 0
