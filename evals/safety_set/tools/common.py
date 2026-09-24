"""Shared helpers for the safety-set tooling (spec-s1 v0.2): paths, ids, canaries, DSNs, class table."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import urllib.parse
from collections.abc import Iterable

REPO = pathlib.Path(__file__).resolve().parents[3]
SAFETY = REPO / "evals/safety_set"
DRAFTS = SAFETY / "drafts"
SCHEMA = SAFETY / "schema/safety_sample.schema.json"
SYNTHETIC_DIR = SAFETY / "synthetic"  # gitignored DOCX sources
INJECTION_PLAN = SAFETY / "injection_plan.json"
CORPUS_SAFETY = SAFETY / "corpus_safety.json"
PRODUCTION_DB = "medops_v2"
SAFETY_DB = "medops_v2_safety"
DATASET_VERSION = "safety-v1-provisional"
DRAFTER = {"kind": "llm", "id": "drafter-safety-01", "model": "claude-fable-5-1"}
CANARY_RE = re.compile(r"SAFETY-CANARY-[0-9a-f]{8}")

# category code -> (minimum, expected outcome family) per SPEC §2
CATEGORIES: dict[str, int] = {
    "high_risk": 30,
    "injection_input": 20,
    "injection_document": 20,
    "acl_cross_dept": 30,
    "acl_skill_scope": 10,
    "ungrounded": 20,
    "numeric_trap": 10,
    "combined": 20,
    "version_guard": 10,
}
DRAFT_FILES = {
    "high_risk": "samples_draft_A_high_risk.jsonl",
    "injection_input": "samples_draft_B1_injection_input.jsonl",
    "injection_document": "samples_draft_B2_injection_document.jsonl",
    "acl_cross_dept": "samples_draft_C1_acl_cross_dept.jsonl",
    "acl_skill_scope": "samples_draft_C2_acl_skill_scope.jsonl",
    "ungrounded": "samples_draft_D1_ungrounded.jsonl",
    "numeric_trap": "samples_draft_D2_numeric_trap.jsonl",
    "combined": "samples_draft_E_combined.jsonl",
    "version_guard": "samples_draft_F_version_guard.jsonl",
}
MIN_PER_LANGUAGE = 30
MIN_PER_DEPT = 40
TOTAL_MIN = 170


def canary_for(sample_id: str) -> str:
    """Deterministic, unique per sample id (PR-S1 checks uniqueness over the whole set)."""
    return "SAFETY-CANARY-" + hashlib.sha256(f"safety-v1:{sample_id}".encode()).hexdigest()[:8]


def _env() -> dict[str, str | None]:
    from dotenv import dotenv_values

    return dotenv_values(REPO / ".env")


def with_database(dsn: str, database: str) -> str:
    return re.sub(r"/[^/?]+(\?|$)", rf"/{database}\1", dsn)


def admin_dsn(database: str) -> str:
    return with_database(_env()["DATABASE_ADMIN_URL"] or "", database)


def app_dsn(database: str) -> str:
    """The application LOGIN user (RLS enforced), as the harness uses it."""
    env = _env()
    dsn = env["DATABASE_URL"] or ""
    p = urllib.parse.urlsplit(dsn)
    user = urllib.parse.quote("medops_app_user")
    pw = urllib.parse.quote(env["DB_APP_PASSWORD"] or "")
    return f"postgresql://{user}:{pw}@{p.hostname}:{p.port or 5432}/{database}"


def read_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: pathlib.Path, rows: Iterable[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def load_drafts() -> list[dict]:
    rows: list[dict] = []
    for name in DRAFT_FILES.values():
        rows.extend(read_jsonl(DRAFTS / name))
    return rows
