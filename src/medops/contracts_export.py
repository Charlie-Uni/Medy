"""Export JSON Schemas for the API and MCP contracts (M0-08).

    python -m medops.contracts_export --out schemas

Files are deterministic (sorted keys, stable indentation) so a test can detect drift between the
generated schemas and the models. Cross-field rules that JSON Schema can express are emitted via the
models' `json_schema_extra`; rules needing server state stay server-side. `openapi.json` is the OpenAPI
3.1 document built from the same API models by `medops.api.openapi` (no web framework involved).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from medops.api import contracts as api
from medops.api.openapi import build_openapi
from medops.core.errors import ErrorResponse
from medops.mcp import contracts as mcp

API_MODELS: dict[str, type[BaseModel]] = {
    "AskRequest": api.AskRequest,
    "AskResponse": api.AskResponse,
    "TaskCreateRequest": api.TaskCreateRequest,
    "TaskResult": api.TaskResult,
    "TaskResponse": api.TaskResponse,
    "FeedbackRequest": api.FeedbackRequest,
    "FeedbackReceipt": api.FeedbackReceipt,
    "ReplayRequest": api.ReplayRequest,
    "ReplayReport": api.ReplayReport,
    "DocumentListResponse": api.DocumentListResponse,
    "DocumentDetail": api.DocumentDetail,
    "DocumentStatusRequest": api.DocumentStatusRequest,
    "DocumentAclRequest": api.DocumentAclRequest,
    "DocumentAclResponse": api.DocumentAclResponse,
    "PolicyListResponse": api.PolicyListResponse,
    "PolicyResponse": api.PolicyResponse,
    "PolicyDecisionRequest": api.PolicyDecisionRequest,
    "PolicyReleaseRequest": api.PolicyReleaseRequest,
    "PolicyRollbackRequest": api.PolicyRollbackRequest,
    "ErrorResponse": ErrorResponse,
}
MCP_MODELS: dict[str, type[BaseModel]] = {
    "SearchDocumentsInput": mcp.SearchDocumentsInput,
    "SearchDocumentsOutput": mcp.SearchDocumentsOutput,
    "GetChunkInput": mcp.GetChunkInput,
    "ChunkView": mcp.ChunkView,
    "VerifyCitationInput": mcp.VerifyCitationInput,
    "VerifyCitationOutput": mcp.VerifyCitationOutput,
    "ListActiveVersionsInput": mcp.ListActiveVersionsInput,
    "ListActiveVersionsOutput": mcp.ListActiveVersionsOutput,
}


def render() -> dict[str, str]:
    """Return {relative path: file content} for every schema file."""
    files: dict[str, str] = {}
    for folder, models in (("api", API_MODELS), ("mcp", MCP_MODELS)):
        for name, model in models.items():
            files[f"{folder}/{name}.schema.json"] = (
                json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
    tools = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": f"mcp/{t.input_model}.schema.json",
            "output_schema": f"mcp/{t.output_model}.schema.json",
            "read_only": t.read_only,
        }
        for t in mcp.MCP_TOOLS
    ]
    files["mcp/tools.json"] = (
        json.dumps(
            {
                "_note": "Local descriptor for M3-06; not an MCP tools/list response. The server maps input_schema/output_schema to the protocol's inputSchema/outputSchema; read_only is documentation, database roles enforce read-only access.",
                "transport": "streamable-http",
                "auth": "bearer (OIDC)",
                "tools": tools,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    files["openapi.json"] = json.dumps(build_openapi(API_MODELS), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return files


def write(out: Path) -> list[Path]:
    written = []
    for rel, content in render().items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medops.contracts_export")
    parser.add_argument("--out", type=Path, default=Path("schemas"))
    parser.add_argument("--check", action="store_true", help="exit 1 if committed files differ from the models")
    args = parser.parse_args(argv)
    if args.check:
        stale = [
            rel
            for rel, content in render().items()
            if not (args.out / rel).is_file() or (args.out / rel).read_text(encoding="utf-8") != content
        ]
        print("schemas up to date" if not stale else f"stale schema files: {stale}")
        return 1 if stale else 0
    for path in write(args.out):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
