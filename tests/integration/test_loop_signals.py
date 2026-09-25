"""Migration 0016 (M4-01): `trace_signals` joins feedback, escalation, verifier, safety and replay signals to their
trace; the Loop LOGIN user reads it, opens and attributes cases, and can neither touch released policy nor write a
human override; the admin user corrects cases and records escalation resolutions; the app user sees neither."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from medops.loop.observe import PgCaseStore, PgSignalSource, observe

T0 = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
PRINCIPAL = "a" * 32


def _trace(
    conn, trace_id: str, *, kind: str = "ask", dept: str = "MA", outcome: str = "answered", codes=(), flagged=()
) -> None:
    conn.execute(
        "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, reason_codes, versions, "
        "evidence_chunk_ids, cited_chunk_ids, flagged_chunk_ids, model_calls, tokens, cost_usd, duration_ms) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 10, 0.001, 100)",
        (
            trace_id,
            trace_id,
            kind,
            PRINCIPAL,
            dept,
            "q",
            outcome,
            list(codes),
            Jsonb({"policy_version": "p"}),
            [],
            [],
            list(flagged),
        ),
    )


def _feedback(conn, trace_id: str, signal: str, text: str | None = None) -> None:
    conn.execute(
        "insert into feedback (feedback_id, trace_id, principal, signal, correction_text) values (%s, %s, %s, %s, %s)",
        (uuid.uuid4(), trace_id, PRINCIPAL, signal, text),
    )


def _escalation(conn, trace_id: str, codes, dept: str = "PV", verify=None) -> None:
    conn.execute(
        "insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, evidence_chunk_ids, "
        "verify_result, safety_result, policy_version, detail, status) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')",
        (trace_id, trace_id, PRINCIPAL, dept, list(codes), "q", [], Jsonb(verify) if verify else None, None, "p", "d"),
    )


@pytest.fixture(scope="module")
def seeded(migrated, login_users):
    ids = {
        k: uuid.uuid4().hex
        for k in ("up", "down", "esc", "drift", "plain", "task", "sysfail", "safety", "replay_trace")
    }
    with psycopg.connect(migrated) as conn:
        _trace(conn, ids["up"])
        _feedback(conn, ids["up"], "up")
        _trace(conn, ids["down"])
        _feedback(conn, ids["down"], "down")
        _feedback(conn, ids["down"], "correction", "the dose is 8 mg")
        _feedback(conn, ids["down"], "up")
        _trace(conn, ids["esc"], dept="PV", outcome="escalated", codes=("insufficient_evidence",))
        _escalation(conn, ids["esc"], ("insufficient_evidence",))
        _trace(conn, ids["drift"])
        _trace(conn, ids["replay_trace"], kind="replay")
        conn.execute(
            "insert into replays (replay_id, source_trace_id, replay_trace_id, replay_run_id, requested_by, reason, versions_match, changed, report) "
            "values (%s, %s, %s, %s, %s, 'drift check', true, %s, %s)",
            (uuid.uuid4(), ids["drift"], ids["replay_trace"], ids["replay_trace"], PRINCIPAL, ["outcome"], Jsonb({})),
        )
        _trace(conn, ids["plain"])
        _trace(conn, ids["task"], kind="task", outcome="completed")
        _feedback(conn, ids["task"], "down")
        _trace(conn, ids["sysfail"], outcome="escalated", codes=("system_failure",))
        _escalation(conn, ids["sysfail"], ("system_failure",), dept="MA")
        _trace(conn, ids["safety"], outcome="escalated", codes=("prompt_injection",), flagged=("c1",))
        _escalation(conn, ids["safety"], ("prompt_injection",), dept="MA")
        conn.commit()
    return {"ids": ids, "users": {k: v["dsn"] for k, v in login_users.items()}}


def test_view_joins_every_signal_source_for_the_loop_user(seeded):
    ids = seeded["ids"]
    with psycopg.connect(seeded["users"]["loop"]) as loop:
        src = PgSignalSource(loop)
        rows = {r.trace_id: r for r in src.since(T0 - timedelta(days=1))}
    assert set(ids.values()) <= set(rows)
    down = rows[ids["down"]]
    assert (down.feedback_up, down.feedback_down, down.feedback_corrections) == (1, 1, 1)
    esc = rows[ids["esc"]]
    assert (
        esc.escalation_status == "open"
        and esc.escalation_reason_codes == ("insufficient_evidence",)
        and esc.dept == "PV"
    )
    assert rows[ids["drift"]].replay_count == 1 and rows[ids["drift"]].replay_changed is True
    assert rows[ids["safety"]].safety_flagged is True and rows[ids["plain"]].safety_flagged is False
    assert rows[ids["up"]].verifier_failed is False


def test_observe_opens_cases_once_and_the_loop_user_attributes_but_never_overrides(seeded):
    ids = seeded["ids"]
    with psycopg.connect(seeded["users"]["loop"]) as loop:
        report = observe(PgSignalSource(loop), PgCaseStore(loop), since=T0 - timedelta(days=1), now=T0)
        loop.commit()
        opened = {c["trace_id"]: c for c in PgCaseStore(loop).list(limit=500)}
    assert report.opened >= 6 and report.by_label.get("good", 0) >= 1
    assert {ids["up"], ids["down"], ids["esc"], ids["drift"], ids["task"], ids["safety"]} <= set(opened)
    assert ids["plain"] not in opened and ids["sysfail"] not in opened and ids["replay_trace"] not in opened
    assert opened[ids["up"]]["label"] == "good" and opened[ids["down"]]["reasons"] == [
        "feedback_down",
        "feedback_correction",
    ]
    with psycopg.connect(seeded["users"]["loop"]) as loop:
        again = observe(PgSignalSource(loop), PgCaseStore(loop), since=T0 - timedelta(days=1), now=T0)
        assert again.opened == 0 and again.already_open >= 6
        loop.execute(
            "update bad_cases set attribution = 'retrieval', confidence = 0.8, attributed_by = 'model', status = 'attributed' where trace_id = %s",
            (ids["esc"],),
        )
        loop.commit()
        with pytest.raises(pg_errors.InsufficientPrivilege):  # a human override is not the Loop's to write
            loop.execute(
                "update bad_cases set human_override = %s where trace_id = %s",
                (Jsonb({"attribution": "intent"}), ids["esc"]),
            )
        loop.rollback()
        with pytest.raises(pg_errors.RestrictViolation):  # the label and the opening signals are immutable
            loop.execute("update bad_cases set label = 'good' where trace_id = %s", (ids["esc"],))
        loop.rollback()
        with pytest.raises(
            (pg_errors.InsufficientPrivilege, pg_errors.RestrictViolation)
        ):  # no delete grant; the guard would refuse too
            loop.execute("delete from bad_cases where trace_id = %s", (ids["esc"],))
        loop.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "delete from traces",  # select only
        "update escalations set resolution = 'false_alarm'",  # resolutions are a human's (admin role)
        "delete from released_policies",  # never the Loop's (INV-AUTH-05)
        "update policies set status = 'released'",  # candidates in, decisions by humans
        "delete from feedback",
    ],
)
def test_loop_user_has_no_write_path_outside_cases_and_candidates(seeded, statement):
    with psycopg.connect(seeded["users"]["loop"]) as loop:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            loop.execute(statement)


def test_admin_corrects_cases_and_records_escalation_resolutions_and_the_app_sees_nothing(seeded):
    ids = seeded["ids"]
    with psycopg.connect(seeded["users"]["admin"]) as admin:
        admin.execute(
            "update bad_cases set human_override = %s, status = 'corrected' where trace_id = %s",
            (Jsonb({"attribution": "knowledge_gap", "by": "reviewer-1"}), ids["esc"]),
        )
        admin.execute(
            "update escalations set resolution = 'false_alarm', status = 'closed', handled_by = %s, handled_at = now() where trace_id = %s",
            (PRINCIPAL, ids["esc"]),
        )
        admin.commit()
        with pytest.raises(pg_errors.RestrictViolation):  # the 0011 guard still protects the escalation content
            admin.execute("update escalations set detail = 'edited' where trace_id = %s", (ids["esc"],))
        admin.rollback()
    with psycopg.connect(seeded["users"]["loop"]) as loop:
        row = PgSignalSource(loop).for_trace(ids["esc"])
        assert row is not None and row.escalation_resolution == "false_alarm" and row.escalation_status == "closed"
        case = next(c for c in PgCaseStore(loop).list(limit=500) if c["trace_id"] == ids["esc"])
        assert case["status"] == "corrected"
    with psycopg.connect(seeded["users"]["app"]) as app:
        for sql in ("select count(*) from bad_cases", "select count(*) from trace_signals"):
            with pytest.raises(pg_errors.InsufficientPrivilege):
                app.execute(sql)
            app.rollback()
