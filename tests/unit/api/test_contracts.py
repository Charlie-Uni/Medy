import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from medops.api.contracts import (
    AskRequest,
    AskResponse,
    EscalationReceipt,
    FeedbackRequest,
    FeedbackSignal,
    HistoricalRequest,
    OutcomeKind,
    Refusal,
    TaskCreateRequest,
    TaskResponse,
    TaskStatus,
)
from medops.contracts_export import render
from medops.core.errors import ErrorCode, ErrorResponse
from medops.domain import DISCLAIMER, Answer, Citation, Claim, ReasonCode, VersionSet

REPO = Path(__file__).resolve().parents[3]
VERSIONS = VersionSet(policy_version="pol-1", retrieval_version="ret-1", model_config_version="m-1")
TRACE = "a" * 32
NOW = datetime.now(UTC)


def _answer() -> Answer:
    cit = Citation(
        doc_id="d1", version="2026-01", effective_date=date(2026, 1, 1), page=3, section="用法用量", chunk_id="c1"
    )
    return Answer(claims=(Claim(text="每次 0.5 g，每日 2 次", citation_chunk_ids=("c1",)),), citations=(cit,))


def _err() -> ErrorResponse:
    return ErrorResponse(
        code=ErrorCode.dependency_timeout, message="服务暂时不可用，请稍后重试", trace_id=TRACE, retryable=True
    )


def test_ask_response_carries_exactly_one_outcome_payload():
    ok = AskResponse(trace_id=TRACE, outcome=OutcomeKind.answered, versions=VERSIONS, answer=_answer())
    assert ok.answer is not None and ok.answer.disclaimer == DISCLAIMER
    AskResponse(
        trace_id=TRACE,
        outcome=OutcomeKind.refused,
        versions=VERSIONS,
        refusal=Refusal(reason_codes=(ReasonCode.high_risk_medical,), message="拒答"),
    )
    AskResponse(
        trace_id=TRACE,
        outcome=OutcomeKind.escalated,
        versions=VERSIONS,
        escalation=EscalationReceipt(
            escalation_id="e-1", reason_codes=(ReasonCode.insufficient_evidence,), message="已升级"
        ),
    )
    with pytest.raises(ValidationError, match="exactly its own payload"):
        AskResponse(
            trace_id=TRACE,
            outcome=OutcomeKind.answered,
            versions=VERSIONS,
            refusal=Refusal(reason_codes=(ReasonCode.acl_denied,), message="x"),
        )
    with pytest.raises(ValidationError, match="exactly its own payload"):
        AskResponse(
            trace_id=TRACE,
            outcome=OutcomeKind.refused,
            versions=VERSIONS,
            answer=_answer(),
            refusal=Refusal(reason_codes=(ReasonCode.acl_denied,), message="x"),
        )
    with pytest.raises(ValidationError):
        Refusal(reason_codes=(), message="x")


def test_ask_request_bounds_and_historical_selector():
    AskRequest(query="示例药品X片 用法用量", historical=HistoricalRequest(version="2025-06"))
    with pytest.raises(ValidationError):
        AskRequest(query="")
    with pytest.raises(ValidationError):
        AskRequest(query="x" * 2001)
    with pytest.raises(ValidationError, match="exactly one"):
        HistoricalRequest()
    with pytest.raises(ValidationError, match="exactly one"):
        HistoricalRequest(version="v1", as_of=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        HistoricalRequest(version="")  # empty version is not a selector
    with pytest.raises(ValidationError):
        AskRequest(query="q", dept="MA")  # identity never comes from the body


def test_task_response_terminal_payloads_are_mutually_exclusive():
    TaskResponse(task_id="t1", status=TaskStatus.queued, created_at=NOW, updated_at=NOW)
    ok_done = TaskResponse(
        task_id="t1",
        status=TaskStatus.completed,
        created_at=NOW,
        updated_at=NOW,
        result=AskResponse(trace_id=TRACE, outcome=OutcomeKind.answered, versions=VERSIONS, answer=_answer()),
    )
    ok_failed = TaskResponse(task_id="t1", status=TaskStatus.failed, created_at=NOW, updated_at=NOW, error=_err())
    assert ok_done.error is None and ok_failed.result is None and "detail" not in ok_failed.model_dump_json()
    with pytest.raises(ValidationError, match="carry a result and no error"):
        TaskResponse(task_id="t1", status=TaskStatus.completed, created_at=NOW, updated_at=NOW)
    with pytest.raises(ValidationError, match="carry a result and no error"):  # double payload
        TaskResponse(
            task_id="t1",
            status=TaskStatus.completed,
            created_at=NOW,
            updated_at=NOW,
            result=ok_done.result,
            error=_err(),
        )
    with pytest.raises(ValidationError, match="carry an error and no result"):
        TaskResponse(task_id="t1", status=TaskStatus.failed, created_at=NOW, updated_at=NOW)
    with pytest.raises(ValidationError, match="carry an error and no result"):  # double payload
        TaskResponse(
            task_id="t1", status=TaskStatus.failed, created_at=NOW, updated_at=NOW, result=ok_done.result, error=_err()
        )
    with pytest.raises(ValidationError, match="non-terminal"):
        TaskResponse(task_id="t1", status=TaskStatus.running, created_at=NOW, updated_at=NOW, error=_err())


def test_task_create_rejects_non_finite_numbers_and_bad_names():
    TaskCreateRequest(
        skill_name="off_label_check",
        skill_version="1",
        input={"drug": "示例药品X", "dose_mg": 500, "nested": {"ok": True}},
    )
    with pytest.raises(ValidationError):
        TaskCreateRequest(skill_name="Off-Label", skill_version="1", input={})
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValidationError):
            TaskCreateRequest(skill_name="off_label_check", skill_version="1", input={"dose": bad})
        with pytest.raises(ValidationError):
            TaskCreateRequest(skill_name="off_label_check", skill_version="1", input={"nested": {"list": [1, bad]}})


def test_feedback_rules():
    FeedbackRequest(trace_id=TRACE, signal=FeedbackSignal.correction, correction_text="剂量应为 0.25 g")
    with pytest.raises(ValidationError, match="correction_text"):
        FeedbackRequest(trace_id=TRACE, signal=FeedbackSignal.correction)
    with pytest.raises(ValidationError, match="correction_text"):
        FeedbackRequest(trace_id=TRACE, signal=FeedbackSignal.up, correction_text="x")


def test_committed_schemas_match_the_models():
    stale = []
    for rel, content in render().items():
        path = REPO / "schemas" / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            stale.append(rel)
    assert stale == [], f"run `make schemas` to refresh: {stale}"
    ask = json.loads((REPO / "schemas" / "api" / "AskResponse.schema.json").read_text(encoding="utf-8"))
    assert ask["additionalProperties"] is False and "outcome" in ask["required"] and "allOf" in ask
