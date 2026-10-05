"""`scripts/demo.py` (docs/DEMO.md): the launcher always targets the demo database, never prints or keeps secrets in
its plan, and its scenarios stay in step with the demo guide."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location("demo_launcher", REPO / "scripts/demo.py")
demo = importlib.util.module_from_spec(_SPEC)
sys.modules["demo_launcher"] = demo
_SPEC.loader.exec_module(demo)


def test_database_urls_are_rewritten_to_the_demo_database_and_proxies_removed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/medops")
    monkeypatch.setenv("DATABASE_ADMIN_URL", "postgresql://a:p@localhost:5432/medops?sslmode=disable")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setattr("dotenv.dotenv_values", lambda *_a, **_k: {})
    env = demo.demo_env()
    assert env["DATABASE_URL"].endswith("/medops_v2")
    assert env["DATABASE_ADMIN_URL"].endswith("/medops_v2?sslmode=disable")
    assert "HTTPS_PROXY" not in env and env["HF_HUB_OFFLINE"] == "1"
    assert env["GLOSSARY_DIR"].endswith("evals/glossary")


def test_scenarios_cover_the_seven_cases_of_the_guide_with_known_departments():
    assert len(demo.SCENARIOS) == 7
    assert {dept for _, dept, _ in demo.SCENARIOS} <= set(demo.SUBJECTS)
    assert demo.SCENARIOS[0][2] == demo.SCENARIOS[6][2] and demo.SCENARIOS[6][1] == "PV"  # the ACL scenario
    guide = (REPO / "docs/DEMO.md").read_text(encoding="utf-8")
    for _, _, query in demo.SCENARIOS[:6]:
        assert query[:12] in guide  # the guide's table abbreviates long questions
    assert "make demo" in guide and "scripts/demo.py" in guide
