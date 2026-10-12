"""MCP restricted material schema. No bodies enter metadata exporters or public errors."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from medops.application.search import SearchExecution
from medops.core.canonical import canonical_hash
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.identity import UserContext

FORMAT = "mcp-audit-v1"
MAX_BYTES = 16 * 1024 * 1024


def tool_payloads(
    *,
    tool: str,
    input_body: Mapping[str, Any],
    user: UserContext,
    versions: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
    stats: SearchExecution,
    outcome: str,
    result: Mapping[str, Any] | None,
    error_type: str | None,
    reason_codes: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    material: dict[str, Mapping[str, Any]] = {
        "input": {
            "format_version": FORMAT,
            "tool": tool,
            "input": dict(input_body),
            "input_sha256": canonical_hash(input_body),
            "user": user.model_dump(mode="json"),
            "versions": dict(versions),
            "query_context": stats.query_context.model_dump(mode="json") if stats.query_context else None,
            "conditions": stats.conditions,
        },
        "evidence_snapshot": {
            "format_version": FORMAT,
            "observed": dict(snapshot) if snapshot is not None else None,
            "observation_available": snapshot is not None,
        },
        "model_output": {
            "format_version": FORMAT,
            "tool_result": dict(result) if result is not None else None,
            "outcome": outcome,
            "reason_codes": list(reason_codes),
            "error_type": error_type,
            "model_calls": list(stats.call_records),
            "call_receipts": list(stats.call_receipts),
            "model_call_audit_complete": stats.call_audit_complete,
        },
    }
    if outcome == "answered" and not stats.call_audit_complete:
        raise InfrastructureError(ErrorCode.audit_unavailable, detail="MCP model call journal incomplete")
    encoded = json.dumps(material, ensure_ascii=False, default=str, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        if outcome == "answered":
            raise InfrastructureError(ErrorCode.audit_unavailable, detail="MCP restricted material capacity exceeded")
        # Failure retains bounded identity/hash/accounting instead of publishing an incomplete success.
        material = {
            "input": {
                "format_version": FORMAT,
                "tool": tool,
                "input_sha256": canonical_hash(input_body),
                "user_sha256": canonical_hash(user.model_dump(mode="json")),
                "dept": user.dept.value,
                "input_audit_complete": False,
            },
            "evidence_snapshot": {"format_version": FORMAT, "observation_available": False},
            "model_output": {
                "format_version": FORMAT,
                "outcome": outcome,
                "reason_codes": list(reason_codes),
                "error_type": error_type,
                "model_call_audit_complete": False,
                "material_capacity_exceeded": True,
                "call_receipts": list(stats.call_receipts),
            },
        }
        fallback_size = len(json.dumps(material, ensure_ascii=False, default=str, allow_nan=False).encode("utf-8"))
        if fallback_size > MAX_BYTES:
            material["model_output"] = {
                **material["model_output"],
                "call_receipts": [],
                "call_receipts_sha256": canonical_hash(stats.call_receipts),
                "call_receipts_included": False,
            }
    return material
