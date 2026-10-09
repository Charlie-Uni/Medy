"""Run an explicitly authorized answer-quality review through the tools-off Claude CLI.

The request binds exact run rows, cases and prompt hashes. The separate authorization binds the user's quoted
approval, model, attempt count and cost limits. Any failed, invalid, unknown-charge or over-cap call stops without
automatic retry.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parents[2] / "main_set/tools"
sys.path.insert(0, str(TOOLS))
import draft_common as dc  # noqa: E402

from medops.core.canonical import canonical_hash, canonical_json  # noqa: E402
from medops.evals.answer_review import (  # noqa: E402
    MODEL_REVIEW_SCHEMA_VERSION,
    MODEL_REVIEW_SYSTEM,
    SCORER_VERSION,
    load_run_cases,
    model_review_prompt,
    model_review_schema,
    model_review_verdict,
    summarize,
    validate_review,
)
from medops.evals.datasets import read_rows, sha256_file  # noqa: E402
from medops.evals.review_budget import ReviewBudget, money  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
REQUEST_FORMATS = {
    "answer-quality-review-request-v1",
    "answer-quality-review-request-v2",
    "answer-quality-review-request-v3",
}
AUTH_FORMAT = "answer-quality-review-budget-authorization-v1"


def _atomic_json(path: Path, value: Any, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _atomic_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(canonical_json(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_bound_request(path: Path, *, root: Path = REPO) -> tuple[dict, list[dict]]:
    request = json.loads(path.read_text(encoding="utf-8"))
    if (
        request.get("format") not in REQUEST_FORMATS
        or request.get("status") != "prepared_no_model_calls_waiting_authorization"
    ):
        raise ValueError("unsupported answer review request")
    rubric = request.get("rubric") or {}
    root = root.resolve()
    rubric_path = (root / str(rubric.get("path", ""))).resolve()
    rubric_path.relative_to(root)
    if rubric.get("sha256") != sha256_file(rubric_path):
        raise ValueError("answer review rubric changed after preparation")
    cases = []
    case_runs: dict[str, str] = {}
    seen_ids: set[str] = set()
    for binding in request.get("runs") or []:
        run = (root / binding["path"]).resolve()
        run.relative_to(root)
        for key, name in (
            ("rows_sha256", "rows.jsonl"),
            ("run_conditions_sha256", "run_conditions.json"),
            ("dataset_binding_sha256", "dataset_binding.json"),
            ("scoring_binding_sha256", "scoring_binding.json"),
        ):
            if binding.get(key) != sha256_file(run / name):
                raise ValueError(f"bound answer run file changed: {name}")
        current, _ = load_run_cases(run)
        overlap = seen_ids & {case["sample_id"] for case in current}
        if overlap:
            raise ValueError(f"bound answer runs contain duplicate samples: {sorted(overlap)}")
        seen_ids.update(case["sample_id"] for case in current)
        for case in current:
            case_runs[case["sample_id"]] = binding["path"]
        cases.extend(current)
    by_id = {case["sample_id"]: case for case in cases}
    answered = [case for case in cases if case["outcome"] == "answered"]
    escalated = [case for case in cases if case["outcome"] != "answered"]
    if request.get("all_cases") != len(cases):
        raise ValueError("answer review request case count changed")
    reviewer = request.get("reviewer") or {}
    if (
        rubric.get("version") != SCORER_VERSION
        or reviewer.get("kind") != "llm"
        or not reviewer.get("id")
        or not reviewer.get("model")
        or not reviewer.get("reasoning_effort")
        or reviewer.get("system_prompt_sha256") != dc.sha256_bytes(MODEL_REVIEW_SYSTEM.encode("utf-8"))
        or reviewer.get("one_case_per_call") is not True
        or reviewer.get("independent_second_human") is not False
    ):
        raise ValueError("answer review rubric or reviewer identity changed")
    structured = reviewer.get("structured_output")
    if request.get("format") == "answer-quality-review-request-v3":
        if structured != {"kind": "claude_json_schema", "version": MODEL_REVIEW_SCHEMA_VERSION}:
            raise ValueError("answer review structured-output identity changed")
    elif structured is not None:
        raise ValueError("legacy answer review request cannot add structured output")
    selected_ids = [item.get("sample_id") for item in request.get("answered_cases", [])]
    unselected_items = request.get("unselected_answered_cases", [])
    unselected_ids = [item.get("sample_id") for item in unselected_items]
    if request.get("format") == "answer-quality-review-request-v1":
        if unselected_items or request.get("prior_reviews"):
            raise ValueError("v1 answer review request cannot bind prior reviews")
        expected_answered_ids = selected_ids
    else:
        expected_answered_ids = selected_ids + unselected_ids
        if len(selected_ids) != len(set(selected_ids)) or len(unselected_ids) != len(set(unselected_ids)):
            raise ValueError("answer review selection is duplicated")
        if set(selected_ids) & set(unselected_ids):
            raise ValueError("answer review selected and prior cases overlap")
    if not selected_ids:
        raise ValueError("answer review request has no selected answered cases")
    if set(expected_answered_ids) != {case["sample_id"] for case in answered}:
        raise ValueError("answer review request answered accounting changed")
    if selected_ids != [case["sample_id"] for case in answered if case["sample_id"] in set(selected_ids)]:
        raise ValueError("answer review request answered selection order changed")
    if unselected_ids != [case["sample_id"] for case in answered if case["sample_id"] in set(unselected_ids)]:
        raise ValueError("answer review request prior selection order changed")
    if [item.get("sample_id") for item in request.get("escalated_cases", [])] != [
        case["sample_id"] for case in escalated
    ]:
        raise ValueError("answer review request escalation selection changed")
    for item in [*request["answered_cases"], *unselected_items, *request["escalated_cases"]]:
        case = by_id[item["sample_id"]]
        if (
            item.get("run") != case_runs[case["sample_id"]]
            or item.get("case_sha256") != canonical_hash(case)
            or item.get("sample_input_sha256") != case["sample_input_sha256"]
        ):
            raise ValueError(f"{case['sample_id']}: answer review request case identity changed")
    for item in [*request["answered_cases"], *unselected_items]:
        case = by_id[item["sample_id"]]
        prompt = model_review_prompt(case)
        if (
            item.get("case_sha256") != canonical_hash(case)
            or item.get("sample_input_sha256") != case["sample_input_sha256"]
            or item.get("prompt_sha256") != dc.sha256_bytes(prompt.encode("utf-8"))
            or item.get("prompt_chars") != len(prompt)
            or (
                request.get("format") == "answer-quality-review-request-v3"
                and item.get("output_schema_sha256") != canonical_hash(model_review_schema(case))
            )
            or item.get("claims") != len(case["answer"]["claims"])
            or item.get("citations") != len(case["answer"]["citations"])
        ):
            raise ValueError(f"{case['sample_id']}: answer review request differs from exact case")
    budget = request.get("budget_request") or {}
    if (
        budget.get("max_attempts") != len(request["answered_cases"])
        or budget.get("stop_on_nonvalidated_attempt") is not True
        or budget.get("automatic_retry") is not False
        or budget.get("reservation_usd_per_call") != 0.30
        or budget.get("cli_stop_usd_per_call") != 0.28
        or Decimal(str(budget.get("total_budget_usd")))
        != Decimal(str(budget.get("reservation_usd_per_call"))) * len(request["answered_cases"])
    ):
        raise ValueError("answer review request budget scope changed")
    load_bound_prior_verdicts(request, cases, root=root)
    return request, cases


def load_bound_prior_verdicts(request: dict, cases: list[dict], *, root: Path = REPO) -> list[dict]:
    by_hash = {canonical_hash(case): case for case in cases}
    by_id = {case["sample_id"]: case for case in cases}
    unselected = request.get("unselected_answered_cases") or []
    expected = {item["case_sha256"] for item in unselected}
    verdicts: list[dict] = []
    seen = set()
    for binding in request.get("prior_reviews") or []:
        review = (root.resolve() / str(binding.get("path", ""))).resolve()
        review.relative_to(root.resolve())
        files = {name: review / name for name in ("run.json", "budget.json")}
        verdicts_path = review / "verdicts.jsonl"
        for key, path in files.items():
            if binding.get(f"{key.removesuffix('.json')}_sha256") != sha256_file(path):
                raise ValueError(f"bound prior review file changed: {key}")
        expected_verdicts_sha = binding.get("verdicts_sha256")
        if expected_verdicts_sha is None:
            if verdicts_path.exists():
                raise ValueError("bound prior review unexpectedly gained a verdict ledger")
        elif expected_verdicts_sha != sha256_file(verdicts_path):
            raise ValueError("bound prior review file changed: verdicts.jsonl")
        run = json.loads(files["run.json"].read_text(encoding="utf-8"))
        budget = json.loads(files["budget.json"].read_text(encoding="utf-8"))
        if binding.get("request_sha256") != run.get("request_sha256") or binding.get("authorization_sha256") != run.get(
            "authorization_sha256"
        ):
            raise ValueError("bound prior review identity changed")
        attempts = {item["attempt_id"]: item for item in binding.get("attempts") or []}
        ledger_attempts = {item["attempt_id"]: item for item in budget.get("attempts") or []}
        run_attempts = {item["attempt_id"]: item for item in run.get("attempts") or []}
        if set(attempts) != set(ledger_attempts) or set(attempts) != set(run_attempts):
            raise ValueError("bound prior review attempt accounting changed")
        known_cost = Decimal("0")
        for attempt_id, item in attempts.items():
            ledger = ledger_attempts[attempt_id]
            checkpoint = run_attempts[attempt_id]
            capture = review / "call_artifacts" / f"{attempt_id}.json"
            if (
                ledger.get("status") != "accounted"
                or item.get("sample_id") not in by_id
                or item.get("sample_id") != checkpoint.get("sample_id")
                or item.get("outcome") != checkpoint.get("outcome")
                or item.get("cost_usd") != ledger.get("cost_usd")
                or item.get("cli_capture_sha256") != sha256_file(capture)
                or item.get("cli_capture_sha256") != (ledger.get("metadata") or {}).get("cli_capture_sha256")
                or item.get("json_schema_sha256") != (ledger.get("metadata") or {}).get("json_schema_sha256")
            ):
                raise ValueError("bound prior review call artifact changed")
            known_cost += Decimal(str(ledger.get("cost_usd")))
        if binding.get("known_cost_usd") != f"{known_cost:.6f}":
            raise ValueError("bound prior review cost changed")
        validated_cases = []
        current_seen = set()
        for verdict in read_rows(verdicts_path) if verdicts_path.is_file() else []:
            key = verdict.get("case_sha256")
            case = by_hash.get(key)
            if case is None or key in seen:
                raise ValueError("bound prior review verdict is unknown or duplicated")
            validate_review(case, verdict)
            actor = verdict["reviewer"]
            item = next((candidate for candidate in unselected if candidate["case_sha256"] == key), None)
            if (
                item is None
                or actor.get("id") != request["reviewer"]["id"]
                or actor.get("model") != request["reviewer"]["model"]
                or actor.get("prompt_sha256") != item["prompt_sha256"]
            ):
                raise ValueError("bound prior review verdict provenance changed")
            seen.add(key)
            current_seen.add(key)
            verdicts.append(verdict)
            validated_cases.append({"sample_id": case["sample_id"], "case_sha256": key})
        if (
            binding.get("validated_cases") != validated_cases
            or set(run.get("completed_case_sha256") or []) != current_seen
        ):
            raise ValueError("bound prior review checkpoint or validated cases changed")
    if seen != expected:
        raise ValueError("bound prior reviews do not exactly cover unselected answered cases")
    return verdicts


def validate_authorization(request_path: Path, request: dict, authorization_path: Path) -> dict:
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    budget = request["budget_request"]
    expected = {
        "request_sha256": sha256_file(request_path),
        "model": request["reviewer"]["model"],
        "reasoning_effort": request["reviewer"]["reasoning_effort"],
        "total_budget_usd": budget["total_budget_usd"],
        "reservation_usd_per_call": budget["reservation_usd_per_call"],
        "cli_stop_usd_per_call": budget["cli_stop_usd_per_call"],
        "max_attempts": budget["max_attempts"],
        "stop_on_nonvalidated_attempt": True,
        "automatic_retry": False,
        "authorized_sample_ids": [item["sample_id"] for item in request["answered_cases"]],
    }
    if authorization.get("format") != AUTH_FORMAT or any(authorization.get(k) != v for k, v in expected.items()):
        raise ValueError("answer review authorization differs from the prepared request")
    if authorization.get("approved_by") != "project-owner" or not str(authorization.get("approval_quote", "")).strip():
        raise ValueError("answer review authorization lacks the project owner's quoted approval")
    return authorization


def recover_structured_output_attempts(
    request: dict,
    cases: list[dict],
    authorization: dict,
    out: Path,
    ledger: ReviewBudget,
) -> int:
    """Recover valid v3 verdicts that an older adapter ignored in the CLI structured_output field."""
    run_path = out / "run.json"
    budget_path = out / "budget.json"
    if request.get("format") != "answer-quality-review-request-v3" or not run_path.is_file():
        return 0
    run = json.loads(run_path.read_text(encoding="utf-8"))
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    if (
        run.get("request_sha256") != authorization["request_sha256"]
        or run.get("authorization_sha256") != authorization["authorization_sha256"]
    ):
        raise ValueError("cannot recover a structured output from another execution identity")
    by_id = {case["sample_id"]: case for case in cases}
    items = {item["sample_id"]: item for item in request["answered_cases"]}
    ledger_attempts = {item["attempt_id"]: item for item in budget.get("attempts") or []}
    verdicts_path = out / "verdicts.jsonl"
    verdicts = read_rows(verdicts_path) if verdicts_path.is_file() else []
    verdict_hashes = {item["case_sha256"] for item in verdicts}
    recovered = 0
    for attempt in run.get("attempts") or []:
        if attempt.get("outcome") != "failed":
            continue
        sample_id = attempt.get("sample_id")
        item = items.get(sample_id)
        case = by_id.get(sample_id)
        accounted = ledger_attempts.get(attempt.get("attempt_id"))
        if item is None or case is None or accounted is None or accounted.get("status") != "accounted":
            continue
        identity = accounted.get("identity") or {}
        metadata = accounted.get("metadata") or {}
        if (
            identity.get("case_sha256") != item["case_sha256"]
            or identity.get("prompt_sha256") != item["prompt_sha256"]
            or identity.get("output_schema_sha256") != item["output_schema_sha256"]
        ):
            raise ValueError("failed structured-output attempt differs from the request")
        if metadata.get("json_schema_sha256") != item["output_schema_sha256"]:
            continue
        capture = out / "call_artifacts" / f"{attempt['attempt_id']}.json"
        if not capture.is_file():
            continue
        if sha256_file(capture) != metadata.get("cli_capture_sha256"):
            raise ValueError("failed structured-output artifact differs from its ledger")
        raw = json.loads(capture.read_text(encoding="utf-8"))
        outer = json.loads(raw.get("stdout", ""))
        usage = outer.get("modelUsage") or {}
        structured = outer.get("structured_output")
        if (
            raw.get("returncode") != 0
            or outer.get("subtype") != "success"
            or outer.get("is_error") is True
            or list(usage) != [authorization["model"]]
            or not isinstance(structured, dict)
            or money(outer.get("total_cost_usd")) != money(accounted.get("cost_usd"))
        ):
            continue
        verdict = model_review_verdict(
            case,
            json.dumps(structured, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            reviewer_id=request["reviewer"]["id"],
            model=authorization["model"],
            prompt_sha256=item["prompt_sha256"],
        )
        if item["case_sha256"] not in verdict_hashes:
            verdicts.append(verdict)
            _atomic_jsonl(verdicts_path, verdicts)
            verdict_hashes.add(item["case_sha256"])
        evidence = {
            "kind": "claude-structured-output-adapter-recovery-v1",
            "case_sha256": item["case_sha256"],
            "prompt_sha256": item["prompt_sha256"],
            "output_schema_sha256": item["output_schema_sha256"],
            "cli_capture_sha256": metadata["cli_capture_sha256"],
            "structured_output_sha256": canonical_hash(structured),
        }
        ledger.reconcile_validated_reply(attempt["attempt_id"], evidence=evidence)
        reconciliation = {"attempt_id": attempt["attempt_id"], **evidence}
        if reconciliation not in run.setdefault("reconciliations", []):
            run["reconciliations"].append(reconciliation)
            _atomic_json(run_path, run)
        recovered += 1
    return recovered


def execute(
    request_path: Path,
    authorization_path: Path,
    out: Path,
    *,
    binary: str = dc.DEFAULT_BINARY,
    call: Callable[..., tuple[str, dict[str, Any]]] = dc.run_claude,
    version_call: Callable[[str], str] = dc.cli_version,
    root: Path = REPO,
) -> dict:
    request, cases = load_bound_request(request_path, root=root)
    prior_verdicts = load_bound_prior_verdicts(request, cases, root=root)
    authorization = validate_authorization(request_path, request, authorization_path)
    out.mkdir(parents=True, exist_ok=True)
    scope = {**authorization, "authorization_sha256": sha256_file(authorization_path)}
    ledger = ReviewBudget(out / "budget.json", total_usd=authorization["total_budget_usd"], scope=scope)
    recover_structured_output_attempts(request, cases, scope, out, ledger)
    verdicts_path = out / "verdicts.jsonl"
    existing = read_rows(verdicts_path) if verdicts_path.exists() else []
    by_hash = {canonical_hash(case): case for case in cases}
    item_by_hash = {item["case_sha256"]: item for item in request["answered_cases"]}
    seen = set()
    for verdict in existing:
        key = verdict.get("case_sha256")
        if key not in by_hash or key in seen:
            raise ValueError("existing verdict is unknown or duplicated")
        item = item_by_hash.get(key)
        if item is None:
            raise ValueError("existing verdict is not for an authorized answered case")
        rebuilt = model_review_verdict(
            by_hash[key],
            json.dumps({k: verdict[k] for k in ("claims", "citations", "completeness")}),
            reviewer_id=request["reviewer"]["id"],
            model=request["reviewer"]["model"],
            prompt_sha256=item["prompt_sha256"],
        )
        if rebuilt != verdict:
            raise ValueError("existing verdict trusted provenance differs from the request")
        seen.add(key)
    cli_version = version_call(binary)
    run_identity = {
        "format": "answer-quality-review-run-v1",
        "request_sha256": sha256_file(request_path),
        "authorization_sha256": sha256_file(authorization_path),
        "cli": "claude-code",
        "cli_version": cli_version,
        "model": authorization["model"],
        "reasoning_effort": authorization["reasoning_effort"],
    }
    run_path = out / "run.json"
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if any(run.get(key) != value for key, value in run_identity.items()):
            raise ValueError("cannot resume answer review after its execution identity changed")
        checkpointed = set(run.get("completed_case_sha256", []))
        if not checkpointed.issubset(seen):
            raise ValueError("answer review checkpoint names a case without a validated verdict")
        if checkpointed != seen:
            run.setdefault("recovered_case_sha256", []).extend(sorted(seen - checkpointed))
            run["completed_case_sha256"] = sorted(seen)
            _atomic_json(run_path, run)
    else:
        if seen:
            raise ValueError("answer review verdicts exist without an execution checkpoint")
        run = {
            **run_identity,
            "completed_case_sha256": sorted(seen),
            "attempts": [],
        }
        _atomic_json(run_path, run)
    with tempfile.TemporaryDirectory(prefix="answer-review-") as temp:
        for item in request["answered_cases"]:
            if item["case_sha256"] in seen:
                continue
            case = by_hash[item["case_sha256"]]
            prompt = model_review_prompt(case)
            schema = model_review_schema(case) if request["format"] == "answer-quality-review-request-v3" else None
            reservation = ledger.reserve(
                authorization["reservation_usd_per_call"],
                identity={
                    "sample_id": item["sample_id"],
                    "case_sha256": item["case_sha256"],
                    "prompt_sha256": item["prompt_sha256"],
                    "model": authorization["model"],
                    "cli_version": cli_version,
                    "output_schema_sha256": canonical_hash(schema) if schema is not None else None,
                },
            )
            capture = out / "call_artifacts" / f"{reservation['attempt_id']}.json"
            meta: dict[str, Any] = {}
            reply = ""
            try:
                reply, meta = call(
                    binary,
                    authorization["model"],
                    authorization["reasoning_effort"],
                    MODEL_REVIEW_SYSTEM,
                    prompt,
                    Path(temp),
                    max_cost_usd=authorization["cli_stop_usd_per_call"],
                    capture_path=capture,
                    json_schema=schema,
                )
                if schema is not None and meta.get("json_schema_sha256") != item["output_schema_sha256"]:
                    raise ValueError("answer review CLI structured-output schema differs from the request")
                verdict = model_review_verdict(
                    case,
                    reply,
                    reviewer_id=request["reviewer"]["id"],
                    model=authorization["model"],
                    prompt_sha256=item["prompt_sha256"],
                )
            except BaseException as exc:
                metering = exc.metadata if isinstance(exc, dc.ClaudeCallError) else meta
                ledger.finish(
                    reservation["attempt_id"],
                    cost_usd=metering.get("cost_usd"),
                    outcome=str(exc) if isinstance(exc, dc.ClaudeCallError) else type(exc).__name__,
                    metadata={
                        k: metering.get(k)
                        for k in ("model_observed", "session_id", "cli_capture_sha256", "json_schema_sha256")
                    },
                )
                run["attempts"].append(
                    {"sample_id": item["sample_id"], "attempt_id": reservation["attempt_id"], "outcome": "failed"}
                )
                _atomic_json(run_path, run)
                if isinstance(exc, (ValueError, dc.ClaudeCallError)):
                    raise RuntimeError(f"{item['sample_id']}: review stopped after a nonvalidated call") from None
                raise
            existing.append(verdict)
            _atomic_jsonl(verdicts_path, existing)
            ledger.finish(
                reservation["attempt_id"],
                cost_usd=meta["cost_usd"],
                outcome="validated_reply",
                metadata={
                    k: meta.get(k) for k in ("model_observed", "session_id", "cli_capture_sha256", "json_schema_sha256")
                },
            )
            seen.add(item["case_sha256"])
            run["completed_case_sha256"] = sorted(seen)
            run["attempts"].append(
                {
                    "sample_id": item["sample_id"],
                    "attempt_id": reservation["attempt_id"],
                    "outcome": "validated_reply",
                    "prompt_sha256": item["prompt_sha256"],
                    "cost_usd": meta["cost_usd"],
                    "model_observed": meta.get("model_observed"),
                    "session_id": meta.get("session_id"),
                    "cli_capture_sha256": meta.get("cli_capture_sha256"),
                    "json_schema_sha256": meta.get("json_schema_sha256"),
                    "input_tokens": meta.get("input_tokens"),
                    "cache_read_input_tokens": meta.get("cache_read_input_tokens"),
                    "cache_creation_input_tokens": meta.get("cache_creation_input_tokens"),
                    "output_tokens": meta.get("output_tokens"),
                }
            )
            _atomic_json(run_path, run)
    budget_summary = ledger.summary()
    if budget_summary["unresolved_attempts"]:
        raise RuntimeError("answer review has an unresolved spend reservation; reconcile before reporting")
    if len(seen) != len(request["answered_cases"]):
        raise RuntimeError("answer review ended without all authorized verdicts")
    result = summarize(cases, [*prior_verdicts, *existing])
    result["budget"] = budget_summary
    result["prior_reviewed_cases"] = len(prior_verdicts)
    result["request_sha256"] = sha256_file(request_path)
    result["authorization_sha256"] = sha256_file(authorization_path)
    _atomic_json(out / "report.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--binary", default=dc.DEFAULT_BINARY)
    args = parser.parse_args()
    print(json.dumps(execute(args.request, args.authorization, args.out, binary=args.binary), indent=2))


if __name__ == "__main__":
    main()
