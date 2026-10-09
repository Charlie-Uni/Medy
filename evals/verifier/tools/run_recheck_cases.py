"""DEC-003 recheck cases (record 69 defect 3 onwards): claim + chunk id pairs collected from live runs whose judge verdict
looked wrong. Evidence text is read from the database at run time (chunk texts never enter Git); the pair goes through
the production verifier (`verify_claims`, rules + judge) and the verdict is compared with the expected one.

    python evals/verifier/tools/run_recheck_cases.py [--cases evals/verifier/dec003/recheck_cases.jsonl] [--judge gpt-6-sol]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import psycopg

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from medops.core.config import Settings  # noqa: E402
from medops.domain.answer import Claim  # noqa: E402
from medops.domain.common import DocStatus  # noqa: E402
from medops.domain.evidence import Citation, Evidence  # noqa: E402
from medops.infrastructure.llm.factory import build_budgeted_gateway  # noqa: E402
from medops.verification.verifier import VERIFIER_VERSION, verify_claims  # noqa: E402


def _admin_dsn(database: str) -> str:
    from dotenv import dotenv_values

    env = dotenv_values(REPO / ".env")
    return re.sub(r"/[^/?]+(\?|$)", rf"/{database}\1", env["DATABASE_ADMIN_URL"] or "")


def evidence_for(conn: psycopg.Connection, chunk_id: str) -> Evidence:
    row = conn.execute(
        """select c.chunk_id::text, d.doc_id::text, d.version, d.effective_from, c.page, c.section, c.content, c.chunk_content_hash, d.status::text
           from chunks c join documents d on d.doc_id = c.doc_id where c.chunk_id::text = %s""",
        (chunk_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"chunk {chunk_id} not found")
    import hashlib

    text = row[6]
    return Evidence(
        citation=Citation(
            doc_id=row[1],
            version=row[2],
            effective_date=row[3],
            page=max(int(row[4] or 1), 1),
            section=row[5] or "",
            chunk_id=row[0],
        ),
        text=text,
        evidence_text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        chunk_content_hash=row[7] or hashlib.sha256(text.encode("utf-8")).hexdigest(),
        status=DocStatus(row[8]),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=pathlib.Path, default=REPO / "evals/verifier/dec003/recheck_cases.jsonl")
    ap.add_argument("--judge", default="gpt-6-sol")
    ap.add_argument(
        "--no-judge",
        action="store_true",
        help="rules + containment only (no model calls): tool smoke, not the DEC-003 answer",
    )
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/recheck_results.json")
    args = ap.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = Settings()
    gateway = build_budgeted_gateway(settings)
    results = []
    for case in cases:
        with psycopg.connect(_admin_dsn(case["database"])) as conn:
            ev = evidence_for(conn, case["chunk_id"])
        claim = Claim(text=case["claim"], citation_chunk_ids=(ev.citation.chunk_id,))
        result = verify_claims(
            (claim,),
            (ev,),
            gateway=None if args.no_judge else gateway,
            judge_model_id=None if args.no_judge else args.judge,
        )
        verdicts = sorted({e.verdict.value for e in result.elements})
        supported = all(e.verdict.value == "supported" for e in result.elements) and bool(result.elements)
        observed = "supported" if supported else ("contradicted" if "contradicted" in verdicts else "not_supported")
        results.append(
            {
                **case,
                "observed": observed,
                "elements": [
                    {"kind": e.kind.value, "verdict": e.verdict.value, "reason": e.reason[:160]}
                    for e in result.elements
                ],
                "pass": observed == case["expected"],
            }
        )
        print(
            f"{case['case_id']}: expected {case['expected']} observed {observed} {'PASS' if observed == case['expected'] else 'FAIL'}"
        )
    args.out.write_text(
        json.dumps(
            {"verifier_version": VERIFIER_VERSION, "judge": args.judge, "results": results},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
