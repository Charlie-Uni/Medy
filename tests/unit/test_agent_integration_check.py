"""The engineering gate must not pass skipped, missing or duplicated evidence."""

import copy
import xml.etree.ElementTree as ET

import pytest
from scripts.agent_integration_check import build_report, checks, load_plan


def report_xml(plan, *, mutation=None):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for check in checks(plan):
        file, _, name = check["nodeid"].partition("::")
        for i in range(check["instances"]):
            case = ET.SubElement(
                suite,
                "testcase",
                classname=file.removesuffix(".py").replace("/", "."),
                name=(name or "test_public_fixture") + (f"[PUBLIC-{i}]" if check["instances"] > 1 else ""),
            )
    if mutation in {"skipped", "failure", "error"}:
        ET.SubElement(case, mutation)
    elif mutation == "missing":
        suite.remove(case)
    elif mutation == "duplicate":
        suite.append(copy.deepcopy(case))
    return ET.tostring(root)


def test_all_twelve_scenarios_require_exact_executed_checks():
    plan = load_plan()
    report = build_report(plan, report_xml(plan))
    assert report["engineering_passed"] and len(report["scenarios"]) == 12
    assert report["selected_instances"] == sum(c["instances"] for c in checks(plan))
    assert report["formal_gate"] is report["real_model_quality_measured"] is False


@pytest.mark.parametrize("mutation", ["skipped", "failure", "error", "missing"])
def test_partial_or_failed_run_cannot_pass(mutation):
    plan = load_plan()
    assert build_report(plan, report_xml(plan, mutation=mutation))["engineering_passed"] is False


def test_duplicate_results_are_not_counted_as_coverage():
    plan = load_plan()
    with pytest.raises(ValueError, match="duplicate test result"):
        build_report(plan, report_xml(plan, mutation="duplicate"))


def test_nonzero_pytest_exit_cannot_be_hidden_by_successful_case_rows():
    plan = load_plan()
    assert build_report(plan, report_xml(plan), pytest_exit_code=2)["engineering_passed"] is False


def test_extra_full_suite_results_do_not_replace_missing_selected_cases():
    plan = load_plan()
    root = ET.fromstring(report_xml(plan, mutation="missing"))
    ET.SubElement(root[0], "testcase", classname="tests.unit.test_other", name="test_unrelated")
    assert build_report(plan, ET.tostring(root))["engineering_passed"] is False


def test_matrix_cannot_select_arbitrary_code_or_duplicate_coverage():
    plan = load_plan()
    plan["supplemental"].append(copy.deepcopy(plan["supplemental"][0]))
    with pytest.raises(ValueError, match="duplicate integration selector"):
        checks(plan)
    plan["supplemental"][-1] = dict(nodeid="tests/../scripts/other.py", instances=1)
    with pytest.raises(ValueError, match="invalid integration selector"):
        checks(plan)
