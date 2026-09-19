"""OpenAPI 3.1 document (M0-08): valid, built from the same models as the standalone schemas, and
faithful to the contract table in docs/api/CONTRACTS.md."""

import json
from pathlib import Path
from typing import Any

import pytest
from openapi_spec_validator import validate as validate_openapi

from medops.api.contracts import IDEMPOTENCY_KEY_HEADER
from medops.api.openapi import BEARER_SCHEME, IDEMPOTENCY_PARAMETER, OPENAPI_VERSION, build_openapi
from medops.contracts_export import API_MODELS, render
from medops.core.errors import HTTP_STATUS

REPO = Path(__file__).resolve().parents[3]

# (path, method) -> (request model, success status, response model); mirrors the REST table in CONTRACTS.md
EXPECTED_OPERATIONS = {
    ("/v1/ask", "post"): ("AskRequest", "200", "AskResponse"),
    ("/v1/tasks", "post"): ("TaskCreateRequest", "202", "TaskResponse"),
    ("/v1/tasks/{task_id}", "get"): (None, "200", "TaskResponse"),
    ("/v1/tasks/{task_id}/retry", "post"): (None, "202", "TaskResponse"),
    ("/v1/feedback", "post"): ("FeedbackRequest", "201", "FeedbackReceipt"),
}
IDEMPOTENT_OPERATIONS = {("/v1/tasks", "post"), ("/v1/feedback", "post")}
HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    return build_openapi(API_MODELS)


def _operations(doc: dict[str, Any]):
    for path, item in doc["paths"].items():
        for method in HTTP_METHODS:
            if method in item:
                yield path, method, item[method]


def _refs(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _refs(value)


def _resolve(doc: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/"), ref
    node: Any = doc
    for part in ref[2:].split("/"):
        assert part in node, f"unresolvable $ref {ref}"
        node = node[part]
    return node


def test_document_is_valid_openapi_3_1(doc):
    assert doc["openapi"] == OPENAPI_VERSION == "3.1.0"
    validate_openapi(doc)  # raises on any structural violation of the OAS 3.1 schema


def test_every_ref_resolves_inside_components_and_no_local_defs_remain(doc):
    refs = set(_refs(doc))
    assert refs, "document has no references"
    for ref in refs:
        assert ref.startswith("#/components/"), ref
        _resolve(doc, ref)
    assert "$defs" not in json.dumps(doc), "component schemas must not nest their own $defs"


def test_operations_match_the_contract_table(doc):
    seen = {}
    operation_ids = []
    for path, method, op in _operations(doc):
        operation_ids.append(op["operationId"])
        success = [s for s in op["responses"] if s.startswith("2")]
        assert len(success) == 1, f"{method} {path} must have exactly one success status, got {success}"
        body = op.get("requestBody")
        request_model = None
        if body is not None:
            assert body["required"] is True
            request_model = body["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
        response_model = op["responses"][success[0]]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
        seen[(path, method)] = (request_model, success[0], response_model)
    assert seen == EXPECTED_OPERATIONS
    assert len(operation_ids) == len(set(operation_ids)), "operationIds must be unique"
    for path in doc["paths"]:
        if "{task_id}" in path:
            assert {"$ref": "#/components/parameters/TaskId"} in doc["paths"][path]["parameters"]


def test_error_responses_are_derived_from_the_http_status_mapping(doc):
    statuses = sorted(set(HTTP_STATUS.values()))
    responses = doc["components"]["responses"]
    assert sorted(responses) == [f"Error{s}" for s in statuses]
    for status in statuses:
        response = responses[f"Error{status}"]
        assert response["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
        for code, mapped in HTTP_STATUS.items():
            assert (f"`{code.value}`" in response["description"]) == (mapped == status), (status, code)
    for path, method, op in _operations(doc):
        for status in statuses:
            assert op["responses"].get(str(status)) == {"$ref": f"#/components/responses/Error{status}"}, (
                path,
                method,
                status,
            )
    error_schema = doc["components"]["schemas"]["ErrorResponse"]
    assert set(error_schema["properties"]) == {"code", "message", "trace_id", "retryable"}
    assert error_schema["additionalProperties"] is False


def test_idempotency_key_header_only_on_task_creation_and_feedback(doc):
    parameter = doc["components"]["parameters"][IDEMPOTENCY_PARAMETER]
    assert (
        parameter["name"] == IDEMPOTENCY_KEY_HEADER and parameter["in"] == "header" and parameter["required"] is False
    )
    for needle in ("422", "idempotency_payload_mismatch", "never 409", "one transaction", "86400", "604800"):
        assert needle in parameter["description"], needle
    with_header = set()
    for path, method, op in _operations(doc):
        params = [_resolve(doc, p["$ref"]) if "$ref" in p else p for p in op.get("parameters", [])]
        if any(p["name"] == IDEMPOTENCY_KEY_HEADER for p in params):
            with_header.add((path, method))
            assert "422" in op["responses"] and IDEMPOTENCY_KEY_HEADER in op["description"]
    assert with_header == IDEMPOTENT_OPERATIONS


def test_bearer_security_is_global_and_request_bodies_carry_no_identity(doc):
    scheme = doc["components"]["securitySchemes"][BEARER_SCHEME]
    assert scheme["type"] == "http" and scheme["scheme"] == "bearer"
    assert doc["security"] == [{BEARER_SCHEME: []}]
    for path, method, op in _operations(doc):
        assert "security" not in op, f"{method} {path} must not override the global security requirement"
        body = op.get("requestBody")
        if body is None:
            continue
        top = _resolve(doc, body["content"]["application/json"]["schema"]["$ref"])
        assert top["additionalProperties"] is False, (path, method)
        names, todo, done = set(), [top], set()
        while todo:  # every property name reachable from the request body through component refs
            node = todo.pop()
            names.update(node.get("properties", {}))
            for ref in set(_refs(node)):
                if ref not in done:
                    done.add(ref)
                    todo.append(_resolve(doc, ref))
        assert names.isdisjoint({"dept", "scopes", "user_id", "sub"}), (path, method, names)


def test_component_schemas_equal_the_standalone_schema_files_and_export_is_current(doc):
    for name in API_MODELS:
        standalone = json.loads((REPO / "schemas" / "api" / f"{name}.schema.json").read_text(encoding="utf-8"))
        standalone.pop("$defs", None)
        rewritten = json.loads(json.dumps(standalone).replace("#/$defs/", "#/components/schemas/"))
        assert rewritten == doc["components"]["schemas"][name], name
    exported = json.loads((REPO / "schemas" / "openapi.json").read_text(encoding="utf-8"))
    assert exported == doc
    assert render()["openapi.json"] == json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
