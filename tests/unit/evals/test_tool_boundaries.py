"""Maintained modules and compatibility command boundaries."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_maintained_tools_do_not_inject_paths_or_load_sibling_scripts_by_filename():
    paths = list((REPO / "src/medops/evals/tools").rglob("*.py"))
    assert len(paths) >= 79
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                assert ast.unparse(node.func) not in {
                    "sys.path.insert",
                    "sys.path.append",
                    "importlib.util.spec_from_file_location",
                }, path


def test_original_commands_delegate_and_preserve_telemetry_flush():
    wrappers = [path for directory in (REPO / "evals").rglob("tools") for path in directory.glob("*.py")]
    assert len(wrappers) == 67
    for path in wrappers:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)), path
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module.startswith("medops.evals.tools.")
            and [n.name for n in node.names] == ["main"]
            for node in tree.body
        ), path
    for name in ("smoke_ask", "safety_run"):
        tree = ast.parse((REPO / f"evals/harness/tools/{name}.py").read_text())
        assert any(isinstance(node, ast.Try) and node.finalbody for node in ast.walk(tree))
        assert any(isinstance(node, ast.Call) and ast.unparse(node.func) == "flush" for node in ast.walk(tree))
