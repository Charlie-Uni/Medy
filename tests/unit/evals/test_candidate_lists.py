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


def test_later_versions_keep_earlier_ids() -> None:
    """A new version appends; ids from an earlier version keep the same title (renumbering would break references)."""
    previous: dict[str, str] = {}
    for path in LISTS:
        current = {c["candidate_id"]: c["title"] for c in _load(path)["candidates"]}
        for cid, title in previous.items():
            assert current.get(cid) == title, f"{path.name} changed or dropped {cid}"
        previous = current
