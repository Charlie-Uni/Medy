"""Exercise the real runner control flow with synthetic runtime adapters and no provider calls."""

import json
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet
from medops.core.canonical import canonical_hash
from medops.domain.answer import Escalation
from medops.domain.common import ReasonCode
from medops.harness.runtime import HarnessRun
from tests.unit.evals.test_replay_inputs import frozen

REPO = Path(__file__).resolve().parents[3]
PROMPT = "Synthetic released answer policy used by this test."


def setup_runner(monkeypatch, filename):
    namespace = runpy.run_path(str(REPO / "evals/harness/tools" / filename))
    glob = namespace["main"].__globals__
    settings = SimpleNamespace(
        database_url=SecretStr("postgresql://localhost/test"),
        database_admin_url=SecretStr("postgresql://localhost/test"),
        glossary_dir=None,
        llm_monthly_budget_usd=30,
        otel_exporter_otlp_endpoint=None,
        otel_exporter_otlp_headers=None,
        otel_service_name="fixture",
        langfuse_base_url=None,
    )

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args):
            return None

        def rollback(self):
            pass

        def close(self):
            pass

        @contextmanager
        def transaction(self):
            yield

    def gpu(*args):
        return SimpleNamespace(call=lambda fn: fn(), stalled=False)

    health = {"ready": True, "problems": [], "database_identity": "test-only-database"}
    facts = {"sha256": "test-only-facts", "tables": {}}
    released = ReleasedPolicySet((ReleasedPolicy("test-policy", "prompt", "answer_system", "1", {"text": PROMPT}),))
    monkeypatch.setitem(glob, "Settings", lambda: settings)
    monkeypatch.setitem(glob, "PinnedThread", gpu)
    monkeypatch.setitem(glob, "PinnedEmbedding", lambda provider, thread: provider)
    monkeypatch.setitem(glob, "PinnedReranker", lambda provider, thread: provider)
    monkeypatch.setitem(
        glob,
        "build_budgeted_gateway",
        lambda settings, **kwargs: SimpleNamespace(provider="fixture", run_cap_blocked=False),
    )
    monkeypatch.setattr("psycopg.connect", lambda *args, **kwargs: Connection())
    monkeypatch.setattr(
        "medops.retrieval.vector.embedding.BgeM3EmbeddingProvider", lambda **kwargs: SimpleNamespace(spec=None)
    )
    monkeypatch.setattr(
        "medops.retrieval.rerank.BgeRerankerV2M3", lambda **kwargs: SimpleNamespace(score=lambda *args: [])
    )
    monkeypatch.setattr("medops.retrieval.integrity.require_retrieval_integrity", lambda *args, **kwargs: health)
    monkeypatch.setattr("medops.evals.run_conditions.fact_snapshot", lambda *args: facts)
    monkeypatch.setattr("medops.evals.run_conditions.fact_snapshot_from_dsn", lambda *args, **kwargs: facts)
    if "fact_snapshot" in glob:
        monkeypatch.setitem(glob, "fact_snapshot", lambda *args: facts)
    if "fact_snapshot_from_dsn" in glob:
        monkeypatch.setitem(glob, "fact_snapshot_from_dsn", lambda *args, **kwargs: facts)
    monkeypatch.setattr("medops.application.policy_loader.load_released", lambda conn: released)
    return glob


def test_main_retry_preserves_fees_applies_released_prompt_and_refuses_changed_date(tmp_path, monkeypatch):
    glob = setup_runner(monkeypatch, "smoke_ask.py")
    sample = {
        "sample_id": "ms-0001",
        "query": "Synthetic unanswerable question?",
        "dept": "PV",
        "language": "en",
        "slices": ["no_answer"],
        "answerable": False,
        "expected_behaviour": "insufficient_evidence",
        "required_gold_evidence": [],
    }
    dataset = tmp_path / "dataset"
    manifest = frozen(dataset, [sample], "precise_clause_main")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"dataset_hash": manifest["dataset_hash"], "entries": []}))
    out = tmp_path / "run"
    calls = []

    def run(state, deps):
        calls.append(deps.answer_system)
        deps.gateway.cost_usd += 0.1 if len(calls) == 1 else 0.2
        deps.gateway.calls += 1
        reason = ReasonCode.system_failure if len(calls) == 1 else ReasonCode.insufficient_evidence
        state = state.model_copy(
            update={
                "escalation": Escalation(
                    reason_codes=(reason,), query=state.query, policy_version=state.versions.policy_version
                )
            }
        )
        return HarnessRun(state, (), ())

    monkeypatch.setitem(glob, "run_ask", run)
    argv = [
        "smoke",
        "--out",
        str(out),
        "--dataset",
        str(dataset),
        "--mapping",
        str(mapping),
        "--ids",
        "ms-0001",
        "--conflict",
        "0",
        "--no-answer",
        "0",
        "--per-dept",
        "0",
        "--device",
        "cpu",
        "--released",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert glob["main"]() == 0
    monkeypatch.setattr(sys, "argv", [*argv, "--resume"])
    assert glob["main"]() == 0
    results = json.loads((out / "results.json").read_text())
    assert results["n"] == 1 and results["rows"][0]["success"]
    assert results["total_cost_usd"] == 0.3 and results["retained_outcome_cost_usd"] == 0.2
    assert results["attempt_accounting"]["recorded_attempts"] == 2
    assert calls == [PROMPT, PROMPT]
    before = (out / "rows.jsonl").read_bytes()
    monkeypatch.setattr(sys, "argv", [*argv, "--resume", "--as-of", "2026-10-09"])
    with pytest.raises(ValueError, match="conditions changed.*configuration"):
        glob["main"]()
    assert (out / "rows.jsonl").read_bytes() == before and len(calls) == 2


def test_safety_persists_failed_paid_attempt_before_stalled_gpu_exit(tmp_path, monkeypatch):
    glob = setup_runner(monkeypatch, "safety_run.py")
    gpu = SimpleNamespace(call=lambda fn: fn(), stalled=False)
    monkeypatch.setitem(glob, "PinnedThread", lambda *args: gpu)
    sample = {
        "sample_id": "ss-0001",
        "query": "Synthetic safety question?",
        "dept": "PV",
        "category": "ungrounded",
        "language": "en",
        "slices": [],
        "expected": {"outcome": ["escalated"], "reason_codes": ["insufficient_evidence"]},
    }
    dataset = tmp_path / "safety"
    frozen(dataset, [sample], "safety_set")

    def run(s, planes, gateway, registry, versions, lookups):
        assert all(plane.deps.answer_system == PROMPT for plane in planes.values())
        gpu.stalled = True
        return {
            "sample_id": s["sample_id"],
            "sample_input_sha256": canonical_hash(s),
            "versions": versions.model_dump(mode="json"),
            "reason_codes": ["system_failure"],
            "cost_usd": 0.12,
            "model_calls": 1,
        }

    monkeypatch.setitem(glob, "run_sample", run)
    out = tmp_path / "run"
    monkeypatch.setattr(
        sys, "argv", ["safety", "--out", str(out), "--dataset", str(dataset), "--device", "cpu", "--released"]
    )
    assert glob["main"]() == glob["EXIT_STALLED"]
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["cost_usd"] == 0.12
    assert rows[0]["attempt_id"] and rows[0]["run_conditions_sha256"]
