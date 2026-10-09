"""Public response mapping and error envelope (baseline 5.5 and 5.12)."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi.responses import JSONResponse

from medops.api.contracts import (
    AskResponse,
    EscalationReceipt,
    OutcomeKind,
    Refusal,
)
from medops.core.errors import HTTP_STATUS, ErrorCode, ErrorResponse
from medops.domain.common import ReasonCode
from medops.domain.state import VersionSet
from medops.harness.runtime import HarnessRun

TRACE_HEADER = "X-Trace-Id"
# Refusals (baseline 5.5): the request itself is not answerable by policy. Everything else is an escalation
# the caller can wait on. High-risk questions are refused *and* recorded as an escalation inside the run.
REFUSAL_CODES: frozenset[ReasonCode] = frozenset(
    {ReasonCode.high_risk_medical, ReasonCode.prompt_injection, ReasonCode.acl_denied}
)
PUBLIC_MESSAGES: Mapping[ReasonCode, str] = {
    ReasonCode.high_risk_medical: "该问题涉及诊断、处方或个体用药调整，系统不提供此类回答；已转人工处理",
    ReasonCode.prompt_injection: "请求包含试图改变系统行为的内容，已拒绝",
    ReasonCode.acl_denied: "当前身份无权访问所需文档",
    ReasonCode.insufficient_evidence: "现有文档证据不足以回答该问题，已记录待人工补充",
    ReasonCode.version_conflict: "相关文档存在版本冲突，已升级人工核对",
    ReasonCode.unsupported_conclusion: "生成内容未能通过证据核验，已升级人工处理",
    ReasonCode.budget_exceeded: "本次请求超出处理预算，已升级人工处理",
    ReasonCode.intent_unclear: "问题不够明确，请补充具体药品、文件或场景后重试",
    ReasonCode.system_failure: "系统处理失败，已记录；请稍后重试或等待人工处理",
}


def _error_response(code: ErrorCode, message: str, trace_id: str | None, *, retryable: bool) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, trace_id=trace_id, retryable=retryable)
    return JSONResponse(
        status_code=HTTP_STATUS[code], content=body.model_dump(mode="json"), headers={TRACE_HEADER: trace_id or ""}
    )


def to_ask_response(run: HarnessRun, trace_id: str, versions: VersionSet) -> AskResponse:
    if run.state.answer is not None:
        return AskResponse(trace_id=trace_id, outcome=OutcomeKind.answered, versions=versions, answer=run.state.answer)
    esc = run.state.escalation
    assert esc is not None  # run_ask guarantees an answer or an escalation
    codes = esc.reason_codes
    message = "；".join(dict.fromkeys(PUBLIC_MESSAGES.get(c, c.value) for c in codes))
    if set(codes) <= REFUSAL_CODES:
        return AskResponse(
            trace_id=trace_id,
            outcome=OutcomeKind.refused,
            versions=versions,
            refusal=Refusal(reason_codes=codes, message=message),
        )
    return AskResponse(
        trace_id=trace_id,
        outcome=OutcomeKind.escalated,
        versions=versions,
        escalation=EscalationReceipt(escalation_id=trace_id, reason_codes=codes, message=message),
    )
