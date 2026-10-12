"""Keep collected tests as consumers, and fixture ownership explicit."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_tests_do_not_import_collected_test_modules_or_load_scripts_by_filename():
    violations = []
    for path in (REPO / "tests").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = (
                [node.module]
                if isinstance(node, ast.ImportFrom)
                else [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for module in modules:
                if module and module.startswith("tests.") and module.rsplit(".", 1)[-1].startswith("test_"):
                    violations.append((str(path.relative_to(REPO)), node.lineno, module))
            if isinstance(node, ast.Call) and ast.unparse(node.func) in {
                "importlib.util.spec_from_file_location",
                "runpy.run_path",
                "sys.path.insert",
                "sys.path.append",
            }:
                violations.append((str(path.relative_to(REPO)), node.lineno, ast.unparse(node.func)))
    assert violations == []


def test_shared_support_contains_no_collected_cases_or_conftest_imports():
    paths = list((REPO / "tests/support").glob("*.py"))
    assert paths
    violations = []
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                violations.append((path.name, node.name))
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith(".conftest"):
                violations.append((path.name, node.module))
    assert violations == []
