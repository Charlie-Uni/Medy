"""Semantic review has its own evidence and denominators; missing judgments cannot become successes."""

import copy
import hashlib
import json
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest

from medops.core.canonical import canonical_hash
from medops.evals.answer_review import (
    INPUT_FORMAT,
    SCORER_VERSION,
    VERDICT_FORMAT,
    capture_snapshot,
    load_snapshot,
    model_review_prompt,
    model_review_schema,
    model_review_verdict,
    save_snapshot,
    snapshot,
    summarize,
    validate_calibration_plan,
    validate_claude_review_schema,
    validate_review,
    validate_snapshot,
)
from medops.evals.datasets import sha256_file
from medops.harness.runtime import run_ask
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval, make_deps, state

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def case():
    run = run_ask(
        state(),
        make_deps(
            FakeRetrieval(evidence("c1", LABEL)),
            FakeModelGateway(
                {
                    "answer": [
                        {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}
                    ]
                }
            ),
        ),
    )
    assert run.outcome == "answered"
    sample = {
        "sample_id": "synthetic-1",
        "query": run.state.query,
        "dept": "PV",
        "answerable": True,
        "required_gold_evidence": [{"gold_id": "g1", "key_text": LABEL}],
    }
    return snapshot(
        sample,
        run.state,
        run.outcome,
        documents={
            "doc-1": {
                "document_key": "synthetic-doc",
                "source_hash": "a" * 64,
                "version": "v1",
                "title": "Synthetic unit test label",
            }
        },
    )


def judgment(case, *, support="supported", completeness="complete"):
    answer = case["answer"] or {"claims": [], "citations": []}
    return {
        "format": VERDICT_FORMAT,
        "rubric_version": SCORER_VERSION,
        "case_sha256": canonical_hash(case),
        "reviewer": {
            "kind": "llm",
            "id": "test-fixture-not-actual-review",
            "model": "fixture",
            "prompt_sha256": "b" * 64,
            "independent_second_human": False,
        },
        "claims": [
            {"claim_index": i, "verdict": support, "reason": "Synthetic fixture judgment."}
            for i in range(len(answer["claims"]))
        ],
        "citations": [
            {"citation_index": i, "verdict": support, "reason": "Synthetic fixture judgment."}
            for i in range(len(answer["citations"]))
        ],
        "completeness": {"verdict": completeness, "reason": "Synthetic fixture judgment."},
    }


