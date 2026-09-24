"""Mechanical checks over the safety-set drafts (spec-s1 v0.2 §2 quotas, §3 schema, §8 PR-S1…PR-S6).

    python evals/safety_set/tools/check_safety.py [--no-db] [--json out.json]

Exit 1 when any rule fails. PR-S3 / PR-S4 need the databases (admin DSN from .env); --no-db skips them.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

import jsonschema

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CATEGORIES,
    CORPUS_SAFETY,
    MIN_PER_DEPT,
    MIN_PER_LANGUAGE,
    PRODUCTION_DB,
    SAFETY_DB,
    SCHEMA,
    TOTAL_MIN,
    admin_dsn,
    load_drafts,
)

CANARY = re.compile(r"SAFETY-CANARY-[0-9a-f]{8}")
NO_CITE = {"high_risk", "injection_input", "ungrounded"}


def check(rows: list[dict], *, use_db: bool, partial: bool = False) -> tuple[list[str], dict]:
    problems: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    ids = collections.Counter(r.get("sample_id") for r in rows)
    for sid, n in ids.items():
        if n > 1:
            problems.append(f"duplicate sample_id {sid}")
    for r in rows:
        sid = r.get("sample_id", "?")
        for err in validator.iter_errors(r):
            problems.append(f"{sid}: schema {'/'.join(str(x) for x in err.path)}: {err.message[:140]}")
    # PR-S1 canaries unique, absent from non-injection queries
    canaries = collections.Counter(r["attack"]["canary"] for r in rows if r.get("attack"))
    for c, n in canaries.items():
        if n > 1:
            problems.append(f"PR-S1 canary {c} used {n} times")
    for r in rows:
        if not r.get("attack") and CANARY.search(r.get("query", "")):
            problems.append(f"PR-S1 {r['sample_id']}: canary in a non-injection query")
        if r.get("attack") and r["attack"]["vector"] == "user_input" and r["attack"]["canary"] not in r["query"]:
            problems.append(f"PR-S1 {r['sample_id']}: user_input canary not present in the query")
    # PR-S2 must_cite rules
    for r in rows:
        exp = r.get("expected", {})
        cites = exp.get("must_cite") or []
        if r.get("category") in NO_CITE and cites:
            problems.append(f"PR-S2 {r['sample_id']}: {r['category']} must not carry must_cite")
        if r.get("category") == "version_guard" and not cites:
            problems.append(f"PR-S2 {r['sample_id']}: version_guard needs must_cite")
        if r.get("category") == "numeric_trap" and "answered" in exp.get("outcome", []) and not cites:
            problems.append(f"PR-S2 {r['sample_id']}: numeric_trap with an answered path needs must_cite")
    # PR-S5 outcome / reason-code consistency
    for r in rows:
        exp = r.get("expected", {})
        outs, codes = set(exp.get("outcome", [])), set(exp.get("reason_codes", []))
        if outs == {"answered"} and codes:
            problems.append(f"PR-S5 {r['sample_id']}: answered-only expectation must have no reason codes")
        if outs - {"answered"} and not codes:
            problems.append(f"PR-S5 {r['sample_id']}: non-answered outcomes need reason codes")
        if "insufficient_evidence" in outs and "insufficient_evidence" not in codes:
            problems.append(f"PR-S5 {r['sample_id']}: insufficient_evidence outcome needs its reason code")
        if exp.get("high_risk_required") and "high_risk_medical" not in codes:
            problems.append(f"PR-S5 {r['sample_id']}: high_risk_required without the high_risk_medical code")
        if exp.get("escalation_required") and "answered" in outs:
            problems.append(f"PR-S5 {r['sample_id']}: escalation_required contradicts an answered outcome")
    # category-specific shape
    for r in rows:
        cat, exp, sid = r.get("category"), r.get("expected", {}), r.get("sample_id")
        if cat == "high_risk" and not (exp.get("high_risk_required") and exp.get("escalation_required")):
            problems.append(f"{sid}: high_risk needs high_risk_required + escalation_required")
        if cat == "injection_input" and r.get("attack", {}).get("vector") != "user_input":
            problems.append(f"{sid}: injection_input vector must be user_input")
        if cat == "injection_document":
            att = r.get("attack", {})
            if att.get("vector") != "document" or not att.get("document_key"):
                problems.append(f"{sid}: injection_document needs vector=document and document_key")
            if att.get("subtype") == "overt" and not (exp.get("must_flag_evidence") and exp.get("injected_not_cited")):
                problems.append(f"{sid}: overt injection_document needs must_flag_evidence and injected_not_cited")
            if r.get("database") != SAFETY_DB:
                problems.append(f"{sid}: injection_document must run against {SAFETY_DB}")
        if cat == "acl_skill_scope" and not exp.get("zero_retrieval_requests"):
            problems.append(f"{sid}: acl_skill_scope needs zero_retrieval_requests")
        if cat == "combined" and len(r.get("slices") or []) < 2:
            problems.append(f"{sid}: combined needs at least two component slices")
        if r.get("attack", {}).get("vector") == "document" and r.get("database") != SAFETY_DB:
            problems.append(f"{sid}: document-vector attacks must run against {SAFETY_DB}")
    # quotas
    counts = {
        "total": len(rows),
        "by_category": dict(collections.Counter(r.get("category") for r in rows)),
        "by_language": dict(collections.Counter(r.get("language") for r in rows)),
        "by_dept": dict(collections.Counter(r.get("dept") for r in rows)),
    }
    for cat, minimum in ({} if partial else CATEGORIES).items():
        if counts["by_category"].get(cat, 0) < minimum:
            problems.append(f"quota: {cat} has {counts['by_category'].get(cat, 0)} < {minimum}")
    for lang in () if partial else ("zh-Hant", "zh-Hans", "en"):
        if counts["by_language"].get(lang, 0) < MIN_PER_LANGUAGE:
            problems.append(f"quota: language {lang} has {counts['by_language'].get(lang, 0)} < {MIN_PER_LANGUAGE}")
    for dept in () if partial else ("MA", "PV", "CO"):
        if counts["by_dept"].get(dept, 0) < MIN_PER_DEPT:
            problems.append(f"quota: dept {dept} has {counts['by_dept'].get(dept, 0)} < {MIN_PER_DEPT}")
    if not partial and len(rows) < TOTAL_MIN:
        problems.append(f"quota: total {len(rows)} < {TOTAL_MIN}")
    if use_db:
        problems.extend(_db_checks(rows))
    return problems, counts


def _db_checks(rows: list[dict]) -> list[str]:
    import psycopg

    problems: list[str] = []
    with psycopg.connect(admin_dsn(PRODUCTION_DB)) as prod, psycopg.connect(admin_dsn(SAFETY_DB)) as safe:
        # PR-S3: forbidden documents exist, are active and are not readable by the requesting dept
        for r in rows:
            acl = r.get("acl")
            if not acl:
                continue
            for h in acl["forbidden_source_hashes"]:
                row = prod.execute(
                    """select d.document_key, d.status::text,
                              exists(select 1 from document_acl a where a.doc_id = d.doc_id and a.dept::text = %s and a.permission = 'read')
                       from documents d join source_objects so on so.source_object_id = d.source_object_id
                       where so.source_hash = %s""",
                    (r["dept"], h),
                ).fetchone()
                if row is None:
                    problems.append(f"PR-S3 {r['sample_id']}: source hash {h[:12]} not in {PRODUCTION_DB}")
                    continue
                key, status, readable = row
                if status != "active":
                    problems.append(f"PR-S3 {r['sample_id']}: forbidden document {key} is {status}, not active")
                if readable:
                    problems.append(f"PR-S3 {r['sample_id']}: {key} is readable by {r['dept']} (not a cross-dept case)")
                if key not in acl["forbidden_document_keys"]:
                    problems.append(
                        f"PR-S3 {r['sample_id']}: hash {h[:12]} belongs to {key}, not listed in forbidden_document_keys"
                    )
        # PR-S4: document-vector canaries live exactly once in the safety database and nowhere in production
        corpus = json.loads(CORPUS_SAFETY.read_text(encoding="utf-8")) if CORPUS_SAFETY.exists() else {"documents": []}
        for r in rows:
            att = r.get("attack")
            if not att or att["vector"] != "document":
                continue
            n_safe = safe.execute(
                "select count(*) from chunks where content like %s", (f"%{att['canary']}%",)
            ).fetchone()[0]
            n_prod = prod.execute(
                "select count(*) from chunks where content like %s", (f"%{att['canary']}%",)
            ).fetchone()[0]
            if n_safe != 1:
                problems.append(
                    f"PR-S4 {r['sample_id']}: canary {att['canary']} in {n_safe} safety chunks (expected 1)"
                )
            if n_prod:
                problems.append(f"PR-S4 {r['sample_id']}: canary {att['canary']} leaked into {PRODUCTION_DB}")
        # PR-S7: an ungrounded (D1) topic must not be answerable from the department's visible corpus — no chunk readable
        # by the dept carries a topic term together with one of the tempting facts
        for r in rows:
            if r.get("category") != "ungrounded":
                continue
            terms, facts = r.get("topic_terms") or [], r["expected"].get("must_not_contain") or []
            if not terms:
                problems.append(f"PR-S7 {r['sample_id']}: ungrounded sample without topic_terms")
                continue
            hits = prod.execute(
                """select d.document_key, count(*) from chunks c join documents d on d.doc_id = c.doc_id
                   join document_acl a on a.doc_id = d.doc_id and a.dept::text = %s and a.permission = 'read'
                   where d.status = 'active' and c.content ilike any(%s) and c.content ilike any(%s) group by 1""",
                (r["dept"], [f"%{t}%" for t in terms], [f"%{f}%" for f in facts if not f.startswith("re:")]),
            ).fetchall()
            if hits:
                problems.append(f"PR-S7 {r['sample_id']}: topic + fact co-occur in visible chunks {dict(hits)}")
        for d in corpus["documents"]:
            if prod.execute("select 1 from source_objects where source_hash = %s", (d["source_hash"],)).fetchone():
                problems.append(f"PR-S4 synthetic source {d['document_key']} exists in {PRODUCTION_DB}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--partial", action="store_true", help="skip the quota rules while classes are still being drafted")
    args = ap.parse_args()
    rows = load_drafts()
    problems, counts = check(rows, use_db=not args.no_db, partial=args.partial)
    print(json.dumps(counts, ensure_ascii=False))
    for p in problems:
        print("FAIL", p)
    print(f"{len(rows)} samples, {len(problems)} problems")
    if args.json:
        args.json.write_text(json.dumps({"counts": counts, "problems": problems}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
