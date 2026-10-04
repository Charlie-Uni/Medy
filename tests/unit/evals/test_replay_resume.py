"""`replay_run.py --resume`: a stored row is redone only when it is a system failure; the rule is the same for main
and safety items (record 97: safety rows of a collapsed run were kept, leaving the gate's safety blockers in place)."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "evals/replay/tools/replay_run.py"
_SPEC = importlib.util.spec_from_file_location("replay_run_resume", _PATH)
rr = importlib.util.module_from_spec(_SPEC)
sys.modules["replay_run_resume"] = rr
_SPEC.loader.exec_module(rr)


def test_missing_and_system_failure_rows_are_redone_others_kept():
    done = {
        "candidate|3|rp-0001": {"reason_codes": ["system_failure"], "success": False},
        "candidate|3|rp-0002": {"reason_codes": ["insufficient_evidence"], "success": False},
        "candidate|3|rs-0100": {"reason_codes": ["system_failure", "high_risk_medical"], "success": False},
        "candidate|3|rs-0101": {"reason_codes": [], "success": True},
    }
    assert rr.needs_run(done, "candidate|3|rp-0001")
    assert not rr.needs_run(done, "candidate|3|rp-0002")
    assert rr.needs_run(done, "candidate|3|rs-0100")
    assert not rr.needs_run(done, "candidate|3|rs-0101")
    assert rr.needs_run(done, "candidate|3|rp-9999")


def test_both_item_loops_use_the_same_resume_rule():
    """Guards against the safety loop regressing to a bare `key in done` check."""
    src = inspect.getsource(rr.main)
    assert src.count("if not needs_run(done, key):") == 2
    assert "if key in done:" not in src


def test_arm_settings_show_what_each_arm_really_runs_with():
    """Printed for both arms before any paid row (record 107); the answer-context layout is part of it (record 113)."""
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet

    bundle = {
        "glossary": {"from": "glossary-none", "to": "glossary-20260926-e4daca58a8e4"},
        "multi_query": {"from": False, "to": True},
        "doc_focus": {"from": False, "to": True},
        "query_translation": {"from": "off", "to": "gpt-6-luna"},
    }
    baseline = ReleasedPolicySet((ReleasedPolicy("b" * 32, "retrieval_params", "hybrid", "v1", bundle),))
    spec = {
        "kind": "retrieval_params",
        "name": "hybrid",
        "diff": {
            **{k: {"from": v["to"], "to": v["to"]} for k, v in bundle.items()},
            "evidence_focus": {"from": "off", "to": "sentfocus-v1"},
        },
    }
    candidate = rr.candidate_set(baseline, spec)
    base, cand = rr.arm_settings(baseline), rr.arm_settings(candidate)
    assert base["evidence_focus"] == "off" and cand["evidence_focus"] == "sentfocus-v1"
    assert {k: v for k, v in cand.items() if k != "evidence_focus"} == {
        k: v for k, v in base.items() if k != "evidence_focus"
    }  # nothing else differs between the arms
    assert cand["glossary"] == "glossary-20260926-e4daca58a8e4" and cand["query_translation"] == "gpt-6-luna"
    assert rr.arm_versions("candidate", candidate, "p").retrieval_version == rr.arm_versions(
        "candidate", baseline, "p"
    ).retrieval_version  # the layout does not change what is retrieved
    assert rr.arm_versions("candidate", candidate, "p").model_config_version.endswith(";ctx=sentfocus-v1")
