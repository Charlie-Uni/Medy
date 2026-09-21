"""Derive the main-set (spec-m1) JSON Schemas from the frozen probe schemas so that every probe rule that still
applies is inherited verbatim and only the spec-m1 differences are expressed here.

    python evals/main_set/tools/make_schemas.py   # rewrites evals/main_set/schema/*.schema.json

Differences (SPEC.md sections 2, 3, 4): sample ids `ms-` (imported probe samples keep `pc-`), three new slices
(`version_conflict`, `no_answer`, `long_context`), `answerable=false` samples with an `abstention` block and no
gold, `conflict` blocks, per-sample `drafted_by`, dataset versions `main-v<N>[-provisional]`, new minimums and
gates, a `NA` review batch, `imported_samples` (the merged probe v2) and the `second_human_review` status that
forces `-provisional` while pending.
"""

from __future__ import annotations

import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO / "evals/probe/precise_clause/schema"
DST = REPO / "evals/main_set/schema"
ID_PATTERN = "^(pc|ms)-[0-9]{4}$"
GOLD_PATTERN = "^(pc|ms)-[0-9]{4}-g[0-9]{1,2}$"
VERSION_PATTERN = "^main-v[0-9]+(\\.[0-9]+)?(-provisional)?$"
SLICES = ["drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en"]
NEW_SLICES = ["version_conflict", "no_answer", "long_context"]
BATCHES = ["MA", "PV", "CO", "EN", "NA"]


def load(name: str) -> dict:
    return json.loads((SRC / f"{name}.schema.json").read_text(encoding="utf-8"))


def dump(name: str, schema: dict) -> None:
    schema["$id"] = f"https://medy.local/evals/main_set/{name}.schema.json"
    (DST / f"{name}.schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sample_schema() -> dict:
    s = load("probe_sample")
    s["title"] = "MainSetSample"
    p = s["properties"]
    p["sample_id"]["pattern"] = ID_PATTERN
    p["derived_from"]["pattern"] = ID_PATTERN
    p["slices"]["items"]["enum"] = SLICES + NEW_SLICES
    p["slices"]["maxItems"] = 8
    p["required_gold_evidence"]["minItems"] = 0
    s["$defs"]["goldEvidence"]["properties"]["gold_id"]["pattern"] = GOLD_PATTERN
    p["answerable"] = {
        "type": "boolean",
        "description": "spec-m1: false for no-answer samples (gold empty); absent means true",
    }
    p["expected_behaviour"] = {"enum": ["cite_evidence", "insufficient_evidence", "refuse"]}
    p["abstention"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scope_document_key", "topic", "absence_check"],
        "properties": {
            "scope_document_key": {"type": "string", "minLength": 1, "maxLength": 120},
            "topic": {"type": "string", "minLength": 2, "maxLength": 200},
            "absence_check": {"type": "string", "minLength": 5, "maxLength": 800},
            "document_pages": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "integer", "minimum": 1},
                "description": "pages of the scope document packed for the LLM reviewer (reconstructed by PR-09)",
            },
        },
    }
    p["conflict"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["family_document_keys", "current_document_key", "clause_topic", "synthetic"],
        "properties": {
            "family_document_keys": {
                "type": "array",
                "minItems": 2,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "current_document_key": {"type": "string", "minLength": 1},
            "clause_topic": {"type": "string", "minLength": 2, "maxLength": 200},
            "synthetic": {"type": "boolean"},
        },
    }
    p["drafted_by"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "id"],
        "properties": {
            "kind": {"enum": ["human", "llm"]},
            "id": {"type": "string", "minLength": 1, "maxLength": 64},
            "model": {"type": "string", "minLength": 1},
        },
    }
    s["allOf"].extend(
        [
            {
                "if": {"properties": {"answerable": {"const": False}}, "required": ["answerable"]},
                "then": {
                    "required": ["expected_behaviour", "abstention"],
                    "properties": {
                        "required_gold_evidence": {"maxItems": 0},
                        "expected_behaviour": {"enum": ["insufficient_evidence", "refuse"]},
                        "slices": {"contains": {"const": "no_answer"}},
                    },
                    "not": {"required": ["derived_from"]},
                },
                "else": {
                    "properties": {
                        "required_gold_evidence": {"minItems": 1},
                        "slices": {"not": {"contains": {"const": "no_answer"}}},
                    },
                    "not": {"required": ["abstention"]},
                },
                "$comment": "spec-m1 §3: no-answer samples carry no gold and no twins; answerable samples carry at least one gold",
            },
            {
                "if": {"properties": {"slices": {"contains": {"const": "version_conflict"}}}},
                "then": {"required": ["conflict"]},
                "else": {"not": {"required": ["conflict"]}},
                "$comment": "spec-m1 §3: the conflict block and the version_conflict slice imply each other",
            },
        ]
    )
    return s