def test_exact_claim_links_and_evidence_survive_round_trip_without_old_judge_opinions(case, tmp_path):
    assert case["answer"]["claims"][0]["citation_chunk_ids"] == ["c1"]
    assert case["evidence"][0]["text"] == LABEL
    assert "verify_result" not in case and "review" not in case and "gold_cited" not in case
    reference = save_snapshot(tmp_path, case)
    assert reference["format"] == INPUT_FORMAT and load_snapshot(tmp_path, reference) == case
    assert save_snapshot(tmp_path, case) == reference
    (tmp_path / reference["path"]).write_text("{}\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_snapshot(tmp_path, reference)
    with pytest.raises(ValueError, match="content changed"):
        save_snapshot(tmp_path, case)


@pytest.mark.parametrize(
    "mutation",
    ["wrong_evidence", "wrong_citation", "duplicate_evidence", "missing_doc", "doc_version", "answer_after_escalation"],
)
def test_snapshot_corruption_is_rejected(case, mutation):
    if mutation == "wrong_evidence":
        case["evidence"][0]["text"] = "Changed text"
    elif mutation == "wrong_citation":
        case["answer"]["citations"][0]["page"] = 99
    elif mutation == "duplicate_evidence":
        case["evidence"].append(copy.deepcopy(case["evidence"][0]))
    elif mutation == "missing_doc":
        case["documents"] = {}
    elif mutation == "doc_version":
        case["documents"]["doc-1"]["version"] = "v2"
    else:
        case["outcome"] = "escalated"
    with pytest.raises(ValueError):
        validate_snapshot(case)


@pytest.mark.parametrize(
    "mutation",
    [
        "stale_case",
        "rubric",
        "missing_claim",
        "duplicate_citation",
        "wrong_index",
        "empty_reason",
        "human_claim",
        "prompt_hash",
        "na_complete",
    ],
)
def test_invalid_reviews_cannot_enter_summary(case, mutation):
    review = judgment(case)
    if mutation == "stale_case":
        review["case_sha256"] = "0" * 64
    elif mutation == "rubric":
        review["rubric_version"] = "old"
    elif mutation == "missing_claim":
        review["claims"] = []
    elif mutation == "duplicate_citation":
        review["citations"].append(copy.deepcopy(review["citations"][0]))
    elif mutation == "wrong_index":
        review["claims"][0]["claim_index"] = True
    elif mutation == "empty_reason":
        review["completeness"]["reason"] = ""
    elif mutation == "human_claim":
        review["reviewer"]["independent_second_human"] = True
    elif mutation == "prompt_hash":
        review["reviewer"]["prompt_sha256"] = "not-a-hash"
    else:
        review["completeness"]["verdict"] = "not_applicable"
    with pytest.raises(ValueError):
        summarize([case], [review])


def test_missing_or_unverifiable_semantics_never_becomes_100_percent(case):
    missing = summarize([case], [])
    assert missing["citation_support"] == {
        "numerator": 0,
        "denominator": 1,
        "pending": 1,
        "unverifiable": 0,
        "rate": None,
    }
    unknown = summarize([case], [judgment(case, support="unverifiable")])
    assert unknown["claim_support"]["rate"] is None and unknown["claim_support"]["unverifiable"] == 1
    assert unknown["formal_gate"] is False
    incomplete = summarize([case], [judgment(case, completeness="incomplete")])
    assert incomplete["claim_support"]["rate"] == 1
    assert incomplete["answer_completeness"]["rate"] == 0


def test_completeness_keeps_answerable_abstentions_and_excludes_no_answer_cases(case):
    abstained = {**case, "sample_id": "synthetic-2", "answer": None, "outcome": "escalated"}
    no_answer = {**abstained, "sample_id": "synthetic-3", "answerable": False, "required_gold_evidence": []}
    result = summarize([case, abstained, no_answer], [judgment(case)])
    assert result["answer_completeness"] == {
        "numerator": 1,
        "denominator": 2,
        "pending": 0,
        "unverifiable": 0,
        "rate": 0.5,
    }
    assert result["citation_support"]["rate"] == 1 and result["citation_support"]["denominator"] == 1
    with pytest.raises(ValueError, match="stays incomplete"):
        validate_review(abstained, judgment(abstained))
    with pytest.raises(ValueError, match="no-answer cases"):
        validate_review(no_answer, judgment(no_answer))
    validate_review(no_answer, judgment(no_answer, completeness="not_applicable"))
    assert summarize([], [])["citation_support"]["rate"] is None


def test_conflicting_judges_require_explicit_resolution_not_last_writer_wins(case):
    with pytest.raises(ValueError, match="duplicate case review"):
        summarize([case], [judgment(case), judgment(case, support="contradicted")])


def test_report_uses_exact_local_snapshot_and_rejects_historical_aggregate_only_rows(case, tmp_path, monkeypatch):
    tool = runpy.run_path(str(REPO / "evals/harness/tools/answer_review.py"))
    report = tool["report"]
    row = {
        "sample_id": case["sample_id"],
        "sample_input_sha256": case["sample_input_sha256"],
        "outcome": case["outcome"],
        "versions": case["versions"],
        "query": case["query"],
        "dept": case["dept"],
        "claims": [c["text"] for c in case["answer"]["claims"]],
        "cited_chunks": [c["chunk_id"] for c in case["answer"]["citations"]],
    }
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="cannot reconstruct"):
        report(tmp_path)
    row["answer_review_input"] = save_snapshot(tmp_path, case)
    path.write_text(json.dumps(row) + "\n")
    assert report(tmp_path)["reviewed_cases"] == 0
    assert tool["report_runs"]([tmp_path])["cases"] == 1
    with pytest.raises(ValueError, match="duplicate samples"):
        tool["report_runs"]([tmp_path, tmp_path])
    verdicts = tmp_path / "reviews.jsonl"
    verdicts.write_text(json.dumps(judgment(case)) + "\n")
    assert report(tmp_path, verdicts)["reviewed_cases"] == 1
    out = tmp_path / "new" / "report.json"
    monkeypatch.setattr(sys, "argv", ["answer_review.py", "--run", str(tmp_path), "--out", str(out)])
    tool["main"]()
    assert json.loads(out.read_text())["reviewed_cases"] == 0
    row["versions"] = {"model_config_version": "changed"}
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="runtime versions differ"):
        report(tmp_path, verdicts)


