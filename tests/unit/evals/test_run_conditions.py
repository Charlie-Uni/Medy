"""A resumed result must have one execution identity; costs count every recorded attempt."""

import copy
import json

import pytest

from medops.core.canonical import canonical_hash
from medops.evals import run_conditions as rc


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "repo"
    (root / "src/medops").mkdir(parents=True)
    runner = root / "runner.py"
    runner.write_text("pass\n")
    (root / "src/medops/runtime.py").write_text("VERSION=1\n")
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\n')
    (root / "requirements.lock").write_text("fixture==1\n")
    samples = [{"sample_id": "test-1", "query": "fixture?", "expected": {"answer": "a"}}]
    kwargs = dict(
        root=root,
        runner=runner,
        samples=samples,
        versions={"model": "test"},
        facts={"plane": {"sha256": "fact"}},
        configuration={"as_of": "2026-10-08"},
        inputs={"mapping_sha256": "mapping"},
    )
    return kwargs, rc.make_conditions(**kwargs)


def row(conditions, **changes):
    return {
        "attempt_id": "first",
        "run_conditions_sha256": canonical_hash(conditions),
        "sample_id": "test-1",
        "sample_input_sha256": conditions["sample_plan"][0]["sha256"],
        "versions": conditions["versions"],
        "cost_usd": 0.1,
        "model_calls": 2,
        "reason_codes": [],
        **changes,
    }


def test_identical_resume_is_accepted_without_rewriting_the_binding(tmp_path, prepared):
    _, conditions = prepared
    assert rc.bind_conditions(tmp_path, conditions) == canonical_hash(conditions)
    original = (tmp_path / "run_conditions.json").read_bytes()
    assert rc.bind_conditions(tmp_path, conditions) == canonical_hash(conditions)
    assert (tmp_path / "run_conditions.json").read_bytes() == original
    rc.validate_attempts([row(conditions)], conditions)


@pytest.mark.parametrize(
    "section", ["configuration", "versions", "facts", "inputs", "sample_plan", "source", "environment"]
)
def test_changed_conditions_refuse_resume_and_preserve_old_file(tmp_path, prepared, section):
    _, conditions = prepared
    rc.bind_conditions(tmp_path, conditions)
    original = (tmp_path / "run_conditions.json").read_bytes()
    changed = copy.deepcopy(conditions)
    changed[section] = {"changed": True}
    with pytest.raises(ValueError, match=f"changed.*{section}"):
        rc.bind_conditions(tmp_path, changed)
    assert (tmp_path / "run_conditions.json").read_bytes() == original


def test_actual_source_edit_and_same_query_changed_expectation_change_identity(prepared):
    kwargs, before = prepared
    runtime = kwargs["root"] / "src/medops/runtime.py"
    runtime.write_text("VERSION=2\n")
    after = rc.make_conditions(**kwargs)
    assert after["source"]["sha256"] != before["source"]["sha256"]
    kwargs["samples"][0]["expected"]["answer"] = "b"
    assert rc.make_conditions(**kwargs)["sample_plan"] != after["sample_plan"]


def test_legacy_rows_cannot_be_retroactively_bound(tmp_path, prepared):
    (tmp_path / "rows.jsonl").write_text('{"sample_id":"test-1"}\n')
    with pytest.raises(ValueError, match="no runtime/fact binding"):
        rc.bind_conditions(tmp_path, prepared[1])
    assert not (tmp_path / "run_conditions.json").exists()


def test_binding_tampering_is_detected(tmp_path, prepared):
    rc.bind_conditions(tmp_path, prepared[1])
    path = tmp_path / "run_conditions.json"
    data = json.loads(path.read_text())
    data["conditions"]["configuration"] = {"bad": True}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="file hash mismatch"):
        rc.bind_conditions(tmp_path, prepared[1])


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_id": "unknown"},
        {"sample_input_sha256": "wrong"},
        {"versions": {}},
        {"run_conditions_sha256": "wrong"},
        {"attempt_id": None},
        {"cost_usd": float("nan")},
        {"cost_usd": -1},
        {"model_calls": True},
    ],
)
def test_bad_rows_are_rejected_before_resuming(prepared, changes):
    conditions = prepared[1]
    with pytest.raises(ValueError):
        rc.validate_attempts([row(conditions, **changes)], conditions)


