"""Validate restricted execution input and report observed condition differences.

These comparisons identify differences; they do not establish causal contribution,
pin a hosted provider's weights, or reconstruct corpus/index snapshots.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field

from medops.api.contracts import AskRequest, ReplayConditions, TracePayloadResponse
from medops.application.audit import TraceSummary
from medops.core.canonical import canonical_hash
from medops.domain.common import DomainModel
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.query import QueryContext
from medops.domain.state import VersionSet
from medops.infrastructure.llm.gateway import ModelCallReceipt, ModelRequest, ModelResponse


class SavedAskInput(DomainModel):
    query: str
    user: UserContext
    versions: VersionSet
    token_limit: int = Field(strict=True, gt=0, le=12_000)
    session_entities: tuple[Entity, ...] = ()
    historical_requested: bool
    query_context: QueryContext
    recursion_limit: int = Field(strict=True, gt=0, le=12)


def payload_sections(response: TracePayloadResponse) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in response.items:
        if item.node != "ask":
            continue
        if item.kind in result:
            raise ValueError("ambiguous source payload")
        if not isinstance(item.payload, Mapping):
            raise ValueError("source payload must be an object")
        result[item.kind] = item.payload
    return result


def saved_input(
    payloads: Mapping[str, Mapping[str, Any]], source: TraceSummary
) -> tuple[AskRequest, SavedAskInput] | None:
    data = payloads.get("input", {})
    if data.get("format_version") != "ask-audit-v2":
        if data.get("format_version") is not None:
            raise ValueError("unsupported source execution payload version")
        return None
    request = AskRequest.model_validate(data.get("request"))
    saved = SavedAskInput.model_validate(data.get("execution_input"))
    if (
        request.query != source.query
        or saved.query != source.query
        or saved.user.user_id != source.principal
        or saved.user.dept != source.dept
        or saved.query_context != source.query_context
        or saved.versions.model_dump(mode="json") != dict(source.versions)
        or saved.historical_requested != saved.query_context.historical_requested
        or (request.historical is not None) != saved.historical_requested
        or (request.historical is not None and request.historical.as_of != saved.query_context.as_of)
    ):
        raise ValueError("source payload disagrees with trace")
    return request, saved


def validate_call_records(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    """Bad source records are rejected before starting another chargeable execution."""
    calls = payloads.get("model_output", {}).get("model_calls", [])
    if not isinstance(calls, list):
        raise ValueError("model call records must be an array")
    for row in calls:
        model_request = ModelRequest.model_validate(row["request"])
        receipt = ModelCallReceipt.model_validate(row["receipt"])
        if (
            model_request.call is None
            or model_request.call.call_id != row["call_id"]
            or receipt.call.call_id != row["call_id"]
            or canonical_hash(row["request"]) != row["request_sha256"]
        ):
            raise ValueError("source model call identity/hash mismatch")
        if row.get("response") is not None:
            response = ModelResponse.model_validate(row["response"])
            if response.call_receipt is not None and response.call_receipt != receipt:
                raise ValueError("source response receipt mismatch")


def compare_conditions(
    source: Mapping[str, Mapping[str, Any]], replay: Mapping[str, Mapping[str, Any]], *, input_complete: bool
) -> ReplayConditions:
    old, new = source.get("input", {}), replay.get("input", {})
    a, b = old.get("execution_input", {}), new.get("execution_input", {})
    ca, cb = old.get("conditions", {}), new.get("conditions", {})
    if not all(isinstance(value, Mapping) for value in (a, b, ca, cb)):
        raise ValueError("execution inputs and conditions must be objects")
    evidence_a, evidence_b = source.get("evidence_snapshot", {}), replay.get("evidence_snapshot", {})
    rendered_a, rendered_b = evidence_a.get("rendered_evidence"), evidence_b.get("rendered_evidence")
    call_a = source.get("model_output", {}).get("model_calls")
    call_b = replay.get("model_output", {}).get("model_calls")

    def models(calls: Any) -> list[tuple[str, str, str | None, str | None, str | None]]:
        return [
            (
                c["request"]["purpose"],
                c["request"]["model_id"],
                (c.get("response") or {}).get("provider"),
                (c.get("response") or {}).get("model_id"),
                (c.get("response") or {}).get("system_fingerprint"),
            )
            for c in calls
        ]

    def renderings(events: Any) -> list[dict[str, Any]]:
        return [{k: e[k] for k in ("focus_mode", "body", "chunk_aliases", "fragments")} for e in events]

    def model_sequence_known(calls: Any) -> bool:
        return all(
            not c["receipt"]["provider_started"] or c["receipt"].get("response_model") is not None for c in calls
        )

    keys = ("query", "session_entities", "historical_requested", "query_context", "token_limit", "recursion_limit")
    limitations = [
        "current_permissions_facts_and_policies",
        "corpus_and_index_snapshot_not_restored",
        "source_files_not_attested_loaded_build",
        "provider_weights_and_nondeterminism_unpinned",
        "differences_are_not_causal_attribution",
    ]
    if not input_complete:
        limitations.append("complete_source_input_unavailable")
    return ReplayConditions(
        input_complete=input_complete,
        input_match=(all(a.get(k) == b.get(k) for k in keys) and old.get("request") == new.get("request"))
        if input_complete
        else None,
        identity_match=a.get("user") == b.get("user") if input_complete else None,
        source_artifacts_match=ca.get("artifacts") == cb.get("artifacts") if ca.get("artifacts") else None,
        configuration_match=ca.get("configuration") == cb.get("configuration") if ca.get("configuration") else None,
        routed_policy_match=ca.get("routed") == cb.get("routed") if ca.get("routed") else None,
        evidence_match=evidence_a.get("evidence") == evidence_b.get("evidence") if "evidence" in evidence_a else None,
        rendered_evidence_match=renderings(rendered_a) == renderings(rendered_b)
        if rendered_a is not None and rendered_b is not None
        else None,
        actual_models_match=models(call_a) == models(call_b)
        if call_a is not None and call_b is not None and model_sequence_known(call_a) and model_sequence_known(call_b)
        else None,
        limitations=tuple(limitations),
    )
