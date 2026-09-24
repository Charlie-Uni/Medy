"""OpenAPI 3.1 document for the public REST contract (baseline 5.7, M0-08).

Built from the same Pydantic models as `schemas/api/*.schema.json` and without a web framework:
`components.schemas` are exactly the standalone schemas with `#/$defs/` rewritten to
`#/components/schemas/` (a test asserts that equality), so there is one definition of every wire
model. Paths cover the endpoints whose request and response models exist (design document 3.10);
admin, policy and trace-replay endpoints join when their models are defined in M1/M3/M4.

Error responses are derived from `core.errors.HTTP_STATUS`: every operation lists every status the
unified error handler can emit, each pointing at `ErrorResponse`. The document is exported to
`schemas/openapi.json` by `medops.contracts_export` and guarded against drift by `--check`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from medops.api.contracts import IDEMPOTENCY_KEY_HEADER
from medops.core.errors import HTTP_STATUS, ErrorCode

OPENAPI_VERSION = "3.1.0"
API_VERSION = "0.1.0"
"""Contract version of this document; any breaking change to a path or model bumps it."""

REF_TEMPLATE = "#/components/schemas/{model}"
BEARER_SCHEME = "bearerAuth"
IDEMPOTENCY_PARAMETER = "IdempotencyKey"
TASK_ID_PARAMETER = "TaskId"
TRACE_ID_PARAMETER = "TraceIdPath"
IDEMPOTENCY_TTL_MIN_SECONDS = 24 * 3600
IDEMPOTENCY_TTL_DEFAULT_SECONDS = 7 * 24 * 3600
"""Baseline 3.2: keys are retained at least 24 h and not shorter than the task lifetime. The deployed value
comes from `Settings.idempotency_key_ttl_seconds` (default 7 days, floor 24 h) and is published here."""

IDEMPOTENCY_DESCRIPTION = (
    f"`{IDEMPOTENCY_KEY_HEADER}` (baseline 3.2). Scope is authenticated principal + route + key; the server "
    "stores the canonical request hash. Same key and same payload returns the original receipt with the "
    "original status code, also while the first request is still processing (never 409). Same key with a "
    "different payload returns 422 `idempotency_payload_mismatch`. The record and the idempotency entry are "
    f"created in one transaction. Retention is configured by IDEMPOTENCY_KEY_TTL_SECONDS (default "
    f"{IDEMPOTENCY_TTL_DEFAULT_SECONDS} seconds, never below {IDEMPOTENCY_TTL_MIN_SECONDS} seconds) and never shorter "
    "than the task lifetime."
)

INFO_DESCRIPTION = (
    "Public REST contract of MedOps Copilot (baseline 5.7). Identity always comes from the verified bearer "
    "token; request bodies never carry `dept` or `scopes`. Every error uses `ErrorResponse` (code, message, "
    "trace_id, retryable) with no internal detail. Final medical answers are never streamed before the safety "
    "check completes (INV-SAF-05). Admin document endpoints (M1), trace replay (M3-08) and policy approval "
    "(M4) are added to this document when their models exist."
)


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _json_body(schema: dict[str, Any]) -> dict[str, Any]:
    return {"content": {"application/json": {"schema": schema}}}


def _codes_by_status() -> dict[int, list[ErrorCode]]:
    by_status: dict[int, list[ErrorCode]] = {}
    for code, status in HTTP_STATUS.items():
        by_status.setdefault(status, []).append(code)
    return dict(sorted(by_status.items()))


def _error_responses() -> dict[str, dict[str, Any]]:
    return {
        f"Error{status}": {
            "description": "`ErrorResponse` with `code` in: " + ", ".join(f"`{c.value}`" for c in codes),
            **_json_body(_ref("ErrorResponse")),
        }
        for status, codes in _codes_by_status().items()
    }


def _operation(
    operation_id: str,
    summary: str,
    description: str,
    *,
    tag: str,
    success_status: int,
    success_description: str,
    response_model: str,
    request_model: str | None = None,
    parameters: tuple[str, ...] = (),
) -> dict[str, Any]:
    responses: dict[str, Any] = {
        str(success_status): {"description": success_description, **_json_body(_ref(response_model))},
    }
    for status in _codes_by_status():
        responses[str(status)] = {"$ref": f"#/components/responses/Error{status}"}
    operation: dict[str, Any] = {
        "operationId": operation_id,
        "summary": summary,
        "description": description,
        "tags": [tag],
        "responses": responses,
    }
    if parameters:
        operation["parameters"] = [{"$ref": f"#/components/parameters/{p}"} for p in parameters]
    if request_model is not None:
        operation["requestBody"] = {"required": True, **_json_body(_ref(request_model))}
    return operation


def _paths() -> dict[str, Any]:
    return {
        "/v1/ask": {
            "post": _operation(
                "askQuestion",
                "Synchronous question answering",
                "Runs the fixed `Intent -> Retrieve -> Evidence Verify -> Safety Check -> Answer / Escalate` chain. "
                "`outcome` is exactly one of answered, refused, escalated and only its own payload is present; "
                "refusals and escalations carry stable reason codes. Archived versions are only returned for an "
                "explicit `historical` selector (INV-DATA-03).",
                tag="ask",
                success_status=200,
                success_description="Answer, refusal or escalation for this trace.",
                response_model="AskResponse",
                request_model="AskRequest",
            ),
        },
        "/v1/tasks": {
            "post": _operation(
                "createTask",
                "Submit an asynchronous skill task",
                "Creates a task for a registered skill; `input` is validated against the skill's registered schema "
                "at execution time (M2-11). The response is the task in `queued` state. " + IDEMPOTENCY_DESCRIPTION,
                tag="tasks",
                success_status=202,
                success_description="Task accepted (or the original task for a repeated `Idempotency-Key`).",
                response_model="TaskResponse",
                request_model="TaskCreateRequest",
                parameters=(IDEMPOTENCY_PARAMETER,),
            ),
        },
        "/v1/tasks/{task_id}": {
            "parameters": [{"$ref": f"#/components/parameters/{TASK_ID_PARAMETER}"}],
            "get": _operation(
                "getTask",
                "Read task status and result",
                "`completed` carries `result` and no `error`; `failed` carries `error` and no `result`; "
                "`queued`/`running` carry neither. Tasks outside the caller's visibility are `404 not_found`.",
                tag="tasks",
                success_status=200,
                success_description="Current task state.",
                response_model="TaskResponse",
            ),
        },
        "/v1/tasks/{task_id}/retry": {
            "parameters": [{"$ref": f"#/components/parameters/{TASK_ID_PARAMETER}"}],
            "post": _operation(
                "retryTask",
                "Re-queue a failed, retryable task",
                "Allowed only when the task is `failed` and `error.retryable` is true; any other state is rejected "
                "with `409 task_not_retryable`. The retry runs under the same task id with a new attempt record.",
                tag="tasks",
                success_status=202,
                success_description="Task re-queued.",
                response_model="TaskResponse",
            ),
        },
        "/v1/feedback": {
            "post": _operation(
                "submitFeedback",
                "Record feedback for a trace",
                "`correction` requires `correction_text`; `up`/`down` must not carry it. " + IDEMPOTENCY_DESCRIPTION,
                tag="feedback",
                success_status=201,
                success_description="Feedback receipt (or the original receipt for a repeated `Idempotency-Key`).",
                response_model="FeedbackReceipt",
                request_model="FeedbackRequest",
                parameters=(IDEMPOTENCY_PARAMETER,),
            ),
        },
        "/admin/traces/{trace_id}/replay": {
            "parameters": [{"$ref": f"#/components/parameters/{TRACE_ID_PARAMETER}"}],
            "post": _operation(
                "replayTrace",
                "Re-run one trace under a fresh replay run id (admin)",
                "Runs the original question again under the original principal's current identity and this "
                "deployment's pinned versions, with an independent `replay_run_id` so no result of the production "
                "run is reused (baseline 3.2, M3-08). Returns both sides and the fields that changed. Requires the "
                "admin role.",
                tag="admin",
                success_status=201,
                success_description="Replay report.",
                response_model="ReplayReport",
                request_model="ReplayRequest",
            ),
        },
    }


def build_openapi(models: Mapping[str, type[BaseModel]]) -> dict[str, Any]:
    """Return the OpenAPI 3.1 document as a plain dict. `models` are the public API models
    (name -> model); the same mapping feeds the standalone schema export."""
    _, definitions = models_json_schema([(m, "validation") for m in models.values()], ref_template=REF_TEMPLATE)
    schemas: dict[str, Any] = dict(sorted(definitions["$defs"].items()))
    missing = sorted(set(models) - set(schemas))
    if missing:  # every named model must be addressable as a component
        raise ValueError(f"models without a component schema: {missing}")
    return {
        "openapi": OPENAPI_VERSION,
        "info": {"title": "MedOps Copilot API", "version": API_VERSION, "description": INFO_DESCRIPTION},
        "tags": [
            {"name": "ask", "description": "Synchronous question answering"},
            {"name": "tasks", "description": "Asynchronous skill tasks"},
            {"name": "feedback", "description": "Feedback signals for the controlled improvement loop"},
            {"name": "admin", "description": "Administrative operations (admin role)"},
        ],
        "security": [{BEARER_SCHEME: []}],
        "paths": _paths(),
        "components": {
            "schemas": schemas,
            "responses": _error_responses(),
            "parameters": {
                IDEMPOTENCY_PARAMETER: {
                    "name": IDEMPOTENCY_KEY_HEADER,
                    "in": "header",
                    "required": False,
                    "description": IDEMPOTENCY_DESCRIPTION,
                    "schema": {"type": "string", "minLength": 1},
                },
                TASK_ID_PARAMETER: {
                    "name": "task_id",
                    "in": "path",
                    "required": True,
                    "description": "Task identifier returned by `POST /v1/tasks`.",
                    "schema": {"type": "string", "minLength": 1},
                },
                TRACE_ID_PARAMETER: {
                    "name": "trace_id",
                    "in": "path",
                    "required": True,
                    "description": "Trace identifier (32 lowercase hex characters) of a previous request.",
                    "schema": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
                },
            },
            "securitySchemes": {
                BEARER_SCHEME: {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "OIDC-compatible token (ADR-0001, INV-AUTH-01): the server verifies issuer, audience, "
                    "expiry and signature; department and scopes are mapped server-side from `sub`, never taken "
                    "from the request.",
                },
            },
        },
    }
