"""Prevent reusing an old reviewer result after changing the prompt or a sample."""

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

PROMPT = "Review exactly the supplied source and query.\n"
PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()

TOOLING = Path(__file__).resolve().parents[3] / "evals/probe/precise_clause/drafts/v1/tooling"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLING))
    return importlib.import_module("run_codex_review"), importlib.import_module("assemble")


def review_fixture(runner):
    records = [{"sample_id": "pc-0001", "query": "original question", "page_text": "source text"}]
    run = {
        "review_prompt_sha256": PROMPT_HASH,
        "model": "test-model",
        "reasoning_effort_requested": "high",
        "sample_input_sha256": {r["sample_id"]: runner.record_hash(r) for r in records},
        "chunks": [
            {
                "sample_ids": ["pc-0001"],
                "model": "test-model",
                "reasoning_effort": "high",
                "returncode": 0,
                "session_id": "synthetic-session",
                "prompt_sha256": runner.actual_prompt_hash(PROMPT, records),
            }
        ],
    }
    verdicts = {
        "pc-0001": {
            "sample_id": "pc-0001",
            "verdict": "agree",
            "items": dict.fromkeys(runner.ITEM_KEYS, "ok"),
            "reason": "",
            "suggestion": "",
        }
    }
    return records, run, verdicts


def test_completed_review_can_be_verified(modules):
    runner, assembler = modules
    records, run, verdicts = review_fixture(runner)
    assembler.verify_batch_run(run, records, verdicts, PROMPT_HASH, "test-model", PROMPT)


@pytest.mark.parametrize("field", ["query", "page_text"])
def test_changed_sample_invalidates_review(modules, field):
    runner, assembler = modules
    records, run, verdicts = review_fixture(runner)
    records[0][field] = "changed"
    with pytest.raises(ValueError, match="sample_input_sha256"):
        assembler.verify_batch_run(run, records, verdicts, PROMPT_HASH, "test-model", PROMPT)


@pytest.mark.parametrize("field,value", [("review_prompt_sha256", "c" * 64), ("reasoning_effort_requested", "none")])
def test_changed_policy_or_effort_invalidates_review(modules, field, value):
    runner, assembler = modules
    records, run, verdicts = review_fixture(runner)
    run[field] = value
    with pytest.raises(ValueError, match=field):
        assembler.verify_batch_run(run, records, verdicts, PROMPT_HASH, "test-model", PROMPT)


def test_partial_review_cannot_be_assembled(modules):
    runner, assembler = modules
    records, run, verdicts = review_fixture(runner)
    run["chunks"] = []
    with pytest.raises(ValueError, match="incomplete"):
        assembler.verify_batch_run(run, records, verdicts, PROMPT_HASH, "test-model", PROMPT)


def test_observed_effort_must_match_request(modules):
    runner, assembler = modules
    records, run, verdicts = review_fixture(runner)
    run["chunks"][0]["reasoning_effort"] = "none"
    with pytest.raises(ValueError, match="required model and effort"):
        assembler.verify_batch_run(run, records, verdicts, PROMPT_HASH, "test-model", PROMPT)


def test_reviewer_cannot_agree_with_an_issue(modules):
    runner, _ = modules
    _, _, verdicts = review_fixture(runner)
    verdict = copy.deepcopy(verdicts["pc-0001"])
    verdict["items"]["query"] = "issue"
    with pytest.raises(ValueError, match="agree with an issue"):
        runner.parse_reply(json.dumps(verdict), ["pc-0001"])


@pytest.mark.parametrize("unexpected", [{"page_text": "full source page"}, {"metadata": "unrecognized"}])
def test_reviewer_cannot_add_source_text_or_unknown_fields(modules, unexpected):
    runner, _ = modules
    _, _, verdicts = review_fixture(runner)
    with pytest.raises(ValueError, match="allowed verdict fields"):
        runner.parse_reply(json.dumps({**verdicts["pc-0001"], **unexpected}), ["pc-0001"])


def test_reviewer_reply_must_be_an_object(modules):
    runner, _ = modules
    with pytest.raises(ValueError, match="allowed verdict fields"):
        runner.parse_reply("[]", ["pc-0001"])


def test_pack_rejects_silently_omitting_a_second_gold(modules, tmp_path):
    packer = importlib.import_module("review_pack")
    with pytest.raises(ValueError, match="exactly one gold"):
        packer.pack_samples([{"sample_id": "pc-0001", "required_gold_evidence": [{}, {}]}], {}, tmp_path)


def two_record_fixture(runner):
    records, run, verdicts = review_fixture(runner)
    records.append({"sample_id": "pc-0002", "query": "another question", "page_text": "second source"})
    verdicts["pc-0002"] = {**verdicts["pc-0001"], "sample_id": "pc-0002"}
    run["sample_input_sha256"] = {r["sample_id"]: runner.record_hash(r) for r in records}
    run["chunks"][0]["sample_ids"] = [r["sample_id"] for r in records]
    run["chunks"][0]["prompt_sha256"] = runner.actual_prompt_hash(PROMPT, records)
    return records, run, verdicts