def test_duplicate_attempts_are_not_double_counted_as_an_accepted_run(prepared):
    conditions = prepared[1]
    with pytest.raises(ValueError, match="duplicate attempt"):
        rc.validate_attempts([row(conditions), row(conditions)], conditions)


def test_failed_attempt_fees_survive_a_successful_retry(prepared):
    conditions = prepared[1]
    rows = [row(conditions, reason_codes=["system_failure"]), row(conditions, attempt_id="retry", cost_usd=0.2)]
    rc.validate_attempts(rows, conditions)
    accounting = rc.attempt_accounting(rows)
    assert accounting["cost_usd"] == 0.3 and accounting["model_calls"] == 4
    assert accounting["recorded_attempts"] == 2 and accounting["system_failure_attempts"] == 1


@pytest.mark.parametrize("samples", [[], [{"sample_id": "x"}, {"sample_id": "x"}]])
def test_empty_and_duplicate_measurement_plans_are_rejected(prepared, samples):
    kwargs, _ = prepared
    with pytest.raises(ValueError, match="nonempty unique"):
        rc.make_conditions(**{**kwargs, "samples": samples})


def test_fact_guard_checks_on_interval_and_forces_a_final_check():
    now = [0.0]
    observed = {"sha256": "same"}
    calls = []

    def capture():
        calls.append(now[0])
        return dict(observed)

    guard = rc.FactGuard(
        {"production": {"sha256": "same"}},
        {"production": capture},
        interval_s=10,
        clock=lambda: now[0],
    )
    guard.check()
    now[0] = 5
    guard.check()
    assert calls == [0.0]
    guard.check(force=True)
    assert calls == [0.0, 5]
    observed["sha256"] = "changed"
    now[0] = 15
    with pytest.raises(rc.FactDriftError, match="production.*new output directory"):
        guard.check()


@pytest.mark.parametrize(
    ("expected", "capture", "interval"),
    [({}, {}, 10), ({"a": {}}, {}, 10), ({"a": {}}, {"a": lambda: {}}, 0)],
)
def test_fact_guard_rejects_an_invalid_plan(expected, capture, interval):
    with pytest.raises(ValueError, match="same nonempty planes"):
        rc.FactGuard(expected, capture, interval_s=interval)


def test_replay_attempts_bind_each_row_to_its_actual_arm(prepared):
    kwargs, _ = prepared
    conditions = rc.make_conditions(
        **{
            **kwargs,
            "versions": {"baseline": {"retrieval": "a"}, "candidate": {"retrieval": "b"}},
        }
    )
    common = {
        "attempt_id": "attempt-1",
        "run_conditions_sha256": canonical_hash(conditions),
        "replay_id": "test-1",
        "sample_input_sha256": conditions["sample_plan"][0]["sha256"],
        "arm": "candidate",
        "run": 1,
        "cost_usd": 0.1,
        "model_calls": 2,
    }
    rc.validate_replay_attempts([{**common, "versions": conditions["versions"]["candidate"]}], conditions)
    with pytest.raises(ValueError, match="replay row runtime"):
        rc.validate_replay_attempts([{**common, "versions": conditions["versions"]["baseline"]}], conditions)
    first = {**common, "versions": conditions["versions"]["candidate"]}
    retry = {**first, "attempt_id": "attempt-2"}
    with pytest.raises(ValueError, match="after a completed attempt"):
        rc.validate_replay_attempts([first, retry], conditions)
    rc.validate_replay_attempts(
        [{**first, "reason_codes": ["system_failure"]}, retry],
        conditions,
    )
