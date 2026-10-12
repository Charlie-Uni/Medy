"""Reject statically truthy asserts, including the historical ``... or True`` defects.

This checks explicit AST expressions, not arbitrary Python behavior or test quality. No test code is executed.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def static_truth(node: ast.expr) -> bool | None:
    try:
        return bool(ast.literal_eval(node))
    except (ValueError, TypeError):
        pass
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = static_truth(node.operand)
        return None if value is None else not value
    if isinstance(node, ast.BoolOp):
        values = [static_truth(value) for value in node.values]
        if isinstance(node.op, ast.Or):
            return True if True in values else (False if all(value is False for value in values) else None)
        return False if False in values else (True if all(value is True for value in values) else None)
    if isinstance(node, ast.IfExp):
        condition = static_truth(node.test)
        if condition is not None:
            return static_truth(node.body if condition else node.orelse)
        body, other = static_truth(node.body), static_truth(node.orelse)
        return body if body is other else None
    return None


def truthy_assertions(source: str) -> list[int]:
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Assert) and static_truth(node.test) is True
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="?", default=REPO / "tests")
    args = parser.parse_args()
    files = sorted(args.root.rglob("*.py"))
    if not files:
        print("test-assertion-check: no Python inputs")
        return 2
    findings = []
    for path in files:
        label = path.relative_to(REPO) if path.is_relative_to(REPO) else path
        findings.extend(f"{label}:{line}: statically truthy assert" for line in truthy_assertions(path.read_text()))
    for finding in findings:
        print(finding)
    print(f"test-assertion-check: {len(files)} files, {len(findings)} violations; static scope only")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
