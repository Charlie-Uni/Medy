"""Prepare an exact, zero-call authorization request for semantic answer review.

python evals/harness/tools/prepare_answer_review.py --run RUN [RUN ...] --out REQUEST.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from medops.core.canonical import canonical_hash
from medops.evals.answer_review import (
    MODEL_REVIEW_SCHEMA_VERSION,
    MODEL_REVIEW_SYSTEM,
    SCORER_VERSION,
    load_run_cases,
    model_review_prompt,
    model_review_schema,
    validate_review,
)
from medops.evals.datasets import read_rows, sha256_file

REPO = Path(__file__).resolve().parents[3]
FORMAT = "answer-quality-review-request-v3"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bind_prior_review(path: Path, cases: list[dict], *, root: Path) -> tuple[dict, list[dict]]:
    review = path.resolve()
    relative = review.relative_to(root.resolve()).as_posix()
    required = {name: review / name for name in ("budget.json", "run.json")}
    if not all(item.is_file() for item in required.values()):
        raise ValueError("prior review lacks its budget or run ledger")
    verdicts_path = review / "verdicts.jsonl"
    run = json.loads(required["run.json"].read_text(encoding="utf-8"))
    budget = json.loads(required["budget.json"].read_text(encoding="utf-8"))
    verdicts = read_rows(verdicts_path) if verdicts_path.is_file() else []
    by_hash = {canonical_hash(case): case for case in cases}
    by_id = {case["sample_id"]: case for case in cases}
    validated = []
    seen = set()
    for verdict in verdicts:
        case = by_hash.get(verdict.get("case_sha256"))
        if case is None or verdict["case_sha256"] in seen:
            raise ValueError("prior review contains an unknown or duplicate verdict")
        validate_review(case, verdict)
        seen.add(verdict["case_sha256"])
        validated.append({"sample_id": case["sample_id"], "case_sha256": verdict["case_sha256"]})
    completed = set(run.get("completed_case_sha256") or [])
    if completed != seen:
        raise ValueError("prior review checkpoint and validated verdicts differ")
    attempts = []
    budget_attempts = {item["attempt_id"]: item for item in budget.get("attempts") or []}
    for attempt in run.get("attempts") or []:
        sample_id = attempt.get("sample_id")
        attempt_id = attempt.get("attempt_id")
        ledger_attempt = budget_attempts.get(attempt_id)
        if sample_id not in by_id or ledger_attempt is None or ledger_attempt.get("status") != "accounted":
            raise ValueError("prior review attempt is not fully accounted")
        capture = review / "call_artifacts" / f"{attempt_id}.json"
        capture_sha = (ledger_attempt.get("metadata") or {}).get("cli_capture_sha256")
        if not capture.is_file() or capture_sha != sha256_file(capture):
            raise ValueError("prior review call artifact differs from its ledger")
        attempts.append(
            {
                "sample_id": sample_id,
                "attempt_id": attempt_id,
                "outcome": attempt.get("outcome"),
                "cost_usd": ledger_attempt.get("cost_usd"),
                "cli_capture_sha256": capture_sha,
                "json_schema_sha256": (ledger_attempt.get("metadata") or {}).get("json_schema_sha256"),
            }
        )
    if set(budget_attempts) != {item["attempt_id"] for item in attempts}:
        raise ValueError("prior review run and budget attempts differ")
    known_cost = sum(Decimal(str(item["cost_usd"])) for item in budget_attempts.values())
    return (
        {
            "path": relative,
            "request_sha256": run.get("request_sha256"),
            "authorization_sha256": run.get("authorization_sha256"),
            "run_sha256": sha256_file(required["run.json"]),
            "budget_sha256": sha256_file(required["budget.json"]),
            "verdicts_sha256": sha256_file(verdicts_path) if verdicts_path.is_file() else None,
            "known_cost_usd": f"{known_cost:.6f}",
            "validated_cases": validated,
            "attempts": attempts,
        },
        verdicts,
    )


def prepare(
    runs: list[Path],
    *,
    root: Path = REPO,
    selected_sample_ids: list[str] | None = None,
    prior_review: Path | list[Path] | None = None,
) -> dict:
    if not runs:
        raise ValueError("at least one run is required")
    cases = []
    bound_runs = []
    case_runs: dict[str, str] = {}
    seen_ids: set[str] = set()
    for supplied in runs:
        run = supplied.resolve()
        relative = run.relative_to(root.resolve()).as_posix()
        current, _ = load_run_cases(run)
        overlap = seen_ids & {case["sample_id"] for case in current}
        if overlap:
            raise ValueError(f"review runs contain duplicate samples: {sorted(overlap)}")
        for case in current:
            seen_ids.add(case["sample_id"])
            case_runs[case["sample_id"]] = relative
        cases.extend(current)
        bound_runs.append(
            {
                "path": relative,
                "rows_sha256": sha256_file(run / "rows.jsonl"),
                "run_conditions_sha256": sha256_file(run / "run_conditions.json"),
                "dataset_binding_sha256": sha256_file(run / "dataset_binding.json"),
                "scoring_binding_sha256": sha256_file(run / "scoring_binding.json"),
            }
        )
    answered, escalated = [], []
    for case in cases:
        common = {
            "sample_id": case["sample_id"],
            "run": case_runs[case["sample_id"]],
            "case_sha256": canonical_hash(case),
            "sample_input_sha256": case["sample_input_sha256"],
        }
        if case["outcome"] == "answered":
            prompt = model_review_prompt(case)
            schema = model_review_schema(case)
            answered.append(
                {
                    **common,
                    "prompt_sha256": digest(prompt),
                    "prompt_chars": len(prompt),
                    "output_schema_sha256": canonical_hash(schema),
                    "claims": len(case["answer"]["claims"]),
                    "citations": len(case["answer"]["citations"]),
                }
            )
        else:
            escalated.append(common)
    if len(answered) < 8:
        raise ValueError("fewer than eight answered cases; do not request semantic review")
    all_answered_ids = [item["sample_id"] for item in answered]
    if selected_sample_ids is None:
        selected_sample_ids = all_answered_ids
    if not selected_sample_ids or len(selected_sample_ids) != len(set(selected_sample_ids)):
        raise ValueError("answer review selection must be nonempty and unique")
    unknown = set(selected_sample_ids) - set(all_answered_ids)
    if unknown:
        raise ValueError(f"answer review selection contains non-answered cases: {sorted(unknown)}")
    selected = set(selected_sample_ids)
    selected_answered = [item for item in answered if item["sample_id"] in selected]
    if [item["sample_id"] for item in selected_answered] != selected_sample_ids:
        raise ValueError("answer review selection must preserve bound run order")
    unselected_answered = [item for item in answered if item["sample_id"] not in selected]
    prior_reviews = []
    prior_paths = [] if prior_review is None else ([prior_review] if isinstance(prior_review, Path) else prior_review)
    if unselected_answered:
        if not prior_paths:
            raise ValueError("a partial follow-up request must bind prior validated verdicts")
        prior_verdicts = []
        for path in prior_paths:
            binding, current_verdicts = _bind_prior_review(path, cases, root=root)
            prior_reviews.append(binding)
            prior_verdicts.extend(current_verdicts)
        prior_ids = [item["sample_id"] for binding in prior_reviews for item in binding["validated_cases"]]
        if set(prior_ids) != {item["sample_id"] for item in unselected_answered}:
            raise ValueError("prior validated verdicts do not exactly cover unselected answered cases")
        if len(prior_ids) != len(set(prior_ids)) or len(prior_verdicts) != len(unselected_answered):
            raise ValueError("prior review verdict count differs from the follow-up selection")
    elif prior_paths:
        raise ValueError("a full review request must not attach an unused prior review")
    rubric = root / "evals/answer_quality/RUBRIC.md"
    total_budget = float(Decimal("0.30") * len(selected_answered))
    return {
        "format": FORMAT,
        "created_at": "2026-10-09",
        "status": "prepared_no_model_calls_waiting_authorization",
        "rubric": {
            "version": SCORER_VERSION,
            "path": rubric.relative_to(root).as_posix(),
            "sha256": sha256_file(rubric),
        },
        "runs": bound_runs,
        "reviewer": {
            "kind": "llm",
            "id": "reviewer-llm-answer-quality-01",
            "model": "claude-opus-5",
            "reasoning_effort": "high",
            "system_prompt_sha256": digest(MODEL_REVIEW_SYSTEM),
            "one_case_per_call": True,
            "independent_second_human": False,
            "structured_output": {
                "kind": "claude_json_schema",
                "version": MODEL_REVIEW_SCHEMA_VERSION,
            },
        },
        "budget_request": {
            "cli_stop_usd_per_call": 0.28,
            "reservation_usd_per_call": 0.30,
            "total_budget_usd": total_budget,
            "max_attempts": len(selected_answered),
            "stop_on_nonvalidated_attempt": True,
            "automatic_retry": False,
        },
        "answered_cases": selected_answered,
        "unselected_answered_cases": unselected_answered,
        "prior_reviews": prior_reviews,
        "escalated_cases": escalated,
        "all_cases": len(cases),
        "limitations": [
            "This purposeful development panel is not a population estimate or a formal gate.",
            "Model judgments are not an independent second-human review.",
            "The Claude CLI stop threshold is not a guaranteed settlement ceiling; a call above its 0.30 USD reservation stops the run.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, nargs="+", required=True)
    parser.add_argument("--only", nargs="+", help="Answered sample IDs for a bound follow-up request")
    parser.add_argument(
        "--prior-review", type=Path, nargs="+", help="Stopped reviews containing earlier verdicts and attempts"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    request = prepare(
        args.run,
        selected_sample_ids=args.only,
        prior_review=args.prior_review,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": request["status"],
                "request_sha256": sha256_file(args.out),
                "all_cases": request["all_cases"],
                "answered_cases": len(request["answered_cases"]),
                "escalated_cases": len(request["escalated_cases"]),
                "prompt_chars": sum(item["prompt_chars"] for item in request["answered_cases"]),
                "budget_request": request["budget_request"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
