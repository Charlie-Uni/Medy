"""PUBLIC offline loop images: reconstruction is not permission or provider replay."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import timedelta
from uuid import uuid4

import pytest

from medops.application.agent_loop_state import (
    MAX_LOOP_STATE_BYTES,
    decode_loop_state,
    encode_loop_state,
    rebuild_loop_state,
)
from medops.core.canonical import canonical_json
from medops.infrastructure.llm.gateway import ModelTimeout
from tests.support.pv_agent import CANARY, NOW, proposal
from tests.support.pv_loop import choose_from_observation, setup_loop, terminal
from tests.support.pv_tools import parent


def execute(script=None, *, choose=None, fail=None):
    current, loop, driver, fake, meter = setup_loop(script, choose=choose)
    driver.fail_phase = fail
    with parent():
        result = loop.run(current)
    return result, driver, fake, meter


@pytest.fixture
def trajectory():
    return execute(choose=choose_from_observation)


def rebuild(state):
    return rebuild_loop_state(state, expected_run=state.run, config=state.config)


def test_all_images_round_trip_and_reconstruct_exact_next_planning_request(trajectory):
    result, driver, fake, meter = trajectory
    counts = (len(fake.calls), len(meter.receipts), len(driver.actions))
    for index, event in enumerate(driver.events):
        image = decode_loop_state(encode_loop_state(event.state))
        assert image == event.state and image.run == event.run
        rebuilt = rebuild(image)
        assert rebuilt.progress.snapshot() == event.progress
        if event.phase == "tool_committed":
            following = driver.events[index + 1]
            assert following.phase == "decision_started"
            assert rebuilt.blocked_reason is None
            request = rebuilt.board.request(following.run, image.config)
            assert request.model_dump(exclude={"call"}) == following.request.model_dump(exclude={"call"})
        elif event.phase in {"decision_started", "planning_returned"}:
            assert rebuilt.blocked_reason == "unsupported_recovery"
    final = rebuild(driver.events[-1].state)
    assert final.evidence_registry == result.evidence_registry and final.outcomes == result.outcomes
    assert final.blocked_reason == "completed" and result.run.status == "running"
    assert counts == (len(fake.calls), len(meter.receipts), len(driver.actions))


@pytest.mark.parametrize("mode", ["read", "extract"])
def test_neighbor_reads_and_extraction_are_reconstructed_without_rerunning_tools(mode):
    def choose(state):
        if mode == "extract" and state["last_observation"]["kind"] is None:
            return proposal("extract_ae")
        if mode == "read" and state["last_observation"]["action"] == "search_documents":
            data = proposal("read_evidence")
            data["proposal"].update(handle=state["evidence"][-1]["handle"], region="current")
            return data
        return choose_from_observation(state) if state["last_observation"]["action"] != "extract_ae" else proposal()

    script = (
        {"skill:ae_extraction": [{"elements": [{"kind": "event", "value": "an event", "quote": "reported an event"}]}]}
        if mode == "extract"
        else None
    )
    result, driver, fake, _ = execute(script, choose=choose)
    calls = len(fake.calls)
    image = decode_loop_state(encode_loop_state(driver.events[-1].state))
    rebuilt = rebuild(image)
    assert rebuilt.outcomes == result.outcomes and len(fake.calls) == calls
    projected = json.loads(rebuilt.board.request(image.run, image.config).messages[1].content)
    assert projected["extracted_unverified"] is not None if mode == "extract" else projected["evidence"]


def test_rejected_decision_preserves_count_and_resets_progress():
    result, driver, _, _ = execute({"agent_plan": [proposal(), "bad JSON", proposal(), terminal()]})
    assert result.run.decisions_consumed == 4
    event = next(e for e in driver.events if e.phase == "proposal_rejected")
    image = decode_loop_state(encode_loop_state(event.state))
    restored = rebuild(image)
    assert restored.progress.snapshot().consecutive == 0
    assert restored.board.last_kind == "invalid_action" and len(restored.evidence_registry) == 1
    assert len(image.history) == 2 and image.history[-1].decision_index == 2
    final = rebuild(driver.events[-1].state)
    assert final.progress.snapshot().consecutive == 1  # rejection interrupts the repeated search


def test_repeat_stop_is_derived_at_tool_commit_before_handoff():
    result, driver, _, _ = execute({"agent_plan": [proposal(), proposal(), terminal()]})
    assert result.reason == "no_progress"
    event = [e for e in driver.events if e.phase == "tool_committed"][-1]
    rebuilt = rebuild(decode_loop_state(encode_loop_state(event.state)))
    assert rebuilt.progress.snapshot().consecutive == 2 and rebuilt.blocked_reason == "no_progress"


def test_step_limit_survives_eight_rejections():
    result, driver, fake, _ = execute({"agent_plan": ["invalid"] * 8})
    assert result.reason == "step_limit" and len(fake.calls) == 8
    rejected = [e for e in driver.events if e.phase == "proposal_rejected"][-1].state
    assert len(rejected.history) == 8 and rebuild(rejected).blocked_reason == "step_limit"
    assert rebuild(decode_loop_state(encode_loop_state(driver.events[-1].state))).blocked_reason == "step_limit"


@pytest.mark.parametrize(
    "action,reason", [("clarify", "clarification_required"), ("escalate", "insufficient_evidence")]
)
def test_terminal_request_is_sealed_as_handoff_not_resume(action, reason):
    result, driver, fake, _ = execute({"agent_plan": [terminal(action)]})
    image = decode_loop_state(encode_loop_state(driver.events[-1].state))
    assert image.terminal_request == result.terminal_request and rebuild(image).blocked_reason == reason
    assert len(fake.calls) == 1 and image.run.terminal is None


def test_uncertain_planning_failure_preserves_consumption_without_replay():
    result, driver, fake, meter = execute({"agent_plan": [ModelTimeout(CANARY)]})
    image = decode_loop_state(encode_loop_state(driver.events[-1].state))
    assert image.run.budget == result.run.budget and image.run.budget.accounted_tokens > 0
    assert image.run.decisions_consumed == 1 and not image.history
    assert rebuild(image).blocked_reason == "timeout" and len(fake.calls) == len(meter.receipts) == 1


def test_checkpoint_failure_hands_off_committed_tool_state_and_stops():
    result, driver, fake, _ = execute({"agent_plan": [proposal(), terminal()]}, fail="tool_committed")
    assert result.reason == "audit_failure" and len(fake.calls) == 1
    image = decode_loop_state(encode_loop_state(driver.events[-1].state))
    assert len(image.history) == 1 and rebuild(image).evidence_registry == result.evidence_registry
    assert rebuild(image).blocked_reason == "audit_failure"


def test_projection_failure_never_saves_a_half_updated_board_or_progress(monkeypatch):
    from medops.application.agent_planning import PlanningBoard

    observe = PlanningBoard.observe

    def fail_after_mutating(self, action, outcome):
        observe(self, action, outcome)
        raise ValueError(CANARY)

    monkeypatch.setattr(PlanningBoard, "observe", fail_after_mutating)
    result, driver, fake, _ = execute({"agent_plan": [proposal(), terminal()]})
    assert result.reason == "audit_failure" and len(fake.calls) == 1
    image = driver.events[-1].state
    assert not image.history and not result.evidence_registry and not result.outcomes
    assert driver.events[-1].progress.consecutive == 0
    # No completed observation is replayed; the separately committed tool/audit
    # must be reconciled by the future durable driver, not re-executed here.
    assert rebuild(image).blocked_reason == "audit_failure" and len(driver.audits) == 1


def test_refused_old_run_emits_no_replacement_image():
    current, loop, driver, fake, _ = setup_loop({"agent_plan": [terminal()]})
    with parent():
        result = loop.run(current.model_copy(update={"decisions_consumed": 1}))
    assert result.reason == "unsupported_recovery" and not fake.calls
    assert driver.events[-1].state is None and driver.events[-1].progress is None


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "run",
        "config",
        "phase",
        "captured_at",
        "decision_id",
        "history",
        "stop_reason",
        "terminal_request",
        "terminal_admitted_at",
    ],
)
def test_missing_fields_never_default_to_fresh_state(trajectory, field):
    data = trajectory[1].events[-1].state.model_dump(mode="json")
    del data[field]
    with pytest.raises(ValueError, match="^invalid_agent_loop_state$"):
        decode_loop_state(canonical_json(data).encode())


def change(data, kind):
    if kind == "duplicate":
        data["history"][1]["decision_id"] = data["history"][0]["decision_id"]
    elif kind == "gap":
        data["history"][0]["decision_index"] = 2
    elif kind == "rewind":
        data["run"]["decisions_consumed"] = 1
    elif kind == "budget":
        data["run"]["budget"]["accounted_tokens"] = 0
    elif kind == "binding":
        data["history"][0]["action"]["binding"]["run_id"] = str(uuid4())
    elif kind == "text":
        data["history"][0]["outcome"]["payload"]["matches"][0]["text"] = CANARY
    elif kind == "receipt":
        for h in data["history"]:
            h["outcome"]["call_receipt_ids"] = ["PUBLIC-duplicate-receipt"]
    elif kind == "time":
        data["history"][0]["observed_at"] = (NOW + timedelta(seconds=126)).isoformat()
    elif kind == "action_id":
        data["history"][0]["action"]["action_id"] = str(uuid4())
    elif kind == "erased_terminal":
        data["terminal_request"] = None
        data["terminal_admitted_at"] = None
    elif kind == "terminal_handle":
        data["terminal_request"]["proposal"]["draft"]["guideline_claims"] = [
            {"requirement_id": "guideline", "text": CANARY, "evidence_handles": [str(uuid4())]}
        ]
    elif kind == "past_capture":
        data["captured_at"] = (NOW - timedelta(seconds=1)).isoformat()
    elif kind == "version":
        data["version"] = "future"
    elif kind == "tool_version":
        data["run"]["context"]["versions"]["tool_contract_sha256"] = "f" * 64
    elif kind == "planner_version":
        data["run"]["context"]["versions"]["planning_prompt_sha256"] = "f" * 64
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate",
        "gap",
        "rewind",
        "budget",
        "binding",
        "text",
        "receipt",
        "time",
        "action_id",
        "erased_terminal",
        "terminal_handle",
        "past_capture",
        "version",
        "tool_version",
        "planner_version",
    ],
)
def test_corruption_rejected_with_fixed_error_without_private_bodies(trajectory, kind):
    data = trajectory[1].events[-1].state.model_dump(mode="json")
    change(data, kind)
    with pytest.raises(ValueError) as caught:
        decode_loop_state(canonical_json(data).encode())
    assert str(caught.value) == "invalid_agent_loop_state" and CANARY not in str(caught.value)


@pytest.mark.parametrize(
    "body", [b"", b"{", b'{"version":1,"version":2}', b"x" * (MAX_LOOP_STATE_BYTES + 1), b"\xff", b"[" * 1500]
)
def test_bad_or_oversize_json_fails_closed(body):
    with pytest.raises(ValueError, match="^invalid_agent_loop_state$"):
        decode_loop_state(body)


def test_expected_run_and_planner_config_are_not_taken_from_an_untrusted_image(trajectory):
    state = trajectory[1].events[2].state
    with pytest.raises(ValueError):
        rebuild_loop_state(
            state, expected_run=state.run.model_copy(update={"decisions_consumed": 0}), config=state.config
        )
    with pytest.raises(ValueError):
        rebuild_loop_state(
            state, expected_run=state.run, config=state.config.model_copy(update={"max_output_tokens": 1})
        )


def test_new_process_reconstructs_exact_request_and_progress_from_restricted_bytes(trajectory):
    state = trajectory[1].events[2].state
    rebuilt = rebuild(state)
    projection = canonical_json(
        {
            "request": rebuilt.board.request(state.run, state.config).model_dump(mode="json"),
            "progress": rebuilt.progress.snapshot().__dict__,
        }
    ).encode()
    script = """import sys,hashlib
from medops.application.agent_loop_state import decode_loop_state,rebuild_loop_state
from medops.core.canonical import canonical_json
s=decode_loop_state(sys.stdin.buffer.read());r=rebuild_loop_state(s,expected_run=s.run,config=s.config)
p=canonical_json({'request':r.board.request(s.run,s.config).model_dump(mode='json'),'progress':r.progress.snapshot().__dict__}).encode()
print(hashlib.sha256(p).hexdigest())
"""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    process = subprocess.run(
        [sys.executable, "-c", script], input=encode_loop_state(state), capture_output=True, env=env, timeout=30
    )
    assert process.returncode == 0, process.stderr.decode()
    assert process.stdout.decode().strip() == hashlib.sha256(projection).hexdigest()
