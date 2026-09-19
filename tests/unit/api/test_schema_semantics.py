"""The exported JSON Schemas must reject the same structurally-expressible cases as the models
(Codex review of record 09, item 2). Rules that need server state are listed as schema-only-accepts."""

import hashlib
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

from medops.api.contracts import AskResponse, FeedbackRequest, HistoricalRequest, TaskResponse
from medops.mcp.contracts import ChunkView, SearchHit, VerifyCitationOutput

TRACE = "a" * 32
NOW = datetime.now(UTC).isoformat()
VERSIONS = {
    "policy_version": "pol-1",
    "retrieval_version": "ret-1",
    "skill_version_set": [],
    "model_config_version": "m-1",
}
CIT = {
    "doc_id": "d1",
    "version": "2026-01",
    "effective_date": "2026-01-01",
    "page": 3,
    "section": "用法用量",
    "chunk_id": "c1",
}
ANSWER = {
    "claims": [{"text": "x", "citation_chunk_ids": ["c1"]}],
    "citations": [CIT],
    "disclaimer": "基于文档检索，仅供专业人员参考",
    "historical_notice": False,
}
REFUSAL = {"reason_codes": ["high_risk_medical"], "message": "拒答"}
ERR = {"code": "dependency_timeout", "message": "服务暂时不可用，请稍后重试", "trace_id": TRACE, "retryable": True}
RESULT = {"trace_id": TRACE, "outcome": "answered", "versions": VERSIONS, "answer": ANSWER}
CONTENT = "孕妇禁用。"
HASH = hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()

CASES: list[tuple[type[BaseModel], dict, bool]] = [
    # HistoricalRequest: exactly one selector
    (HistoricalRequest, {"version": "2025-06"}, True),
    (HistoricalRequest, {"as_of": "2026-01-01"}, True),
    (HistoricalRequest, {}, False),
    (HistoricalRequest, {"version": "v1", "as_of": "2026-01-01"}, False),
    # AskResponse: outcome/payload pairing
    (AskResponse, RESULT, True),
    (AskResponse, {"trace_id": TRACE, "outcome": "refused", "versions": VERSIONS, "refusal": REFUSAL}, True),
    (AskResponse, {"trace_id": TRACE, "outcome": "answered", "versions": VERSIONS}, False),
    (
        AskResponse,
        {"trace_id": TRACE, "outcome": "answered", "versions": VERSIONS, "answer": ANSWER, "refusal": REFUSAL},
        False,
    ),
    (AskResponse, {"trace_id": TRACE, "outcome": "refused", "versions": VERSIONS, "answer": ANSWER}, False),
    # TaskResponse: terminal payloads
    (TaskResponse, {"task_id": "t", "status": "queued", "created_at": NOW, "updated_at": NOW}, True),
    (
        TaskResponse,
        {"task_id": "t", "status": "completed", "created_at": NOW, "updated_at": NOW, "result": RESULT},
        True,
    ),
    (TaskResponse, {"task_id": "t", "status": "completed", "created_at": NOW, "updated_at": NOW}, False),
    (
        TaskResponse,
        {"task_id": "t", "status": "completed", "created_at": NOW, "updated_at": NOW, "result": RESULT, "error": ERR},
        False,
    ),
    (TaskResponse, {"task_id": "t", "status": "failed", "created_at": NOW, "updated_at": NOW, "error": ERR}, True),
    (
        TaskResponse,
        {"task_id": "t", "status": "failed", "created_at": NOW, "updated_at": NOW, "error": ERR, "result": RESULT},
        False,
    ),
    (TaskResponse, {"task_id": "t", "status": "running", "created_at": NOW, "updated_at": NOW, "error": ERR}, False),
    # FeedbackRequest: correction text
    (FeedbackRequest, {"trace_id": TRACE, "signal": "correction", "correction_text": "剂量应为 0.25 g"}, True),
    (FeedbackRequest, {"trace_id": TRACE, "signal": "correction"}, False),
    (FeedbackRequest, {"trace_id": TRACE, "signal": "up", "correction_text": "x"}, False),
    # MCP visibility
    (SearchHit, {"citation": CIT, "snippet": "s", "status": "active"}, True),
    (SearchHit, {"citation": CIT, "snippet": "s", "status": "draft"}, False),
    (SearchHit, {"citation": CIT, "snippet": "s", "status": "archived"}, False),
    (SearchHit, {"citation": CIT, "snippet": "s", "status": "archived", "historical": True}, True),
    (ChunkView, {"citation": CIT, "content": CONTENT, "content_hash": HASH, "status": "active"}, True),
    (ChunkView, {"citation": CIT, "content": CONTENT, "content_hash": HASH, "status": "draft"}, False),
    (VerifyCitationOutput, {"exists": False}, True),
    (VerifyCitationOutput, {"exists": False, "status": "active"}, False),
    (VerifyCitationOutput, {"exists": True}, False),
    (VerifyCitationOutput, {"exists": True, "status": "draft", "fields_match": True}, False),
    (VerifyCitationOutput, {"exists": True, "status": "active", "fields_match": True}, True),
]


@pytest.mark.parametrize("model,payload,valid", CASES, ids=[f"{m.__name__}-{i}" for i, (m, _, _) in enumerate(CASES)])
def test_model_and_exported_schema_agree(model, payload, valid):
    schema = model.model_json_schema()
    schema_ok = Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(payload)
    try:
        model.model_validate(payload)
        model_ok = True
    except ValidationError:
        model_ok = False
    assert model_ok == valid, f"model verdict {model_ok} != expected {valid}"
    assert schema_ok == valid, f"schema verdict {schema_ok} != expected {valid}"


def test_server_side_only_rules_are_documented_as_schema_accepts():
    """These need state or hashing and are intentionally not in the schema; the model still rejects them."""
    tampered = {"citation": CIT, "content": CONTENT, "content_hash": "0" * 64, "status": "active"}
    assert Draft202012Validator(ChunkView.model_json_schema(), format_checker=FormatChecker()).is_valid(tampered)
    with pytest.raises(ValidationError, match="content_hash"):
        ChunkView.model_validate(tampered)
