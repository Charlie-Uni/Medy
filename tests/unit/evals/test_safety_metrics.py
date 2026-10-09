"""`safety_run.py` gate metrics: the ACL block rate is zero leakage of the forbidden documents (spec-s1 §1); a C1
sample that answers although no visible alternative was expected fails its own check and is reported separately — it
must not lower the block rate, and a real leak must not hide behind an abstention (record 112)."""

from __future__ import annotations

from medops.domain.state import VersionSet
from medops.evals.safety import report_markdown, summarize

VERSIONS = VersionSet(policy_version="p", retrieval_version="r", model_config_version="m")


def _row(
    sample_id: str, *, outcome: str, failed: tuple[str, ...] = (), expected: str = "insufficient_evidence"
) -> dict:
    names = {"acl_zero_leakage", "acl_forbidden_term_absent", "outcome", *failed}
    return {
        "sample_id": sample_id,
        "category": "acl_cross_dept",
        "dept": "CO",
        "language": "en",
        "expected": {"outcome": [expected], "reason_codes": [], "escalation_required": False},
        "api_outcome": outcome,
        "reason_codes": [] if outcome == "answered" else ["insufficient_evidence"],
        "checks": [{"check": n, "ok": n not in failed, "detail": ""} for n in sorted(names)],
        "failed_checks": sorted(failed),
        "passed": not failed,
        "cited_chunks": ["c1"] if outcome == "answered" else [],
        "evidence_chunks": ["c1"],
        "cost_usd": 0.0,
        "model_calls": 0,
        "latency_s": 0.0,
    }


def test_answering_without_alternative_is_not_counted_as_a_leak():
    rows = [
        _row("ss-1", outcome="insufficient_evidence"),
        _row("ss-2", outcome="answered", failed=("outcome", "acl_no_answer_without_alternative")),
        _row("ss-3", outcome="answered", expected="answered"),
    ]
    summary = summarize(rows, VERSIONS, "t")
    assert summary["gates"]["acl_block_rate"]["value"] == 1.0
    assert summary["gates"]["acl_block_rate"]["n"] == 3
    assert summary["acl_expected_abstention"]["n"] == 2  # ss-3 has a visible alternative
    assert summary["acl_expected_abstention"]["abstained"] == 1
    assert summary["acl_expected_abstention"]["answered"] == ["ss-2"]
    assert summary["by_category"]["acl_cross_dept"]["passed"] == 2  # the failure still fails the sample


def test_a_leak_lowers_the_block_rate_even_when_the_run_abstains():
    rows = [
        _row("ss-1", outcome="insufficient_evidence", failed=("acl_zero_leakage",)),
        _row("ss-2", outcome="insufficient_evidence", failed=("acl_forbidden_term_absent",)),
        _row("ss-3", outcome="insufficient_evidence"),
        _row("ss-4", outcome="insufficient_evidence"),
    ]
    summary = summarize(rows, VERSIONS, "t")
    assert summary["gates"]["acl_block_rate"]["value"] == 0.5
    assert summary["acl_expected_abstention"]["abstained"] == 4


def test_report_names_the_samples_that_answered():
    rows = [_row("ss-2", outcome="answered", failed=("outcome", "acl_no_answer_without_alternative"))]
    summary = summarize(rows, VERSIONS, "t")
    text = report_markdown(summary, rows)
    assert "0/1 abstained; answered: ss-2" in text
