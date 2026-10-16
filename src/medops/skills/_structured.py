"""Shared pieces for Skills that go beyond claim-citation answers: a grounded harness run (the only path to
evidence, INV-HAR-03), one strict structured-output call over verified statements, and quote grounding."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import ValidationError

from medops.domain.answer import Claim
from medops.domain.common import DomainModel
from medops.domain.intent import Entity
from medops.domain.skill_judgment import JudgmentVerification
from medops.harness.audit import audit_step
from medops.harness.runtime import HarnessRun, initial_state, run_ask
from medops.infrastructure.llm.gateway import Message, ModelOutputInvalid, ModelRequest
from medops.skills.registry import SkillContext
from medops.verification.skill_judgment import BusinessJudgment, verify_business_judgments

STRUCTURED_MAX_OUTPUT_TOKENS = 800  # reasoning tiers spend output tokens before the JSON (record 54 §3.1)
_WS = re.compile(r"\s+")
_T = TypeVar("_T", bound=DomainModel)


def grounded_run(ctx: SkillContext, query: str, entities: Sequence[Entity] = ()) -> HarnessRun:
    """Intent -> Retrieve -> Verify -> Safety -> Answer under the caller's identity and the run's version set."""
    state = initial_state(
        user=ctx.user,
        query=query,
        versions=ctx.versions,
        trace_id=ctx.trace_id,
        run_id=ctx.run_id,
        session_entities=tuple(entities),
        query_context=ctx.query_context,
    )
    return run_ask(state, ctx.deps)


def numbered_statements(claims: Sequence[Claim]) -> str:
    return "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims, 1))


def structured_call(
    ctx: SkillContext, *, purpose: str, system: str, user: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """One strict-schema call through the gateway; the reply must be a JSON object or the Skill fails closed."""
    with audit_step(ctx.deps.audit, f"{purpose}:generate", {"system": system, "user": user, "schema": schema}) as audit:
        result = _structured_call(ctx, purpose=purpose, system=system, user=user, schema=schema, audit=audit)
    return result


def structured_request(
    ctx: SkillContext, *, purpose: str, system: str, user: str, schema: dict[str, Any]
) -> ModelRequest:
    """The actual request, shared with read-only budget planning."""
    return ModelRequest(
        purpose=purpose,
        model_id=ctx.deps.answer_model_id,
        messages=(Message(role="system", content=system), Message(role="user", content=user)),
        max_output_tokens=STRUCTURED_MAX_OUTPUT_TOKENS,
        json_schema=schema,
        timeout_s=min(ctx.deps.specs["answer"].timeout_s, 120),
    )


def _structured_call(
    ctx: SkillContext, *, purpose: str, system: str, user: str, schema: dict[str, Any], audit: dict[str, Any]
) -> dict[str, Any]:
    response = ctx.deps.gateway.complete(
        structured_request(ctx, purpose=purpose, system=system, user=user, schema=schema)
    )
    audit["output"] = {"text": response.text, "parsed": response.parsed, "truncated": response.truncated}
    if response.truncated:
        raise ModelOutputInvalid(f"{purpose}: structured output truncated")
    parsed = response.parsed
    if parsed is None:
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ModelOutputInvalid(f"{purpose}: reply is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ModelOutputInvalid(f"{purpose}: reply is not a JSON object")
    return parsed


def normalize_quote(text: str) -> str:
    return _WS.sub("", text).casefold()


def quote_grounded(quote: str, source: str) -> bool:
    """The quote must occur verbatim in the source (whitespace and case ignored); nothing is inferred."""
    q = normalize_quote(quote)
    return len(q) >= 2 and q in normalize_quote(source)


def validate_structured(parsed: dict[str, Any], model: type[_T]) -> _T:
    """Provider JSON Schema is not a substitute for checking the received payload locally."""
    try:
        return model.model_validate(parsed)
    except ValidationError as exc:
        raise ModelOutputInvalid("structured skill reply violates its contract") from exc


def verify_final_judgments(
    ctx: SkillContext, judgments: Sequence[BusinessJudgment], clauses: Sequence[Claim]
) -> JudgmentVerification:
    with audit_step(
        ctx.deps.audit,
        "skill:verify_judgment",
        {
            "judgments": [j.model_dump(mode="json") for j in judgments],
            "clauses": [c.model_dump(mode="json") for c in clauses],
        },
    ) as audit:
        result = verify_business_judgments(
            judgments,
            clauses,
            gateway=ctx.deps.gateway,
            judge_model_id=ctx.deps.judge_model_id,
            timeout_s=ctx.deps.specs["verify"].timeout_s,
        )
        audit["output"] = result.model_dump(mode="json")
        return result
