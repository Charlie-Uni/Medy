"""Preflight evidence is written before a run; unknown or failed health never authorizes measurement."""

import json

import pytest

from medops.core.canonical import sha256_hex
from medops.evals.preflight import save_preflight
from medops.retrieval import integrity
from medops.retrieval.production import IndexCoverageError


def test_resumes_preserve_every_preflight_snapshot(tmp_path):
    planes = {"fixture": {"ready": True, "database_identity": "db", "coverage": {"active_chunks": 1}}}
    first, second = save_preflight(tmp_path, planes), save_preflight(tmp_path, planes)
    assert first["path"] != second["path"]
    for reference in (first, second):
        data = (tmp_path / reference["path"]).read_bytes()
        assert sha256_hex(data) == reference["sha256"]
        assert json.loads(data)["planes"] == planes


@pytest.mark.parametrize("planes", [{}, {"x": {}}, {"x": {"ready": False}}, {"x": {"ready": "true"}}])
def test_failed_or_unknown_health_cannot_create_a_run_snapshot(tmp_path, planes):
    with pytest.raises(ValueError, match="successful"):
        save_preflight(tmp_path, planes)
    assert not list(tmp_path.iterdir())


def test_mismatched_database_refuses_even_when_admin_indexes_are_complete(monkeypatch):
    monkeypatch.setattr(
        integrity,
        "inspect_retrieval",
        lambda *args, **kwargs: {"ready": True, "problems": [], "database_identity": "admin"},
    )
    monkeypatch.setattr(integrity, "database_identity", lambda *args: "request")
    with pytest.raises(IndexCoverageError, match="request_and_admin_database_mismatch"):
        integrity.require_retrieval_integrity(object(), plane="test", request_conn=object())