def test_selected_change_permitted_but_unselected_change_rejected(modules):
    runner, _ = modules
    records, run, _ = two_record_fixture(runner)
    records[0]["query"] = "changed"
    runner.validate_resume(run, PROMPT_HASH, "test-model", "high", records, {"pc-0001"})
    records[1]["query"] = "also changed"
    with pytest.raises(ValueError, match="sample_input_sha256"):
        runner.validate_resume(run, PROMPT_HASH, "test-model", "high", records, {"pc-0001"})


@pytest.mark.parametrize("only", [set(), {"unknown"}])
def test_empty_or_unknown_selection_rejected(modules, only):
    runner, _ = modules
    records, run, _ = review_fixture(runner)
    with pytest.raises(ValueError, match="--only"):
        runner.validate_resume(run, PROMPT_HASH, "test-model", "high", records, only)


@pytest.mark.parametrize("version", [1, 2])
def test_changing_global_hashes_cannot_launder_old_result(modules, tmp_path, version):
    runner, _ = modules
    records, run, verdicts = review_fixture(runner)
    if version == 2:
        run = runner.migrate_legacy(run, records, verdicts, PROMPT, tmp_path)
    records[0]["query"] = "silently edited"
    run["sample_input_sha256"]["pc-0001"] = runner.record_hash(records[0])
    with pytest.raises(ValueError, match="prompt_sha256|sample_input_sha256"):
        runner.verify_review(run, records, verdicts, PROMPT, "test-model", "high", input_dir=tmp_path)


def test_mixed_chunk_preserves_unchanged_result_but_invalidates_selected(modules, tmp_path):
    runner, assembler = modules
    records, run, verdicts = two_record_fixture(runner)
    run = runner.migrate_legacy(run, records, verdicts, PROMPT, tmp_path)
    records[0]["query"] = "new question"
    pending = runner.start_targeted_review(run, records, {"pc-0001"})
    assert pending == records[:1]
    assert set(runner.current_verdicts(run)) == {"pc-0002"}
    assert len(run["chunks"][0]["verdicts"]) == 2  # Full previous verdict history survives.
    assert "source text" not in json.dumps(run)  # Source page text is never tracked in run metadata.
    runner.verify_review(
        run,
        records,
        runner.current_verdicts(run),
        PROMPT,
        "test-model",
        "high",
        input_dir=tmp_path,
        require_complete=False,
    )
    with pytest.raises(ValueError, match="incomplete"):
        assembler.verify_batch_run(
            run, records, runner.current_verdicts(run), PROMPT_HASH, "test-model", PROMPT, tmp_path
        )
    with pytest.raises(ValueError, match="coverage or content mismatch"):
        runner.verify_review(
            run, records, verdicts, PROMPT, "test-model", "high", input_dir=tmp_path, require_complete=False
        )


def test_wrong_archived_prompt_or_verdict_is_rejected(modules, tmp_path):
    runner, _ = modules
    records, run, verdicts = two_record_fixture(runner)
    run = runner.migrate_legacy(run, records, verdicts, PROMPT, tmp_path)
    run["chunks"][0]["prompt_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="provenance"):
        runner.verify_review(run, records, verdicts, PROMPT, "test-model", "high", input_dir=tmp_path)
    run = runner.migrate_legacy(two_record_fixture(runner)[1], records, verdicts, PROMPT, tmp_path)
    run["chunks"][0]["verdicts"][0]["reason"] = "changed conclusion"
    with pytest.raises(ValueError, match="provenance"):
        runner.verify_review(run, records, verdicts, PROMPT, "test-model", "high", input_dir=tmp_path)


def test_old_agreement_cannot_hide_a_later_dispute(modules, tmp_path):
    runner, _ = modules
    records, legacy, verdicts = review_fixture(runner)
    run = runner.migrate_legacy(legacy, records, verdicts, PROMPT, tmp_path)
    later = copy.deepcopy(run["chunks"][0])
    later["session_id"] = "later-synthetic-session"
    later["verdicts"][0]["verdict"] = "dispute"
    later["verdicts"][0]["items"]["key_text"] = "issue"
    later["verdicts"][0]["reason"] = "Later review found a key issue."
    run["chunks"].append(later)
    # Old latest and the mirror agree with each other, but must not conceal the later call.
    with pytest.raises(ValueError, match="last recorded invocation"):
        runner.verify_review(run, records, verdicts, PROMPT, "test-model", "high", input_dir=tmp_path)


def test_resolution_cannot_apply_to_a_different_input_or_verdict(modules):
    runner, assembler = modules
    records, _, verdicts = review_fixture(runner)
    verdict = verdicts["pc-0001"]
    resolution = {
        "resolution_note": "owner decided",
        "sample_input_sha256": runner.record_hash(records[0]),
        "verdict_sha256": runner.record_hash(verdict),
    }
    assembler.verify_resolution(resolution, records[0], verdict)
    with pytest.raises(ValueError, match="exact current"):
        assembler.verify_resolution(resolution, {**records[0], "query": "different"}, verdict)
    with pytest.raises(ValueError, match="exact current"):
        assembler.verify_resolution(resolution, records[0], {**verdict, "reason": "a new problem"})


def setup_cli(monkeypatch, tmp_path, runner):
    review = tmp_path / "review"
    review.mkdir()
    v1 = tmp_path / "v1"
    v1.mkdir()
    (v1 / "review_prompt.md").write_text(PROMPT)
    records, run, verdicts = two_record_fixture(runner)
    (review / "run_MA.json").write_text(json.dumps(run))
    (review / "verdicts_MA.jsonl").write_text("\n".join(json.dumps(v) for v in verdicts.values()))
    previous = review / "input_previous.jsonl"
    previous.write_text("\n".join(json.dumps(r) for r in records))
    for record in records:
        record["query"] += " revised"
    (review / "input_MA.jsonl").write_text("\n".join(json.dumps(r) for r in records))
    monkeypatch.setattr(runner, "REVIEW", review)
    monkeypatch.setattr(runner, "V1", v1)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_codex_review.py",
            "MA",
            "--model",
            "test-model",
            "--chunk",
            "1",
            "--previous-input",
            str(previous),
            "--only",
            "pc-0001",
            "pc-0002",
        ],
    )
    return review, records, verdicts


