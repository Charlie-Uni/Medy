"""Migration 0017 + the Loop pipeline on real roles (M4-02 / 03 / 05): Reflect attributes open cases through the Loop
user, a human corrects one on the admin user, knowledge-gap cases become document tickets the Loop cannot handle,
Adapt writes an isolation-checked candidate the Loop cannot release, and once an approver releases it the app role's
loader applies it (policy version, retrieval overlay)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from medops.application.policy_loader import load_released
from medops.infrastructure.db.policies import PgPolicyStore
from medops.loop.adapt import Candidate, IsolationError, propose, replay_queries, submit
from medops.loop.observe import PgCaseStore, PgSignalSource, observe
from medops.loop.reflect import correct, reflect
from medops.loop.tickets import open_tickets
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.production import production_hybrid_config

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
PRINCIPAL = "b" * 32
APPROVER = "c" * 32


def _trace(
    conn,
    trace_id: str,
    *,
    dept: str = "MA",
    outcome: str = "answered",
    codes=(),
    evidence=(),
    flagged=(),
    query: str = "q",
) -> None:
    conn.execute(
        "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, reason_codes, versions, "
        "evidence_chunk_ids, cited_chunk_ids, flagged_chunk_ids, model_calls, tokens, cost_usd, duration_ms) "
        "values (%s, %s, 'ask', %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 10, 0.001, 100)",
        (
            trace_id,
            trace_id,
            PRINCIPAL,
            dept,
            query,
            outcome,
            list(codes),
            Jsonb({"policy_version": "p"}),
            list(evidence),
            [],
            list(flagged),
        ),
    )


def _escalation(conn, trace_id: str, codes, dept: str, detail: str = "d") -> None:
    conn.execute(
        "insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, evidence_chunk_ids, "
        "verify_result, safety_result, policy_version, detail, status) values (%s, %s, %s, %s, %s, 'q', '{}', null, null, 'p', %s, 'open')",
        (trace_id, trace_id, PRINCIPAL, dept, list(codes), detail),
    )


@pytest.fixture(scope="module")
def pipeline(migrated, login_users):
    ids = {k: uuid.uuid4().hex for k in ("gap1", "gap2", "ret1", "ret2", "ret3", "gen", "safe")}
    with psycopg.connect(migrated) as conn:
        for k in ("gap1", "gap2"):
            _trace(
                conn,
                ids[k],
                dept="PV",
                outcome="escalated",
                codes=("insufficient_evidence",),
                query=f"question {k} about a missing guideline",
            )
            _escalation(conn, ids[k], ("insufficient_evidence",), "PV")
        for k in ("ret1", "ret2", "ret3"):
            _trace(
                conn,
                ids[k],
                dept="MA",
                outcome="escalated",
                codes=("insufficient_evidence",),
                evidence=("c1", "c2", "c3"),
            )
            _escalation(conn, ids[k], ("insufficient_evidence",), "MA")
        _trace(conn, ids["gen"], dept="CO", outcome="escalated", codes=("unsupported_conclusion",), evidence=("c9",))
        _escalation(
            conn,
            ids["gen"],
            ("unsupported_conclusion",),
            "CO",
            detail="no claim survives verification (forged=0, dropped=1)",
        )
        _trace(
            conn,
            ids["safe"],
            dept="MA",
            outcome="escalated",
            codes=("prompt_injection",),
            evidence=("c5",),
            flagged=("c5",),
        )
        _escalation(conn, ids["safe"], ("prompt_injection",), "MA")
        conn.commit()
    users = {k: v["dsn"] for k, v in login_users.items()}
    with psycopg.connect(users["loop"]) as loop:
        observe(PgSignalSource(loop), PgCaseStore(loop), since=T0 - timedelta(days=1), now=T0)
        loop.commit()
    return {"ids": ids, "users": users}


def test_reflect_attributes_open_cases_and_a_human_can_override(pipeline):
    ids = pipeline["ids"]
    with psycopg.connect(pipeline["users"]["loop"]) as loop:
        report = reflect(loop)
        loop.commit()
        rows = {
            r[0]: r[1:]
            for r in loop.execute(
                "select trace_id, attribution, confidence, attributed_by, status from bad_cases where trace_id = any(%s)",
                (list(ids.values()),),
            ).fetchall()
        }
    assert report.attributed >= 7 and report.left_open == 0
    assert (
        rows[ids["gap1"]][0] == "knowledge_gap"
        and rows[ids["ret1"]][0] == "retrieval"
        and rows[ids["gen"]][0] == "generation"
        and rows[ids["safe"]][0] == "safety"
    )
    assert all(r[2] == "rules" and r[3] == "attributed" and r[1] is not None for r in rows.values())
    with psycopg.connect(pipeline["users"]["admin"]) as admin:
        case_id = admin.execute("select case_id::text from bad_cases where trace_id = %s", (ids["ret3"],)).fetchone()[0]
        assert correct(
            admin,
            case_id=case_id,
            attribution="knowledge_gap",
            by="reviewer-01",
            note="the MA corpus has no such label",
        )
        admin.commit()
    with psycopg.connect(pipeline["users"]["loop"]) as loop:
        status, override = loop.execute(
            "select status, human_override from bad_cases where case_id = %s::uuid", (case_id,)
        ).fetchone()
        assert status == "corrected" and override["attribution"] == "knowledge_gap" and override["by"] == "reviewer-01"
        assert reflect(loop).scanned == 0  # nothing left open


def test_tickets_open_once_for_knowledge_gaps_and_only_humans_handle_them(pipeline):
    ids = pipeline["ids"]
    with psycopg.connect(pipeline["users"]["loop"]) as loop:
        report = open_tickets(loop)
        loop.commit()
        tickets = loop.execute(
            "select c.trace_id, d.topic, d.gap, d.status from document_requests d join bad_cases c using (case_id)"
        ).fetchall()
        assert open_tickets(loop).opened == 0
    assert report.opened == 3  # gap1, gap2 by rule, ret3 by the human override
    by_trace = {t[0]: t for t in tickets}
    assert set(by_trace) >= {ids["gap1"], ids["gap2"], ids["ret3"]}
    assert by_trace[ids["gap1"]][1].startswith("question gap1") and by_trace[ids["gap1"]][2].startswith(
        "knowledge gap (PV)"
    )
    assert by_trace[ids["ret3"]][2].endswith("the MA corpus has no such label")
    with psycopg.connect(pipeline["users"]["loop"]) as loop:
        with pytest.raises((pg_errors.InsufficientPrivilege,)):
            loop.execute(
                "update document_requests set status = 'accepted' where case_id = (select case_id from bad_cases where trace_id = %s)",
                (ids["gap1"],),
            )
        loop.rollback()
    with psycopg.connect(pipeline["users"]["admin"]) as admin:
        admin.execute(
            "update document_requests set status = 'rejected', handled_by = %s, handled_at = now(), note = 'out of scope' where case_id = (select case_id from bad_cases where trace_id = %s)",
            (APPROVER, ids["gap2"]),
        )
        admin.commit()
        with pytest.raises(pg_errors.RestrictViolation):  # closed stays closed; content immutable
            admin.execute(
                "update document_requests set status = 'open' where case_id = (select case_id from bad_cases where trace_id = %s)",
                (ids["gap2"],),
            )
        admin.rollback()
        with pytest.raises(pg_errors.RestrictViolation):
            admin.execute(
                "update document_requests set topic = 'edited' where case_id = (select case_id from bad_cases where trace_id = %s)",
                (ids["gap1"],),
            )
        admin.rollback()
    with psycopg.connect(pipeline["users"]["app"]) as app:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            app.execute("select count(*) from document_requests")


def test_adapt_proposes_submits_an_isolated_candidate_and_only_a_release_makes_the_app_apply_it(pipeline):
    ids = pipeline["ids"]
    base = production_hybrid_config()
    with psycopg.connect(pipeline["users"]["loop"]) as loop:
        rows = [
            {"case_id": r[0], "dept": r[1], "attribution": r[2], "human_override": r[3]}
            for r in loop.execute(
                "select case_id::text, dept::text, attribution, human_override from bad_cases where trace_id = any(%s)",
                (list(ids.values()),),
            ).fetchall()
        ]
        proposals = {(p.attribution, p.dept): p for p in propose(rows, current=base, min_support=2)}
        assert ("retrieval", "MA") in proposals and proposals[("retrieval", "MA")].needs_author  # k already at the cap
        assert ("knowledge_gap", "PV") in proposals and proposals[("knowledge_gap", "PV")].suggested_kind is None
        case_ids = list(proposals[("retrieval", "MA")].case_ids)
        candidate = Candidate(
            kind="retrieval_params",
            name="hybrid",
            diff={"rrf_k": {"from": base.rrf_k, "to": 40.0}},
            evidence={"case_ids": case_ids},
            created_by="loop:adapt-v1",
        )
        policy_id = submit(loop, candidate, current=base, forbidden_queries=replay_queries())
        loop.commit()
        with pytest.raises(IsolationError):
            submit(
                loop,
                Candidate(
                    kind="prompt",
                    name="answer_system",
                    diff={"text": "see rp-0001"},
                    evidence={"case_ids": case_ids},
                    created_by="loop",
                ),
                current=base,
                forbidden_queries=replay_queries(),
            )
        loop.rollback()
        with pytest.raises(pg_errors.InsufficientPrivilege):  # the Loop cannot release what it proposed
            loop.execute("update policies set status = 'released' where policy_id = %s::uuid", (policy_id,))
        loop.rollback()
    with psycopg.connect(pipeline["users"]["app"]) as app:
        assert not load_released(app).retrieval_overridden()
    with psycopg.connect(pipeline["users"]["admin"]) as admin:
        store = PgPolicyStore(admin)
        row = store.get(policy_id)
        assert (
            row is not None and row["status"] == "candidate" and row["evidence"]["adapt"]["isolation_check"] == "passed"
        )
        assert store.decide(
            policy_id, status="approved", decided_by=APPROVER, reason="replay report pending; test", at=T0
        )
        admin.execute(
            "update policies set evidence = evidence || %s where policy_id = %s::uuid",
            (Jsonb({"gate": {"passed": True}}), policy_id),
        )
        store.release(
            policy_id, kind="retrieval_params", name="hybrid", canary_percent=10, actor=APPROVER, reason="drill"
        )
        admin.commit()
    with psycopg.connect(pipeline["users"]["app"]) as app:
        released = load_released(app)
        cfg = released.hybrid_config(base)
        assert released.retrieval_overridden() and cfg == HybridConfig(
            k_lexical=base.k_lexical, k_vector=base.k_vector, rrf_k=40.0, limit=base.limit
        )
        assert released.policy_version("policy-m3-api-1") == "policy-m3-api-1+rel:" + policy_id.replace("-", "")[:8]
    with psycopg.connect(pipeline["users"]["admin"]) as admin:
        PgPolicyStore(admin).rollback(
            policy_id, kind="retrieval_params", name="hybrid", actor=APPROVER, reason="end of drill"
        )
        admin.commit()
    with psycopg.connect(pipeline["users"]["app"]) as app:
        assert not load_released(app).retrieval_overridden()
