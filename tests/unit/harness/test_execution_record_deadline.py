"""Execution binding I/O must consume the same execution time allowance as model work."""

import time
from dataclasses import replace

import pytest

from medops.core.deadline import CURRENT_DEADLINE, DeadlineExceeded
from medops.harness import execution_record
from medops.harness.runtime import run_ask
from medops.infrastructure.llm.execution_budget import default_limits, execution_scope
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.harness import FakeRetrieval, make_deps, state
from tests.support.skill_task import SkillEnv


@pytest.mark.parametrize("entry", ["ask", "skill"])
def test_slow_artifact_capture_is_inside_execution_deadline_and_never_starts_provider(monkeypatch, entry):
    def slow_artifacts():
        assert CURRENT_DEADLINE.get() is not None
        time.sleep(0.03)
        return {"offline": True}

    monkeypatch.setattr(execution_record, "online_artifacts", slow_artifacts)
    limits = default_limits(timeout_s=0.01)
    if entry == "ask":
        gateway = FakeModelGateway()
        deps = make_deps(FakeRetrieval(), gateway)
        with pytest.raises(DeadlineExceeded):
            run_ask(state(), replace(deps, execution_limits=limits))
    else:
        env = SkillEnv("ae_extraction")
        ctx = env.skill_context(None, env.u, "a" * 32, None)
        gateway = env.gateway
        ctx = replace(ctx, deps=replace(ctx.deps, execution_limits=limits))
        with pytest.raises(DeadlineExceeded):
            env.reg.execute(env.name, "1.0.0", env.spec["input"], context=ctx)
    assert gateway.calls == []


def test_nested_record_distinguishes_local_profile_from_shared_parent_allowance(monkeypatch):
    monkeypatch.setattr(execution_record, "online_artifacts", lambda: {"offline": True})
    parent_limits = default_limits(timeout_s=5, token_limit=1000)
    gateway = FakeModelGateway()
    with execution_scope(parent_limits):
        run = run_ask(state(), make_deps(FakeRetrieval(), gateway))
    config = run.conditions["configuration"]
    assert config["execution_limits"]["token_limit"] == 12_000
    assert config["shared_execution_limits"] == parent_limits.model_dump(mode="json")
    assert gateway.calls == []
