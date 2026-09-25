"""Observe (M4-01): the labelling table, idempotent case opening, and the report."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from medops.loop.observe import (
    InMemoryCaseStore,
    StaticSignalSource,
    TraceSignals,
    classify,
    observe,
    snapshot,
)

T0 = datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


def sig(**kw) -> TraceSignals:
    base = {
        "trace_id": kw.pop("trace_id", "t1"),
        "kind": "ask",
        "dept": "MA",
        "outcome": "answered",
        "reason_codes": (),
        "created_at": T0,
    }
    base.update(kw)
    return TraceSignals(**base)


@pytest.mark.parametrize(
    ("signals", "label", "reasons"),
    [
        (sig(), None, ()),  # answered, nobody reacted: not a case
        (sig(feedback_up=2), "good", ("feedback_up",)),
        (sig(feedback_down=1, feedback_up=3), "bad", ("feedback_down",)),  # one down vote outweighs up votes
        (sig(feedback_corrections=1), "bad", ("feedback_correction",)),
        (
            sig(outcome="escalated", reason_codes=("unsupported_conclusion",), verifier_failed=True),
            "bad",
            ("verifier_failed",),
        ),
        (sig(safety_flagged=True), "bad", ("safety_flagged",)),
        (
            sig(outcome="escalated", escalation_status="open", escalation_reason_codes=("insufficient_evidence",)),
            "bad",
            ("escalated_insufficient_evidence",),
        ),
        (sig(outcome="escalated", escalation_status="open", escalation_reason_codes=("system_failure",)), None, ()),
        (sig(outcome="refused", escalation_status="open", escalation_reason_codes=("high_risk_medical",)), None, ()),
        (
            sig(
                outcome="escalated",
                escalation_status="closed",
                escalation_reason_codes=("insufficient_evidence",),
                escalation_resolution="confirmed_issue",
            ),
            "bad",
            ("escalation_confirmed_issue",),
        ),
        (
            sig(
                outcome="escalated",
                escalation_status="closed",
                escalation_reason_codes=("unsupported_conclusion",),
                escalation_resolution="false_alarm",
            ),
            "bad",
            ("escalation_false_alarm",),
        ),
        (sig(replay_count=1, replay_changed=True), "bad", ("replay_drift",)),
        (sig(replay_count=2, replay_changed=False, feedback_up=1), "good", ("feedback_up",)),
        (sig(kind="task", feedback_down=1), "bad", ("feedback_down",)),
        (
            sig(
                kind="task",
                outcome="escalated",
                escalation_status="open",
                escalation_reason_codes=("insufficient_evidence",),
            ),
            None,
            (),
        ),
        (sig(kind="replay", feedback_down=1), None, ()),  # diagnostics never open cases
        (sig(kind="mcp", safety_flagged=True), None, ()),
    ],
)
def test_labelling_table(signals, label, reasons):
    assert classify(signals) == (label, reasons)


def test_several_negative_signals_are_all_kept_as_reasons():
    label, reasons = classify(sig(feedback_down=1, verifier_failed=True, safety_flagged=True, replay_changed=True))
    assert label == "bad" and reasons == ("feedback_down", "verifier_failed", "safety_flagged", "replay_drift")


def test_observe_opens_each_case_once_and_reports():
    rows = [
        sig(trace_id="a", feedback_down=1),
        sig(trace_id="b", feedback_up=1),
        sig(trace_id="c"),
        sig(trace_id="d", kind="replay", feedback_down=1),
        sig(trace_id="e", created_at=datetime(2026, 9, 24, tzinfo=UTC), feedback_down=1),  # before the window
        sig(trace_id="f", dept="PV", verifier_failed=True),
    ]
    store = InMemoryCaseStore()
    report = observe(StaticSignalSource(rows), store, since=T0, now=T0)
    assert (report.scanned, report.opened, report.already_open, report.skipped_no_signal, report.skipped_kind) == (
        5,
        3,
        0,
        1,
        1,
    )
    assert report.by_label == {"bad": 2, "good": 1} and report.by_reason == {
        "feedback_down": 1,
        "feedback_up": 1,
        "verifier_failed": 1,
    }
    assert set(store.cases) == {"a", "b", "f"} and store.cases["a"].signals == snapshot(rows[0])
    again = observe(StaticSignalSource(rows), store, since=T0, now=T0)
    assert again.opened == 0 and again.already_open == 3
    only_pv = observe(StaticSignalSource(rows), InMemoryCaseStore(), since=T0, dept="PV", now=T0)
    assert only_pv.scanned == 1 and only_pv.opened == 1


def test_snapshot_is_json_friendly_and_complete():
    s = snapshot(sig(reason_codes=("insufficient_evidence",), escalation_reason_codes=("insufficient_evidence",)))
    assert s["created_at"] == T0.isoformat() and s["reason_codes"] == ["insufficient_evidence"]
    assert set(s) >= {
        "trace_id",
        "kind",
        "dept",
        "outcome",
        "feedback_down",
        "verifier_failed",
        "safety_flagged",
        "replay_changed",
    }
