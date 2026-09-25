"""Reflect (M4-02, record 80): attribute an open Loop case to one of five classes, with a confidence and the facts used.

The first pass is deterministic (record 74 C: reuse the reason codes and the retrieval facts) so every attribution is
explainable and free; a model-based pass may follow and a human always may override. Classes (baseline 5.8):

| class          | what the rules take as evidence                                                                 |
| -------------- | ----------------------------------------------------------------------------------------------- |
| safety         | the safety layer flagged evidence or refused for injection / ACL reasons                        |
| intent         | `intent_unclear`, or a high-risk refusal that a user voted down (over-refusal suspected)         |
| generation     | a verifier failure, a false-alarm escalation, replay drift, or a user disagreement with an answer |
| knowledge_gap  | an evidence-based escalation with nothing retrieved, or one a human confirmed as a real gap      |
| retrieval      | an evidence-based escalation although candidates were retrieved (ranking / recall suspected)    |

Confidence is a fixed number per rule (calibrated only by the rule's specificity), never a model probability. The
human override (`bad_cases.human_override`, admin role) wins over any rule; `effective_attribution` applies it.

    python -m medops.loop.reflect run [--dry-run]                       (DATABASE_LOOP_URL)
    python -m medops.loop.reflect correct --case <id> --attribution <class> --by <pseudonym> [--note ...]
                                                                          (DATABASE_ADMIN_URL: a human decision)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

CLASSES = ("retrieval", "intent", "generation", "knowledge_gap", "safety")


@dataclass(frozen=True)
class CaseFacts:
    case_id: str
    trace_id: str
    dept: str
    label: str
    reasons: tuple[str, ...]
    outcome: str
    reason_codes: tuple[str, ...]
    evidence_count: int
    cited_count: int
    flagged_count: int
    escalation_status: str | None = None
    escalation_resolution: str | None = None
    escalation_detail: str = ""
    feedback_down: int = 0
    feedback_corrections: int = 0
    replay_changed: bool = False


@dataclass(frozen=True)
class Attribution:
    attribution: str
    confidence: float
    note: str


def attribute(f: CaseFacts) -> Attribution | None:
    """The rule table; first matching rule wins. None = no rule applies (the case stays open for a human)."""
    codes = set(f.reason_codes)
    if "safety_flagged" in f.reasons or codes & {"prompt_injection", "acl_denied"}:
        return Attribution("safety", 0.9, f"safety layer: flagged={f.flagged_count}, codes={sorted(codes)}")
    if "intent_unclear" in codes:
        return Attribution("intent", 0.8, "intent node could not classify the question")
    if f.outcome == "refused" and "high_risk_medical" in codes and f.feedback_down:
        return Attribution("intent", 0.6, f"high-risk refusal voted down {f.feedback_down}x: over-refusal suspected")
    if f.escalation_resolution == "false_alarm":
        return Attribution("generation", 0.7, "human ruled the escalation a false alarm: over-strict verification")
    if "verifier_failed" in f.reasons or "unsupported_conclusion" in codes:
        return Attribution(
            "generation", 0.7, f"verifier rejected the answer: {f.escalation_detail[:160] or 'unsupported_conclusion'}"
        )
    if f.escalation_resolution == "confirmed_issue" and "insufficient_evidence" in codes:
        return Attribution("knowledge_gap", 0.8, "human confirmed the corpus does not answer the question")
    if "insufficient_evidence" in codes:
        if f.evidence_count == 0:
            return Attribution(
                "knowledge_gap", 0.7, "nothing retrieved for the question in the department-visible corpus"
            )
        return Attribution(
            "retrieval",
            0.5,
            f"{f.evidence_count} evidence fragments retrieved but none answered: ranking / recall suspected",
        )
    if f.replay_changed:
        return Attribution(
            "generation", 0.5, "replay under the same versions changed the outcome: non-deterministic generation"
        )
    if f.feedback_corrections or f.feedback_down:
        return Attribution(
            "generation",
            0.4,
            f"user disagreement (down={f.feedback_down}, corrections={f.feedback_corrections}) without a system signal",
        )
    return None


def effective_attribution(case: dict[str, Any]) -> str | None:
    override = case.get("human_override") or {}
    if isinstance(override, dict) and override.get("attribution") in CLASSES:
        return str(override["attribution"])
    return case.get("attribution")


def override_payload(*, attribution: str, by: str, note: str | None, at: datetime | None = None) -> dict[str, Any]:
    if attribution not in CLASSES:
        raise ValueError(f"attribution must be one of {CLASSES}")
    if not by or len(by) > 64:
        raise ValueError("`by` must be a pseudonym of at most 64 characters")
    return {
        "attribution": attribution,
        "by": by,
        "note": (note or "")[:500],
        "at": (at or datetime.now(UTC)).isoformat(),
    }


# ------------------------------------------------------------------------------------------ PostgreSQL

_FACTS_SQL = """
select c.case_id::text, c.trace_id, c.dept::text, c.label, c.reasons, s.outcome, s.reason_codes,
       cardinality(s.evidence_chunk_ids), cardinality(s.cited_chunk_ids), cardinality(s.flagged_chunk_ids),
       s.escalation_status, s.escalation_resolution, coalesce(e.detail, ''), s.feedback_down, s.feedback_corrections,
       s.replay_changed
  from bad_cases c
  join trace_signals s on s.trace_id = c.trace_id
  left join escalations e on e.escalation_id = s.escalation_id
 where c.status = 'open' and c.label = 'bad'
 order by c.opened_at, c.case_id
