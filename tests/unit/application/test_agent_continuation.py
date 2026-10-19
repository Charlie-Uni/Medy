from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from medops.application.agent_continuation import (
    ClarificationPolicy,
    ContinuationAuthorization,
    ContinueAgent,
    continuation_identity,
)


@pytest.mark.parametrize("field", ["ttl_seconds", "max_continuations", "cost_limit_microusd"])
def test_case_lifetime_count_and_total_cost_have_no_implicit_defaults(field):
    raw = dict(ttl_seconds=3600, max_continuations=2, cost_limit_microusd=2000000)
    del raw[field]
    with pytest.raises(ValidationError):
        ClarificationPolicy.model_validate(raw)


@pytest.mark.parametrize("value", [0, -1, True, "2", 2.5])
def test_no_unbounded_or_coerced_case_policy(value):
    with pytest.raises(ValidationError):
        ClarificationPolicy(ttl_seconds=value, max_continuations=2, cost_limit_microusd=2000000)


def test_batch_requires_explicit_scope_deadline_count_cost_and_approval_reference():
    raw = dict(
        batch_id=uuid4(),
        approval_sha256="a" * 64,
        case_ids=[uuid4()],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        max_executions=2,
        cost_limit_microusd=1200000,
    )
    for field in raw:
        with pytest.raises(ValidationError):
            ContinuationAuthorization.model_validate({k: v for k, v in raw.items() if k != field})
    with pytest.raises(ValidationError):
        ContinuationAuthorization.model_validate(raw | {"case_ids": raw["case_ids"] * 2})


def test_command_has_no_profile_identity_or_budget_override_and_duplicate_answers_fail():
    raw = dict(
        command_id=uuid4(),
        batch_id=uuid4(),
        expected_revision=1,
        answers=[dict(field="source_version", value="PUBLIC v1")],
    )
    for override in (
        {"cost_limit": 999},
        {"case_id": uuid4()},
        {"same_run_resumable": True},
        {"answers": raw["answers"] * 2},
        {"answers": [dict(field="source_version", value="   ")]},
    ):
        with pytest.raises(ValidationError):
            ContinueAgent.model_validate(raw | override)
    case_id, command_id = uuid4(), uuid4()
    identity = continuation_identity(case_id, command_id)
    assert identity == continuation_identity(case_id, command_id) and identity.case_id == case_id
    assert identity.run_id != continuation_identity(case_id, uuid4()).run_id
