"""Unified error model (baseline M0-05).

Two families with different audiences:
- `BusinessError`: caused by the request, the caller's permissions or a domain rule. The public
  message is safe to return; never retryable by itself.
- `InfrastructureError`: a dependency, timeout or internal fault. Clients only ever see the generic
  message; `detail` stays in logs. Retryable unless it is an unexplained internal error.

`detail` is internal-only and is excluded from `str()` and from the public `ErrorResponse`, so a
handler cannot leak it by accident. Refusals and escalations are NOT errors: they are domain
outcomes carried by `medops.domain.ReasonCode`; the only bridge is that an infrastructure failure
inside a run escalates with `ReasonCode.system_failure`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    # client / request
    invalid_request = "invalid_request"
    schema_violation = "schema_violation"
    idempotency_payload_mismatch = "idempotency_payload_mismatch"
    rate_limited = "rate_limited"
    # identity
    unauthenticated = "unauthenticated"
    forbidden = "forbidden"
    # domain / fact plane
    not_found = "not_found"
    version_conflict = "version_conflict"
    task_not_retryable = "task_not_retryable"  # retry requested for a task that is not failed+retryable
    status_conflict = "status_conflict"  # illegal document / policy state transition (M3-03)
    gate_not_passed = "gate_not_passed"  # release requested without a passing gate report (M3-03 / M4-08)
    evidence_integrity_failed = "evidence_integrity_failed"
    # infrastructure
    dependency_timeout = "dependency_timeout"
    dependency_unavailable = "dependency_unavailable"
    audit_unavailable = "audit_unavailable"  # trace/audit write failed: fail safe, never answer unaudited (5.10)
    internal_error = "internal_error"


class ErrorCategory(StrEnum):
    client = "client"
    identity = "identity"
    domain = "domain"
    infrastructure = "infrastructure"


CATEGORY: Final[dict[ErrorCode, ErrorCategory]] = {
    ErrorCode.invalid_request: ErrorCategory.client,
    ErrorCode.schema_violation: ErrorCategory.client,
    ErrorCode.idempotency_payload_mismatch: ErrorCategory.client,
    ErrorCode.rate_limited: ErrorCategory.client,
    ErrorCode.unauthenticated: ErrorCategory.identity,
    ErrorCode.forbidden: ErrorCategory.identity,
    ErrorCode.not_found: ErrorCategory.domain,
    ErrorCode.version_conflict: ErrorCategory.domain,
    ErrorCode.task_not_retryable: ErrorCategory.domain,
    ErrorCode.status_conflict: ErrorCategory.domain,
    ErrorCode.gate_not_passed: ErrorCategory.domain,
    ErrorCode.evidence_integrity_failed: ErrorCategory.domain,
    ErrorCode.dependency_timeout: ErrorCategory.infrastructure,
    ErrorCode.dependency_unavailable: ErrorCategory.infrastructure,
    ErrorCode.audit_unavailable: ErrorCategory.infrastructure,
    ErrorCode.internal_error: ErrorCategory.infrastructure,
}

HTTP_STATUS: Final[dict[ErrorCode, int]] = {
    ErrorCode.invalid_request: 400,
    ErrorCode.schema_violation: 422,
    ErrorCode.idempotency_payload_mismatch: 422,
    ErrorCode.rate_limited: 429,
    ErrorCode.unauthenticated: 401,
    ErrorCode.forbidden: 403,
    ErrorCode.not_found: 404,
    ErrorCode.version_conflict: 409,
    ErrorCode.task_not_retryable: 409,
    ErrorCode.status_conflict: 409,
    ErrorCode.gate_not_passed: 409,
    ErrorCode.evidence_integrity_failed: 500,
    ErrorCode.dependency_timeout: 504,
    ErrorCode.dependency_unavailable: 503,
    ErrorCode.audit_unavailable: 503,
    ErrorCode.internal_error: 500,
}

GENERIC_INFRA_MESSAGE: Final = "服务暂时不可用，请稍后重试"

# Codes whose public text is fixed regardless of what the raiser passes; the passed text becomes detail.
FIXED_PUBLIC_MESSAGES: Final[dict[ErrorCode, str]] = {
    ErrorCode.evidence_integrity_failed: "证据完整性校验未通过，无法提供回答，需要人工核验",
}

# `retryable` is a hint for callers; any executor still applies its own attempt limit, budget and
# idempotency rules. While the audit path is unavailable the write may be retried but no medical
# answer may be produced (baseline 5.10).
RETRYABLE_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {
        ErrorCode.dependency_timeout,
        ErrorCode.dependency_unavailable,
        ErrorCode.audit_unavailable,
    }
)


class ErrorResponse(BaseModel):
    """Public wire format. Contains no internal detail by construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ErrorCode
    message: str = Field(min_length=1)
    trace_id: str | None = None
    retryable: bool


class MedOpsError(Exception):
    code: ErrorCode
    category: ErrorCategory
    retryable: bool

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        detail: str | None = None,
        trace_id: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        if type(self) is MedOpsError:
            raise TypeError("raise BusinessError or InfrastructureError, not MedOpsError")
        self.code = code
        self.category = CATEGORY[code]
        self.message = message
        self.detail = detail
        self.trace_id = trace_id
        self.retryable = self._default_retryable(code) if retryable is None else retryable
        super().__init__(message)

    @staticmethod
    def _default_retryable(code: ErrorCode) -> bool:
        return False

    def __str__(self) -> str:  # never includes detail
        return f"{self.code.value}: {self.message}"

    @property
    def http_status(self) -> int:
        return HTTP_STATUS[self.code]

    def public(self, trace_id: str | None = None) -> ErrorResponse:
        return ErrorResponse(
            code=self.code, message=self.message, trace_id=trace_id or self.trace_id, retryable=self.retryable
        )


class BusinessError(MedOpsError):
    """Request-, identity- or domain-caused. `message` is shown to the caller as written."""

    def __init__(
        self, code: ErrorCode, message: str, *, detail: str | None = None, trace_id: str | None = None
    ) -> None:
        if CATEGORY[code] is ErrorCategory.infrastructure:
            raise ValueError(f"{code.value} is an infrastructure code; raise InfrastructureError")
        fixed = FIXED_PUBLIC_MESSAGES.get(code)
        if fixed is not None:
            detail = message if detail is None else f"{message}; {detail}"
            message = fixed
        super().__init__(code, message, detail=detail, trace_id=trace_id, retryable=False)


class InfrastructureError(MedOpsError):
    """Dependency or internal fault. The caller only sees the generic message; `detail` is for logs."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str | None = None,
        *,
        trace_id: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        if CATEGORY[code] is not ErrorCategory.infrastructure:
            raise ValueError(f"{code.value} is not an infrastructure code; raise BusinessError")
        super().__init__(code, GENERIC_INFRA_MESSAGE, detail=detail, trace_id=trace_id, retryable=retryable)

    @staticmethod
    def _default_retryable(code: ErrorCode) -> bool:
        return code in RETRYABLE_CODES
