"""Restricted material failures never become unaudited successful tool output."""

import pytest

from medops.application.search import SearchExecution
from medops.core.errors import InfrastructureError
from medops.mcp import audit
from tests.unit.harness._fixtures import user


def material(*, outcome="answered", stats=None, snapshot=None):
    return audit.tool_payloads(
        tool="search_documents",
        input_body={"query": "synthetic"},
        user=user(),
        versions={},
        snapshot=snapshot,
        stats=stats or SearchExecution(()),
        outcome=outcome,
        result={"hits": []} if outcome == "answered" else None,
        error_type=None if outcome == "answered" else "InfrastructureError",
        reason_codes=() if outcome == "answered" else ("audit_unavailable",),
    )


def test_model_journal_incomplete_is_failure_but_bounded_failure_prefix_and_receipts_remain():
    stats = SearchExecution(
        (),
        model_calls=1,
        cost_usd=0.01,
        call_audit_complete=False,
        call_records=({"request": {"model_id": "synthetic"}},),
        call_receipts=({"call_id": "synthetic", "cost_usd": 0.01},),
    )
    with pytest.raises(InfrastructureError):
        material(stats=stats)
    result = material(stats=stats, outcome="escalated")
    assert result["model_output"]["model_call_audit_complete"] is False
    assert result["model_output"]["call_receipts"] == list(stats.call_receipts)
    assert result["model_output"]["model_calls"] == list(stats.call_records)


def test_material_capacity_refuses_success_and_failure_keeps_only_bounded_hash_and_accounting(monkeypatch):
    monkeypatch.setattr(audit, "MAX_BYTES", 2500)
    stats = SearchExecution((), call_receipts=({"call_id": "synthetic", "cost_usd": 0.01},))
    snapshot = {"synthetic_body": "private synthetic" * 400}
    with pytest.raises(InfrastructureError):
        material(stats=stats, snapshot=snapshot)
    result = material(stats=stats, snapshot=snapshot, outcome="escalated")
    assert result["input"]["input_audit_complete"] is False and "input" not in result["input"]
    assert result["model_output"]["material_capacity_exceeded"] is True
    assert result["model_output"]["call_receipts"] == list(stats.call_receipts)
    assert "private synthetic" not in str(result)


def test_oversized_failure_receipt_is_hashed_instead_of_bypassing_the_material_cap(monkeypatch):
    import json

    monkeypatch.setattr(audit, "MAX_BYTES", 2500)
    stats = SearchExecution((), call_receipts=({"response_id": "synthetic" * 1000},))
    result = material(stats=stats, outcome="escalated")
    assert len(json.dumps(result).encode()) <= audit.MAX_BYTES
    assert result["model_output"]["call_receipts_included"] is False
    assert result["model_output"]["call_receipts"] == []
    assert len(result["model_output"]["call_receipts_sha256"]) == 64
