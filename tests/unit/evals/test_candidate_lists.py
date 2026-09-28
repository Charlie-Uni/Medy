"""DEC-011 candidate lists must match candidate.schema.json and keep contiguous ids across versions."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parents[3]
PROBE = REPO / "evals" / "probe" / "precise_clause"
SCHEMA = json.loads((PROBE / "schema" / "candidate.schema.json").read_text(encoding="utf-8"))
LISTS = sorted((PROBE / "corpus_candidates").glob("DEC-011-candidates-v*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_schema_is_valid() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    assert LISTS, "no candidate list files found"


@pytest.mark.parametrize("path", LISTS, ids=[p.name for p in LISTS])
def test_candidate_list_matches_schema(path: Path) -> None:
    data = _load(path)
    errors = sorted(
        Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path)
    )
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)
    assert path.stem == f"DEC-011-candidates-{data['candidate_list_version']}"
    ids = [c["candidate_id"] for c in data["candidates"]]
    assert ids == [f"cand-{i:04d}" for i in range(1, len(ids) + 1)], "candidate ids must be contiguous from cand-0001"


def _identity(candidate: dict) -> str:
    """What must stay stable for an id across versions: the document it points at (titles may be corrected)."""
    return candidate["pdf_url"] or candidate["landing_url"]


def test_later_versions_keep_earlier_ids() -> None:
    """A new version appends; an id from an earlier version keeps pointing at the same document (no renumbering)."""
    previous: dict[str, str] = {}
    for path in LISTS:
        current = {c["candidate_id"]: _identity(c) for c in _load(path)["candidates"]}
        for cid, identity in previous.items():
            assert current.get(cid) == identity, f"{path.name} changed or dropped {cid}"
        previous = current
