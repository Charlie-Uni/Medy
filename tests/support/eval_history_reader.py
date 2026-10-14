"""Public synthetic sample records matching existing main/probe schemas."""

import hashlib
import json
import time
from pathlib import Path

from medops.evals.isolation.history import HistoryPlan, HistoryRequirement, history_plan_digest
from medops.evals.isolation.history_reader import HistoryReadLimits, history_limits_digest, scan_sample_file
from tests.support.eval_isolation import GOLD_CANARY, uid


def sample(number=1, prefix="ms"):
    sample_id = f"{prefix}-{number:04d}"
    return {
        "sample_id": sample_id,
        "query": "PUBLIC SYNTHETIC QUESTION",
        "dept": "PV",
        "language": "zh",
        "slices": ["protocol_id"],
        "required_gold_evidence": [
            {
                "gold_id": sample_id + "-g1",
                "source_hash": "a" * 64,
                "version_label": "PUBLIC v1",
                "page": 1,
                "printed_page_label": None,
                "section": "PUBLIC SYNTHETIC SECTION",
                "key_text": GOLD_CANARY,
                "evidence_span": {"text": GOLD_CANARY, "char_start": 0, "char_end": len(GOLD_CANARY)},
            }
        ],
        "review": {
            "annotator": {"kind": "human", "id": "PUBLIC FAKE HUMAN"},
            "second_reviewer": {
                "kind": "llm",
                "id": "PUBLIC FAKE MODEL",
                "model": "PUBLIC FAKE MODEL",
                "model_version": "PUBLIC v1",
                "prompt_hash": "b" * 64,
            },
            "status": "agreed",
            "resolution_note": None,
        },
        "notes": "PUBLIC IGNORED NOTES",
    }


def wire(*rows):
    return b"".join(json.dumps(row, ensure_ascii=False).encode() + b"\n" for row in rows)


def arguments(raw, **changes):
    schema = (Path(__file__).resolve().parents[2] / "evals/main_set/schema/probe_sample.schema.json").read_bytes()
    limits = HistoryReadLimits(
        max_file_bytes=1048576, max_line_bytes=65536, max_records=1000, max_projected_chars=1000000
    )
    requirement = HistoryRequirement(
        artifact_id=uid(1),
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        adapter="dataset-fields-v1",
        required_levels=("query", "gold", "source"),
    )
    plan = HistoryPlan(scope_id=uid(2), requirements=(requirement,))
    return dict(
        plan=plan,
        artifact_id=uid(1),
        expected_plan_sha256=history_plan_digest(plan),
        schema_bytes=schema,
        expected_schema_sha256=hashlib.sha256(schema).hexdigest(),
        limits=limits,
        expected_limits_sha256=history_limits_digest(limits),
        cancelled=lambda: False,
        deadline=time.monotonic() + 30,
        **changes,
    )


def scan(tmp_path, raw, options=None):
    path = tmp_path / "public-synthetic.jsonl"
    path.write_bytes(raw)
    path.chmod(0o600)
    with path.open("rb") as stream:
        return scan_sample_file(stream.fileno(), **(options or arguments(raw)))
