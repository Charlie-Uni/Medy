import json
from pathlib import Path

import pytest

from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, UNIT_MAP_V1, UNIT_MAP_VERSION, normalize_text

VECTORS = Path(__file__).resolve().parents[3] / "evals" / "probe" / "precise_clause" / "tests" / "norm_v1_vectors.json"


def _cases():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data["normalization"] == NORMALIZATION_VERSION and data["unit_map_version"] == UNIT_MAP_VERSION
    assert data["unit_map"] == UNIT_MAP_V1
    return [pytest.param(c["input"], c["expected"], id=c["id"]) for c in data["cases"]]


@pytest.mark.parametrize("text,expected", _cases())
def test_norm_v1_vectors(text, expected):  # PR-14
    assert normalize_text(text) == expected


def test_norm_v1_is_idempotent():
    for text in ["每 次 0.5 g，每 日 2 次", "１０ ｍｇ", "1×10⁹/L", "２~８℃"]:
        once = normalize_text(text)
        assert normalize_text(once) == once