def test_capture_failure_is_explicit_without_discarding_the_paid_answer_or_leaking_db_message(tmp_path):
    run = run_ask(
        state(),
        make_deps(
            FakeRetrieval(evidence("c1", LABEL)),
            FakeModelGateway(
                {
                    "answer": [
                        {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}
                    ]
                }
            ),
        ),
    )

    @contextmanager
    def unavailable(user):
        raise psycopg.OperationalError("secret-dsn-must-not-appear")
        yield

    result = capture_snapshot(tmp_path, {}, run.state, run.outcome, unavailable)
    assert result == {"answer_review_input": None, "answer_review_error": "OperationalError"}
    assert run.outcome == "answered" and run.state.answer is not None


def test_calibration_plan_is_bound_to_frozen_samples_and_rubric(tmp_path):
    dataset = REPO / "evals/main_set/main-v5-provisional"
    source = REPO / "evals/answer_quality/calibration-v1-plan.json"
    assert validate_calibration_plan(source, dataset, root=REPO)["selection"]["cases"] == 10
    changed = json.loads(source.read_text())
    changed["selection"]["items"][0]["sample_input_sha256"] = "0" * 64
    bad = tmp_path / "plan.json"
    bad.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="differs from the frozen sample"):
        validate_calibration_plan(bad, dataset, root=REPO)


