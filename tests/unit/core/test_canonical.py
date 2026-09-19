import math

import pytest

from medops.core.canonical import canonical_hash, canonical_json, operation_key, sha256_hex


def test_canonical_json_sorts_keys_and_is_compact():
    assert (
        canonical_json({"b": 1, "a": {"z": None, "y": [1, 2.5, "中文"]}}) == '{"a":{"y":[1,2.5,"中文"],"z":null},"b":1}'
    )


def test_canonical_json_is_deterministic_across_insertion_order():
    assert canonical_json({"x": 1, "y": 2}) == canonical_json({"y": 2, "x": 1})


def test_canonical_json_rejects_nan_and_sets():
    with pytest.raises(ValueError):
        canonical_json({"v": math.nan})
    with pytest.raises(TypeError):
        canonical_json({"v": {1, 2}})


def test_operation_key_has_no_delimiter_ambiguity():
    payload = {
        "policy_version": "p1",
        "retrieval_version": "r1",
        "skill_version_set": ["s1"],
        "model_config_version": "m1",
        "input": {"q": "x"},
    }
    assert operation_key("ask", "trace-ab", "cnode", payload) != operation_key("ask", "trace-a", "bcnode", payload)
    with pytest.raises(ValueError):
        operation_key("ask", "trace\x1fid", "node", payload)


def test_operation_key_changes_with_any_version_or_run_id():
    base = {
        "policy_version": "p1",
        "retrieval_version": "r1",
        "skill_version_set": [],
        "model_config_version": "m1",
        "input": {"q": "x"},
    }
    key = operation_key("ask", "trace-1", "retrieve", base)
    assert key == operation_key("ask", "trace-1", "retrieve", dict(base))
    assert key != operation_key("ask", "replay-1", "retrieve", base)
    assert key != operation_key("ask", "trace-1", "retrieve", {**base, "retrieval_version": "r2"})
    assert len(key) == 64 and canonical_hash(base) == sha256_hex(canonical_json(base))