"""


def _facts(r: Any) -> CaseFacts:
    return CaseFacts(
        case_id=r[0],
        trace_id=r[1],
        dept=r[2],
        label=r[3],
        reasons=tuple(r[4] or ()),
        outcome=r[5],
        reason_codes=tuple(r[6] or ()),
        evidence_count=int(r[7] or 0),
        cited_count=int(r[8] or 0),
        flagged_count=int(r[9] or 0),
        escalation_status=r[10],
        escalation_resolution=r[11],
        escalation_detail=r[12] or "",
        feedback_down=int(r[13] or 0),
        feedback_corrections=int(r[14] or 0),
        replay_changed=bool(r[15]),
    )


@dataclass
class ReflectReport:
    scanned: int = 0
    attributed: int = 0
    left_open: int = 0
    by_class: dict[str, int] | None = None


def reflect(conn: Any, *, attributed_by: str = "rules") -> ReflectReport:
    report = ReflectReport(by_class={})
    for row in conn.execute(_FACTS_SQL).fetchall():
        facts = _facts(row)
        report.scanned += 1
        result = attribute(facts)
        if result is None:
            report.left_open += 1
            continue
        conn.execute(
            "update bad_cases set attribution = %s, confidence = %s, attributed_by = %s, attribution_note = %s, status = 'attributed' "
            "where case_id = %s::uuid and status = 'open'",
            (result.attribution, result.confidence, attributed_by, result.note[:500], facts.case_id),
        )
        report.attributed += 1
        assert report.by_class is not None
        report.by_class[result.attribution] = report.by_class.get(result.attribution, 0) + 1
    return report


def correct(conn: Any, *, case_id: str, attribution: str, by: str, note: str | None) -> bool:
    """A human decision on the admin connection: the override wins over any rule and closes the attribution."""
    from psycopg.types.json import Jsonb

    payload = override_payload(attribution=attribution, by=by, note=note)
    cur = conn.execute(
        "update bad_cases set human_override = %s, status = 'corrected' where case_id = %s::uuid",
        (Jsonb(payload), case_id),
    )
    return cur.rowcount == 1


# ------------------------------------------------------------------------------------------ CLI


def _connect(url: str, settings: Any) -> Any:
    import psycopg

    return psycopg.connect(
        url,
        connect_timeout=settings.db_connect_timeout_s,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    )


def main(argv: list[str] | None = None) -> int:
    from medops.core.config import Settings

    ap = argparse.ArgumentParser(description="Reflect: attribute open Loop cases (rules) or record a human override")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--dry-run", action="store_true")
    fix = sub.add_parser("correct")
    fix.add_argument("--case", required=True)
    fix.add_argument("--attribution", required=True, choices=CLASSES)
    fix.add_argument("--by", required=True, help="reviewer pseudonym (never a name)")
    fix.add_argument("--note", default=None)
    args = ap.parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    if args.cmd == "run":
        if settings.database_loop_url is None:
            print("DATABASE_LOOP_URL is not configured", file=sys.stderr)
            return 2
        with _connect(settings.database_loop_url.get_secret_value(), settings) as conn, conn.transaction():
            report = reflect(conn)
            if args.dry_run:
                conn.rollback()
        print(json.dumps(asdict(report), ensure_ascii=False))
        return 0
    if settings.database_admin_url is None:
        print("DATABASE_ADMIN_URL is not configured (a correction is a human, admin-role action)", file=sys.stderr)
        return 2
    with _connect(settings.database_admin_url.get_secret_value(), settings) as conn, conn.transaction():
        ok = correct(conn, case_id=args.case, attribution=args.attribution, by=args.by, note=args.note)
    print(json.dumps({"corrected": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