def test_exact_review_request_and_budgeted_runner_are_resumable(case, tmp_path):
    prepare_tool = runpy.run_path(str(REPO / "evals/harness/tools/prepare_answer_review.py"))
    run_tool = runpy.run_path(str(REPO / "evals/harness/tools/run_answer_review.py"))
    rubric = tmp_path / "evals/answer_quality/RUBRIC.md"
    rubric.parent.mkdir(parents=True)
    rubric.write_text("fixed rubric\n")
    run = tmp_path / "runs/source"
    run.mkdir(parents=True)
    rows = []
    for index in range(8):
        current = copy.deepcopy(case)
        current["sample_id"] = f"synthetic-{index}"
        current["sample_input_sha256"] = f"{index + 1:064x}"
        answer = current["answer"]
        row = {
            "sample_id": current["sample_id"],
            "sample_input_sha256": current["sample_input_sha256"],
            "outcome": "answered",
            "versions": current["versions"],
            "query": current["query"],
            "dept": current["dept"],
            "claims": [claim["text"] for claim in answer["claims"]],
            "cited_chunks": [citation["chunk_id"] for citation in answer["citations"]],
            "answer_review_input": save_snapshot(run, current),
        }
        rows.append(row)
    (run / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    for name in ("run_conditions.json", "dataset_binding.json", "scoring_binding.json"):
        (run / name).write_text("{}\n")

    request = prepare_tool["prepare"]([run], root=tmp_path)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request) + "\n")
    loaded, loaded_cases = run_tool["load_bound_request"](request_path, root=tmp_path)
    assert len(loaded_cases) == 8 and loaded["budget_request"]["max_attempts"] == 8
    budget = request["budget_request"]
    authorization = {
        "format": run_tool["AUTH_FORMAT"],
        "approved_by": "project-owner",
        "approval_quote": "fixture approval",
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
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(json.dumps(authorization) + "\n")
    calls = []

    def fake_call(binary, model, effort, system, prompt, workdir, **kwargs):
        calls.append((binary, model, effort, system, prompt, workdir, kwargs))
        reply = {
            "claims": [{"claim_index": 0, "verdict": "supported", "reason": "The cited text matches."}],
            "citations": [{"citation_index": 0, "verdict": "supported", "reason": "The citation supports the claim."}],
            "completeness": {"verdict": "complete", "reason": "The answer addresses the question."},
        }
        return json.dumps(reply), {
            "cost_usd": 0.01,
            "model_observed": model,
            "session_id": f"session-{len(calls)}",
            "cli_capture_sha256": f"{len(calls):064x}",
            "input_tokens": 10,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens": 5,
            "json_schema_sha256": canonical_hash(kwargs["json_schema"]),
        }

    out = tmp_path / "review"
    result = run_tool["execute"](
        request_path,
        authorization_path,
        out,
        binary="claude-fixture",
        call=fake_call,
        version_call=lambda _: "fixture-cli",
        root=tmp_path,
    )
    assert len(calls) == 8 and result["reviewed_cases"] == 8
    assert result["claim_support"]["rate"] == result["citation_support"]["rate"] == 1
    assert result["answer_completeness"]["rate"] == 1
    assert result["budget"]["known_cost_usd"] == "0.080000"

    def unexpected_call(*args, **kwargs):
        pytest.fail("a complete review must resume without another model call")

    checkpoint = json.loads((out / "run.json").read_text())
    checkpoint["completed_case_sha256"] = []
    (out / "run.json").write_text(json.dumps(checkpoint) + "\n")
    resumed = run_tool["execute"](
        request_path,
        authorization_path,
        out,
        binary="claude-fixture",
        call=unexpected_call,
        version_call=lambda _: "fixture-cli",
        root=tmp_path,
    )
    assert resumed["reviewed_cases"] == 8
    assert len(json.loads((out / "run.json").read_text())["recovered_case_sha256"]) == 8

    def invalid_call(binary, model, effort, system, prompt, workdir, **kwargs):
        return "not-json", {
            "cost_usd": 0.02,
            "model_observed": model,
            "session_id": "invalid-session",
            "cli_capture_sha256": "f" * 64,
        }

    failed_out = tmp_path / "failed-review"
    with pytest.raises(RuntimeError, match="nonvalidated"):
        run_tool["execute"](
            request_path,
            authorization_path,
            failed_out,
            binary="claude-fixture",
            call=invalid_call,
            version_call=lambda _: "fixture-cli",
            root=tmp_path,
        )
    failed_budget = json.loads((failed_out / "budget.json").read_text())
    assert len(failed_budget["attempts"]) == 1 and failed_budget["attempts"][0]["cost_usd"] == "0.020000"
    with pytest.raises(ValueError, match="nonvalidated"):
        run_tool["execute"](
            request_path,
            authorization_path,
            failed_out,
            binary="claude-fixture",
            call=unexpected_call,
            version_call=lambda _: "fixture-cli",
            root=tmp_path,
        )

    structured_reply = {
        "claims": [{"claim_index": 0, "verdict": "supported", "reason": "The cited text matches."}],
        "citations": [{"citation_index": 0, "verdict": "supported", "reason": "The citation supports the claim."}],
        "completeness": {"verdict": "complete", "reason": "The answer addresses the question."},
    }

    def write_capture(path, *, model, cost, structured):
        path.parent.mkdir(parents=True, exist_ok=True)
        outer = {
            "subtype": "success",
            "is_error": False,
            "total_cost_usd": cost,
            "modelUsage": {model: {"inputTokens": 1, "outputTokens": 1}},
            "structured_output": structured,
            "result": "Human-readable summary.",
        }
        path.write_text(
            json.dumps({"returncode": 0, "stdout": json.dumps(outer), "stderr": ""}, ensure_ascii=False) + "\n"
        )
        path.chmod(0o600)
        return sha256_file(path)

    def old_adapter_call(binary, model, effort, system, prompt, workdir, **kwargs):
        capture_hash = write_capture(kwargs["capture_path"], model=model, cost=0.01, structured=structured_reply)
        return "Human-readable summary.", {
            "cost_usd": 0.01,
            "model_observed": model,
            "session_id": "old-adapter-session",
            "cli_capture_sha256": capture_hash,
            "json_schema_sha256": canonical_hash(kwargs["json_schema"]),
        }

    recovery_out = tmp_path / "schema-adapter-recovery"
    with pytest.raises(RuntimeError, match="nonvalidated"):
        run_tool["execute"](
            request_path,
            authorization_path,
            recovery_out,
            binary="claude-fixture",
            call=old_adapter_call,
            version_call=lambda _: "fixture-cli",
            root=tmp_path,
        )
    continued_calls = []

    def current_adapter_call(binary, model, effort, system, prompt, workdir, **kwargs):
        continued_calls.append(prompt)
        capture_hash = write_capture(kwargs["capture_path"], model=model, cost=0.01, structured=structured_reply)
        return json.dumps(structured_reply), {
            "cost_usd": 0.01,
            "model_observed": model,
            "session_id": f"current-adapter-{len(continued_calls)}",
            "cli_capture_sha256": capture_hash,
            "json_schema_sha256": canonical_hash(kwargs["json_schema"]),
        }

    recovered = run_tool["execute"](
        request_path,
        authorization_path,
        recovery_out,
        binary="claude-fixture",
        call=current_adapter_call,
        version_call=lambda _: "fixture-cli",
        root=tmp_path,
    )
    assert len(continued_calls) == 7 and recovered["reviewed_cases"] == 8
    recovered_budget = json.loads((recovery_out / "budget.json").read_text())
    assert recovered_budget["attempts"][0]["outcome"] == "ValueError"
    assert recovered_budget["attempts"][0]["reconciliation"]["outcome"] == "validated_reply"


def test_model_review_prompt_and_reply_keep_identity_outside_untrusted_output(case):
    prompt = model_review_prompt(case)
    assert case["query"] in prompt and case["evidence"][0]["text"] in prompt
    payload = judgment(case)
    reply = json.dumps({key: payload[key] for key in ("claims", "citations", "completeness")})
    verdict = model_review_verdict(
        case,
        reply,
        reviewer_id="reviewer-llm-answer-quality-01",
        model="claude-opus-5",
        prompt_sha256="c" * 64,
    )
    assert verdict["case_sha256"] == canonical_hash(case)
    assert verdict["reviewer"]["independent_second_human"] is False
    schema = model_review_schema(case)
    assert schema["required"] == ["claims", "citations", "completeness"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["claims"]["minItems"] == 1
    assert schema["properties"]["citations"]["minItems"] == 1
    assert "maxItems" not in schema["properties"]["claims"]
    assert "maximum" not in schema["properties"]["claims"]["items"]["properties"]["claim_index"]
    assert "minLength" not in schema["properties"]["completeness"]["properties"]["reason"]
    broken_schema = copy.deepcopy(schema)
    broken_schema["properties"]["claims"]["maxItems"] = 1
    with pytest.raises(ValueError, match="unsupported constraints"):
        validate_claude_review_schema(broken_schema)
    poisoned = json.loads(reply)
    poisoned["reviewer"] = {"kind": "human"}
    with pytest.raises(ValueError, match="unexpected fields"):
        model_review_verdict(
            case,
            json.dumps(poisoned),
            reviewer_id="reviewer-llm-answer-quality-01",
            model="claude-opus-5",
            prompt_sha256="c" * 64,
        )


def test_followup_request_binds_prior_valid_verdicts_and_reports_all_cases(case, tmp_path):
    prepare_tool = runpy.run_path(str(REPO / "evals/harness/tools/prepare_answer_review.py"))
    run_tool = runpy.run_path(str(REPO / "evals/harness/tools/run_answer_review.py"))
    rubric = tmp_path / "evals/answer_quality/RUBRIC.md"
    rubric.parent.mkdir(parents=True)
    rubric.write_text("fixed rubric\n")
    source = tmp_path / "runs/source"
    source.mkdir(parents=True)
    rows, cases = [], []
    for index in range(10):
        current = copy.deepcopy(case)
        current["sample_id"] = f"synthetic-{index}"
        current["sample_input_sha256"] = f"{index + 1:064x}"
        cases.append(current)
        answer = current["answer"]
        rows.append(
            {
                "sample_id": current["sample_id"],
                "sample_input_sha256": current["sample_input_sha256"],
                "outcome": "answered",
                "versions": current["versions"],
                "query": current["query"],
                "dept": current["dept"],
                "claims": [claim["text"] for claim in answer["claims"]],
                "cited_chunks": [citation["chunk_id"] for citation in answer["citations"]],
                "answer_review_input": save_snapshot(source, current),
            }
        )
    (source / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    for name in ("run_conditions.json", "dataset_binding.json", "scoring_binding.json"):
        (source / name).write_text("{}\n")

    reply = json.dumps(
        {
            "claims": [{"claim_index": 0, "verdict": "supported", "reason": "The cited text matches."}],
            "citations": [{"citation_index": 0, "verdict": "supported", "reason": "The citation supports the claim."}],
            "completeness": {"verdict": "complete", "reason": "The answer addresses the question."},
        }
    )
    prior = tmp_path / "reviews/prior"
    artifacts = prior / "call_artifacts"
    artifacts.mkdir(parents=True)
    verdicts = []
    attempts, budget_attempts = [], []
    for index in range(3):
        attempt_id = f"attempt-{index}"
        capture = artifacts / f"{attempt_id}.json"
        capture.write_text(json.dumps({"attempt": index}) + "\n")
        attempts.append(
            {
                "sample_id": cases[index]["sample_id"],
                "attempt_id": attempt_id,
                "outcome": "validated_reply" if index < 2 else "failed",
            }
        )
        budget_attempts.append(
            {
                "attempt_id": attempt_id,
                "status": "accounted",
                "cost_usd": "0.010000",
                "metadata": {"cli_capture_sha256": sha256_file(capture)},
            }
        )
        if index < 2:
            prompt_hash = hashlib.sha256(model_review_prompt(cases[index]).encode()).hexdigest()
            verdicts.append(
                model_review_verdict(
                    cases[index],
                    reply,
                    reviewer_id="reviewer-llm-answer-quality-01",
                    model="claude-opus-5",
                    prompt_sha256=prompt_hash,
                )
            )
    (prior / "verdicts.jsonl").write_text("".join(json.dumps(item) + "\n" for item in verdicts))
    (prior / "run.json").write_text(
        json.dumps(
            {
                "request_sha256": "a" * 64,
                "authorization_sha256": "b" * 64,
                "completed_case_sha256": [canonical_hash(item) for item in cases[:2]],
                "attempts": attempts,
            }
        )
        + "\n"
    )
    (prior / "budget.json").write_text(json.dumps({"attempts": budget_attempts}) + "\n")

    failed_history = tmp_path / "reviews/failed-history"
    failed_artifacts = failed_history / "call_artifacts"
    failed_artifacts.mkdir(parents=True)
    failed_capture = failed_artifacts / "failed-attempt.json"
    failed_capture.write_text('{"failed":true}\n')
    (failed_history / "run.json").write_text(
        json.dumps(
            {
                "request_sha256": "c" * 64,
                "authorization_sha256": "d" * 64,
                "completed_case_sha256": [],
                "attempts": [{"sample_id": "synthetic-2", "attempt_id": "failed-attempt", "outcome": "failed"}],
            }
        )
        + "\n"
    )
    (failed_history / "budget.json").write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "attempt_id": "failed-attempt",
                        "status": "accounted",
                        "cost_usd": "0.020000",
                        "metadata": {"cli_capture_sha256": sha256_file(failed_capture)},
                    }
                ]
            }
        )
        + "\n"
    )

    selected = [item["sample_id"] for item in cases[2:]]
    request = prepare_tool["prepare"](
        [source], root=tmp_path, selected_sample_ids=selected, prior_review=[prior, failed_history]
    )
    assert request["format"] == "answer-quality-review-request-v3"
    assert request["budget_request"]["max_attempts"] == 8
    assert request["budget_request"]["total_budget_usd"] == 2.4
    assert [item["sample_id"] for item in request["unselected_answered_cases"]] == [
        "synthetic-0",
        "synthetic-1",
    ]
    assert request["prior_reviews"][0]["known_cost_usd"] == "0.030000"
    assert request["prior_reviews"][1]["known_cost_usd"] == "0.020000"
    assert request["prior_reviews"][1]["verdicts_sha256"] is None
    request_path = tmp_path / "followup-request.json"
    request_path.write_text(json.dumps(request) + "\n")
    loaded, loaded_cases = run_tool["load_bound_request"](request_path, root=tmp_path)
    assert loaded == request and len(loaded_cases) == 10

    budget = request["budget_request"]
    authorization = {
        "format": run_tool["AUTH_FORMAT"],
        "approved_by": "project-owner",
        "approval_quote": "fixture follow-up approval",
        "request_sha256": sha256_file(request_path),
        "model": request["reviewer"]["model"],
        "reasoning_effort": request["reviewer"]["reasoning_effort"],
        "total_budget_usd": budget["total_budget_usd"],
        "reservation_usd_per_call": budget["reservation_usd_per_call"],
        "cli_stop_usd_per_call": budget["cli_stop_usd_per_call"],
        "max_attempts": budget["max_attempts"],
        "stop_on_nonvalidated_attempt": True,
        "automatic_retry": False,
        "authorized_sample_ids": selected,
    }
    authorization_path = tmp_path / "followup-authorization.json"
    authorization_path.write_text(json.dumps(authorization) + "\n")
    calls = []

    def fake_call(binary, model, effort, system, prompt, workdir, **kwargs):
        calls.append(prompt)
        return reply, {
            "cost_usd": 0.01,
            "model_observed": model,
            "session_id": f"followup-{len(calls)}",
            "cli_capture_sha256": f"{len(calls):064x}",
            "json_schema_sha256": canonical_hash(kwargs["json_schema"]),
        }

    result = run_tool["execute"](
        request_path,
        authorization_path,
        tmp_path / "reviews/followup",
        binary="claude-fixture",
        call=fake_call,
        version_call=lambda _: "fixture-cli",
        root=tmp_path,
    )
    assert len(calls) == 8
    assert result["reviewed_cases"] == 10 and result["prior_reviewed_cases"] == 2
    assert result["claim_support"]["denominator"] == 10
    assert result["claim_support"]["rate"] == 1
    assert result["budget"]["known_cost_usd"] == "0.080000"

    capture = artifacts / "attempt-2.json"
    capture.write_text("tampered\n")
    with pytest.raises(ValueError, match="prior review"):
        run_tool["load_bound_request"](request_path, root=tmp_path)