def test_failed_rerun_invalidates_old_results_and_resumes_only_pending(modules, monkeypatch, tmp_path):
    runner, _ = modules
    review, records, verdicts = setup_cli(monkeypatch, tmp_path, runner)
    calls = []

    def mock_run(codex, model, effort, prompt, workdir):
        sid = "pc-0001" if "pc-0001" in prompt else "pc-0002"
        calls.append(sid)
        state = json.loads((review / "run_MA.json").read_text())
        assert sid not in state["latest"]
        if len(calls) == 2:
            raise RuntimeError("synthetic model failure")
        return json.dumps(verdicts[sid]), {
            "model": model,
            "reasoning_effort": effort,
            "returncode": 0,
            "session_id": "new-session",
            "tokens_used": "12",
        }

    monkeypatch.setattr(runner, "run_chunk", mock_run)
    with pytest.raises(RuntimeError, match="synthetic model failure"):
        runner.main()
    state = json.loads((review / "run_MA.json").read_text())
    assert set(state["latest"]) == {"pc-0001"}
    assert state["active_review"]["pending_ids"] == ["pc-0002"]
    runner.main()
    assert calls == ["pc-0001", "pc-0002", "pc-0002"]
    state = json.loads((review / "run_MA.json").read_text())
    assert state["active_review"] is None
    assert len(state["chunks"]) == 3
    assert state["latest"]["pc-0001"]["chunk_index"] == 1
    assert state["latest"]["pc-0002"]["chunk_index"] == 2
    runner.verify_review(state, records, runner.current_verdicts(state), PROMPT, "test-model", "high", input_dir=review)


def test_crash_between_invalidation_and_jsonl_write_is_recoverable(modules, monkeypatch, tmp_path):
    runner, _ = modules
    review, records, verdicts = setup_cli(monkeypatch, tmp_path, runner)
    atomic_write = runner.atomic_write

    def fail_mirror(path, text):
        if path.name == "verdicts_MA.jsonl":
            raise OSError("synthetic crash")
        atomic_write(path, text)

    monkeypatch.setattr(runner, "atomic_write", fail_mirror)
    with pytest.raises(OSError, match="synthetic crash"):
        runner.main()
    state = json.loads((review / "run_MA.json").read_text())
    assert state["latest"] == {}
    with pytest.raises(ValueError, match="coverage or content mismatch"):
        runner.verify_review(
            state, records, verdicts, PROMPT, "test-model", "high", input_dir=review, require_complete=False
        )
    monkeypatch.setattr(runner, "atomic_write", atomic_write)
    monkeypatch.setattr(
        runner,
        "run_chunk",
        lambda codex, model, effort, prompt, workdir: (
            json.dumps(verdicts["pc-0001" if "pc-0001" in prompt else "pc-0002"]),
            {"model": model, "reasoning_effort": effort, "returncode": 0, "session_id": "new", "tokens_used": "1"},
        ),
    )
    runner.main()
    state = json.loads((review / "run_MA.json").read_text())
    runner.verify_review(state, records, runner.current_verdicts(state), PROMPT, "test-model", "high", input_dir=review)