def manifest_schema() -> dict:
    m = load("manifest")
    m["title"] = "MainSetManifest"
    p = m["properties"]
    p["dataset_id"] = {"const": "precise_clause_main"}
    p["dataset_version"]["pattern"] = VERSION_PATTERN
    p["spec_version"] = {"enum": ["spec-m1"]}
    p["supersedes"]["oneOf"][0]["pattern"] = "^(v|main-v)[0-9]+(\\.[0-9]+)?(-provisional)?$"
    p["minimums"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "answerable_samples",
            "no_answer_samples",
            "conflict_samples",
            "per_slice",
            "per_dept",
            "max_samples_per_document",
            "documents",
            "documents_per_dept",
            "zh_hans_samples",
            "zh_hant_samples",
            "en_samples",
        ],
        "properties": {
            "answerable_samples": {"const": 300},
            "no_answer_samples": {"const": 40},
            "conflict_samples": {"const": 20},
            "per_slice": {"const": 20},
            "per_dept": {"const": 60},
            "max_samples_per_document": {"const": 8},
            "documents": {"const": 10},
            "documents_per_dept": {"const": 3},
            "zh_hans_samples": {"const": 20},
            "zh_hant_samples": {"const": 80},
            "en_samples": {"const": 150},
        },
    }
    p["gates"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "recall_at_5",
            "abstention_accuracy",
            "invalid_version_citation_rate",
            "conflict_current_cited_rate",
        ],
        "properties": {
            "recall_at_5": {"const": 0.85},
            "abstention_accuracy": {"const": 0.9},
            "invalid_version_citation_rate": {"const": 0.0},
            "conflict_current_cited_rate": {"const": 1.0},
        },
    }
    counts = p["counts"]
    counts["required"] = [
        "samples",
        "answerable",
        "no_answer",
        "conflict",
        "derived",
        "imported",
        "documents",
        "per_slice",
        "per_dept",
        "per_language",
    ]
    for k in ("answerable", "no_answer", "conflict", "derived", "imported"):
        counts["properties"][k] = {"type": "integer", "minimum": 0}
    ps = counts["properties"]["per_slice"]
    ps["required"] = SLICES + NEW_SLICES
    for k in NEW_SLICES:
        ps["properties"][k] = {"type": "integer", "minimum": 0}
    prov = m["$defs"]["reviewProvenance"]["properties"]["artifacts"]
    prov["items"]["properties"]["path"]["enum"] = (
        [f"review_evidence/run_{b}.json" for b in BATCHES]
        + [f"review_evidence/verdicts_{b}.jsonl" for b in BATCHES]
        + ["review_evidence/resolutions.json", "review_evidence/reviewer_runtime_metadata.json"]
    )
    prov["minItems"] = 12
    prov["maxItems"] = 12
    p["imported_samples"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "dataset_id",
            "dataset_version",
            "dataset_hash",
            "path",
            "samples_sha256",
            "count",
            "prompt_hash",
            "reviewer_id",
            "statement",
        ],
        "properties": {
            "dataset_id": {"const": "precise_clause_probe"},
            "dataset_version": {"type": "string", "pattern": "^v[0-9]+(\\.[0-9]+)?$"},
            "dataset_hash": {"$ref": "#/$defs/sha256"},
            "path": {"type": "string", "pattern": "^evals/probe/precise_clause/v[0-9]+(\\.[0-9]+)?/samples\\.jsonl$"},
            "samples_sha256": {"$ref": "#/$defs/sha256"},
            "count": {"type": "integer", "minimum": 1},
            "prompt_hash": {"$ref": "#/$defs/sha256"},
            "reviewer_id": {"type": "string", "minLength": 1},
            "statement": {"type": "string", "minLength": 20, "maxLength": 600},
        },
        "description": "spec-m1 §2: the frozen probe samples merged verbatim (their review blocks keep the probe review prompt hash)",
    }
    p["second_human_review"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "reviewer_id", "statement"],
        "properties": {
            "status": {"enum": ["pending", "complete"]},
            "reviewer_id": {"type": ["string", "null"], "minLength": 1, "maxLength": 64},
            "statement": {"type": "string", "minLength": 20, "maxLength": 600},
        },
    }
    p["conflict_fixtures"] = {
        "type": "array",
        "uniqueItems": True,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["document_key", "archived_document_keys", "synthetic", "source"],
            "properties": {
                "document_key": {"type": "string", "minLength": 1},
                "archived_document_keys": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "synthetic": {"type": "boolean"},
                "source": {"type": "string", "minLength": 5, "maxLength": 300},
            },
        },
        "description": "spec-m1 §5: families with an archived version available to version_conflict samples",
    }
    p["dropped_after_review"] = {
        "type": "object",
        "propertyNames": {"pattern": "^ms-[0-9]{4}$"},
        "additionalProperties": {"type": "string", "minLength": 5, "maxLength": 500},
        "description": "spec-m1: samples removed after their LLM review (their run evidence stays; PR-09 tolerates the ids)",
    }
    m["required"] = m["required"] + ["gates", "imported_samples", "second_human_review", "conflict_fixtures"]
    m["allOf"].append(
        {
            "if": {"properties": {"second_human_review": {"properties": {"status": {"const": "pending"}}}}},
            "then": {"properties": {"dataset_version": {"pattern": "-provisional$"}}},
            "$comment": "spec-m1 §4 item 4: without the second human review the set can only run as main-v<N>-provisional",
        }
    )
    return m


def patched(name: str) -> dict:
    """Same schema with the sample-id, gold-id and dataset-version patterns widened (object-level, no text edits)."""
    s = load(name)

    def walk(node):
        if isinstance(node, dict):
            if node.get("pattern") == "^pc-[0-9]{4}$":
                node["pattern"] = ID_PATTERN
            elif node.get("pattern") == "^pc-[0-9]{4}-g[0-9]{1,2}$":
                node["pattern"] = GOLD_PATTERN
            elif node.get("pattern") == "^v[0-9]+(\\.[0-9]+)?$":
                node["pattern"] = VERSION_PATTERN
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)
    return s


def main() -> None:
    DST.mkdir(exist_ok=True)
    dump("probe_sample", sample_schema())
    dump("manifest", manifest_schema())
    for name in ("pii_exceptions", "chunk_mapping", "acl_probe"):
        dump(name, patched(name))
    for name in ("corpus", "candidate"):
        dump(name, load(name))
    from jsonschema import Draft202012Validator

    for path in sorted(DST.glob("*.schema.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
        print("ok", path.relative_to(REPO))


if __name__ == "__main__":
    main()
