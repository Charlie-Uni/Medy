import pytest
from pydantic import ValidationError

from medops.core.errors import (
    CATEGORY,
    GENERIC_INFRA_MESSAGE,
    HTTP_STATUS,
    BusinessError,
    ErrorCategory,
    ErrorCode,
    ErrorResponse,
    InfrastructureError,
    MedOpsError,
)


def test_every_code_has_a_category_and_http_status():
    assert set(CATEGORY) == set(ErrorCode) == set(HTTP_STATUS)
    assert len({c.value for c in ErrorCode}) == len(ErrorCode)
    assert all(400 <= s < 600 for s in HTTP_STATUS.values())
    for code, cat in CATEGORY.items():
        assert (HTTP_STATUS[code] >= 500) == (
            cat is ErrorCategory.infrastructure
        ) or code is ErrorCode.evidence_integrity_failed


def test_base_class_cannot_be_raised_directly():
    with pytest.raises(TypeError):
        MedOpsError(ErrorCode.internal_error, "x")


def test_business_error_is_public_and_not_retryable():
    err = BusinessError(ErrorCode.forbidden, "no MA:read scope", detail="user u-1 lacks MA:read", trace_id="a" * 32)
    assert err.http_status == 403 and err.retryable is False and err.category is ErrorCategory.identity
    assert str(err) == "forbidden: no MA:read scope"
    public = err.public()
    assert public == ErrorResponse(
        code=ErrorCode.forbidden, message="no MA:read scope", trace_id="a" * 32, retryable=False
    )
    assert "u-1" not in public.model_dump_json() and "u-1" not in str(err)


def test_infrastructure_error_hides_detail_and_defaults_retryable():
    err = InfrastructureError(ErrorCode.dependency_timeout, detail="postgres timeout after 2s at host db-1")
    assert err.message == GENERIC_INFRA_MESSAGE and err.retryable is True and err.http_status == 504
    assert "db-1" not in str(err) and "db-1" not in err.public(trace_id="b" * 32).model_dump_json()
    assert InfrastructureError(ErrorCode.internal_error, detail="boom").retryable is False
    assert InfrastructureError(ErrorCode.audit_unavailable).retryable is True


def test_category_mismatch_is_rejected_at_construction():
    with pytest.raises(ValueError):
        BusinessError(ErrorCode.dependency_timeout, "x")
    with pytest.raises(ValueError):
        InfrastructureError(ErrorCode.forbidden)


def test_error_response_is_frozen_and_forbids_extra():
    with pytest.raises(ValidationError):
        ErrorResponse(code=ErrorCode.not_found, message="m", retryable=False, detail="leak")
    resp = ErrorResponse(code=ErrorCode.not_found, message="m", retryable=False)
    with pytest.raises(ValidationError):
        resp.message = "changed"  # type: ignore[misc]


def test_retryable_is_an_explicit_code_set():
    from medops.core.errors import RETRYABLE_CODES

    assert RETRYABLE_CODES == {
        ErrorCode.dependency_timeout,
        ErrorCode.dependency_unavailable,
        ErrorCode.audit_unavailable,
    }
    assert all(CATEGORY[c] is ErrorCategory.infrastructure for c in RETRYABLE_CODES)
    assert InfrastructureError(ErrorCode.dependency_unavailable).retryable is True
    assert InfrastructureError(ErrorCode.dependency_unavailable, retryable=False).retryable is False


def test_evidence_integrity_failure_has_fixed_public_text_and_keeps_input_as_detail():
    from medops.core.errors import FIXED_PUBLIC_MESSAGES

    err = BusinessError(ErrorCode.evidence_integrity_failed, "SYNTHETIC_INTERNAL_DETAIL chunk c9 hash mismatch")
    assert err.message == FIXED_PUBLIC_MESSAGES[ErrorCode.evidence_integrity_failed]
    assert (
        "SYNTHETIC_INTERNAL_DETAIL" not in str(err)
        and "SYNTHETIC_INTERNAL_DETAIL" not in err.public().model_dump_json()
    )
    assert err.detail is not None and "SYNTHETIC_INTERNAL_DETAIL" in err.detail
    err2 = BusinessError(ErrorCode.evidence_integrity_failed, "msg", detail="extra")
    assert err2.detail == "msg; extra"
