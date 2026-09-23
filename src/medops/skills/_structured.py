"""Shared pieces for Skills that go beyond claim-citation answers: a grounded harness run (the only path to
evidence, INV-HAR-03), one strict structured-output call over verified statements, and quote grounding."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from medops.domain.answer import Claim
from medops.domain.intent import Entity
from medops.harness.runtime import HarnessRun, initial_state, run_ask
from medops.infrastructure.llm.gateway import Message, ModelOutputInvalid, ModelRequest
from medops.skills.registry import SkillContext

STRUCTURED_MAX_OUTPUT_TOKENS = 800  # reasoning tiers spend output tokens before the JSON (record 54 §3.1)
_WS = re.compile(r"\s+")


def grounded_run(ctx: SkillContext, query: str, entities: Sequence[Entity] = ()) -> HarnessRun:
    """Intent -> Retrieve -> Verify -> Safety -> Answer under the caller's identity and the run's version set."""
    state = initial_state(
        user=ctx.user,
        query=query,
        versions=ctx.versions,
        trace_id=ctx.trace_id,
        run_id=ctx.run_id,
        session_entities=tuple(entities),
    )
    return run_ask(state, ctx.deps)


def numbered_statements(claims: Sequence[Claim]) -> str:
    return "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims, 1))


def structured_call(
    ctx: SkillContext, *, purpose: str, system: str, user: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """One strict-schema call through the gateway; the reply must be a JSON object or the Skill fails closed."""
    response = ctx.deps.gateway.complete(
        ModelRequest(
            purpose=purpose,
            model_id=ctx.deps.answer_model_id,
            messages=(Message(role="system", content=system), Message(role="user", content=user)),
            max_output_tokens=STRUCTURED_MAX_OUTPUT_TOKENS,
            json_schema=schema,
            timeout_s=min(ctx.deps.specs["answer"].timeout_s, 120),
        )
    )
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


def valid_indices(raw: Any, upper: int) -> tuple[int, ...]:
    """1-based statement indices from the model, de-duplicated; anything outside 1..upper is dropped."""
    if not isinstance(raw, list):
        return ()
    out: list[int] = []
    for item in raw:
        if isinstance(item, int) and 1 <= item <= upper and item not in out:
            out.append(item)
    return tuple(out)
