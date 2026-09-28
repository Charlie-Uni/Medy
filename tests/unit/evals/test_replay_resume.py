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
