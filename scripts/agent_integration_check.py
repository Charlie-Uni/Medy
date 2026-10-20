"""AGENT-07 engineering coverage gate over actual pytest results, never quality scoring.

--run executes the fixed public matrix with required temporary-PG services.
--junit reuses the full CI test report; it does not execute Agent/model calls.
Only test identities, outcomes and source digests enter the JSON summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evals/agent/development/AGENT-07-integration-v1.json"
SPEC = ROOT / "evals/agent/development/S0-pv-case-spec-v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checks(plan: dict) -> list[dict]:
    result = [c for row in plan["scenarios"] for c in row["checks"]] + plan["supplemental"]
    ids = [c["nodeid"] for c in result]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate integration selector")
    for check in result:
        path = check["nodeid"].split("::", 1)[0]
        if not path.startswith("tests/") or ".." in Path(path).parts or not path.endswith(".py"):
            raise ValueError("invalid integration selector")
        if type(check["instances"]) is not int or check["instances"] < 1:
            raise ValueError("invalid integration instance count")
    return result


def load_plan() -> dict:
    plan = json.loads(PLAN.read_text())
    if (
        plan["format"] != "agent-07-integration-v1"
        or plan["spec_sha256"] != sha(SPEC)
        or [r["id"] for r in plan["scenarios"]] != [f"PV-S0-{i:02}" for i in range(1, 13)]
        or any(not row["checks"] for row in plan["scenarios"])
    ):
        raise ValueError("integration plan/spec mismatch")
    checks(plan)
    return plan


def matches(selector: str, nodeid: str) -> bool:
    return nodeid == selector or nodeid.startswith(selector + ("[" if "::" in selector else "::"))


def build_report(plan: dict, xml: bytes, *, pytest_exit_code: int = 0) -> dict:
    rows = {}
    for case in ET.fromstring(xml).iter("testcase"):
        nodeid = case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", "")
        if nodeid in rows:
            raise ValueError("duplicate test result")
        rows[nodeid] = (
            "failed"
            if case.find("failure") is not None or case.find("error") is not None
            else ("skipped" if case.find("skipped") is not None else "passed")
        )
    selected = {}
    for check in checks(plan):
        nodes = {n: state for n, state in rows.items() if matches(check["nodeid"], n)}
        selected[check["nodeid"]] = dict(
            expected=check["instances"],
            actual=len(nodes),
            passed=len(nodes) == check["instances"] and all(s == "passed" for s in nodes.values()),
            outcomes=nodes,
        )
    scenarios = [
        dict(id=row["id"], passed=all(selected[c["nodeid"]]["passed"] for c in row["checks"]))
        for row in plan["scenarios"]
    ]
    return dict(
        format="agent-07-integration-report-v1",
        task_id="AGENT-07",
        engineering_passed=pytest_exit_code == 0 and all(c["passed"] for c in selected.values()),
        pytest_exit_code=pytest_exit_code,
        scenarios=scenarios,
        checks=selected,
        selected_instances=len({n for c in selected.values() for n in c["outcomes"]}),
        junit_sha256=hashlib.sha256(xml).hexdigest(),
        plan_sha256=sha(PLAN),
        spec_sha256=sha(SPEC),
        test_file_sha256={n: sha(ROOT / n) for n in sorted({c["nodeid"].split("::")[0] for c in checks(plan)})},
        evidence_kind="offline_fake_gateway_real_temporary_postgresql",
        development_only=True,
        formal_gate=False,
        real_model_quality_measured=False,
        unseen_tasks=0,
        hosted_model_calls=0,
        api_cost_usd=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", action="store_true")
    source.add_argument("--junit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = load_plan()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    code = 0
    if args.run:
        if not os.environ.get("MEDOPS_TEST_ADMIN_URL"):
            parser.error("--run requires explicit MEDOPS_TEST_ADMIN_URL for temporary databases")
        env = dict(os.environ, MEDOPS_TEST_REQUIRED_SERVICES="1", PYTEST_ADDOPTS="", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        for key in (
            "DEBUG",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "OPENAI_AUTH_TOKEN",
            "AZURE_OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "ANTHROPIC_BASE_URL",
        ):
            env.pop(key, None)
        with tempfile.TemporaryDirectory(prefix="medy-agent07-") as temp:
            report = Path(temp) / "junit.xml"
            log_path = args.output.with_suffix(".pytest.log")
            with log_path.open("wb") as log:
                log_path.chmod(0o600)
                code = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        *(c["nodeid"] for c in checks(plan)),
                        f"--junitxml={report}",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
            xml = report.read_bytes() if report.exists() else b"<testsuites/>"
            saved_xml = args.output.with_suffix(".junit.xml")
            saved_xml.write_bytes(xml)
            saved_xml.chmod(0o600)
    else:
        xml = args.junit.read_bytes()
    result = build_report(plan, xml, pytest_exit_code=code)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("task_id", "engineering_passed", "selected_instances", "hosted_model_calls")}
        )
    )
    return 0 if result["engineering_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
