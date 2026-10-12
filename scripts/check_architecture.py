"""Check maintained import directions without importing or executing project code.

Runs in make check. Rules deliberately cover the architecture contracts we can
enforce now; they do not claim complete Clean Architecture for the entire monolith.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

# Exact module edges only. A new exception must be reviewed with a reason here.
# Existing application/retrieval/skill adapter dependencies are not silently
# classified as forbidden: this slice enforces protocol and eval separation.
ALLOWLIST: dict[tuple[str, str], str] = {
    (
        "medops.worker.observability",
        "medops.evals.telemetry",
    ): "Explicit --run imports frozen evaluation scores; live request composition never imports evals.",
    (
        "medops.worker.observability",
        "medops.evals.telemetry.events_from_run",
    ): "The same optional frozen-score import, checked at its exact symbol edge.",
}
RULES: dict[str, tuple[str, ...]] = {
    "medops.retrieval.lexical": ("medops.evals",),
    "medops.application": (
        "medops.api",
        "medops.mcp",
        "medops.worker",
        "medops.bootstrap",
        "medops.evals",
        "fastapi",
        "mcp",
    ),
    "medops.infrastructure": (
        "medops.api",
        "medops.mcp",
        "medops.worker",
        "medops.bootstrap",
        "medops.evals",
        "fastapi",
        "mcp",
    ),
    "medops.ingestion": (
        "medops.api",
        "medops.mcp",
        "medops.worker",
        "medops.bootstrap",
        "medops.evals",
        "fastapi",
        "mcp",
    ),
    "medops.knowledge": (
        "medops.api",
        "medops.application",
        "medops.bootstrap",
        "medops.evals",
        "medops.ingestion",
        "medops.infrastructure",
        "medops.mcp",
        "medops.retrieval",
        "medops.worker",
        "fastapi",
        "mcp",
    ),
    "medops.bootstrap": ("medops.api", "medops.mcp", "medops.worker", "medops.evals", "fastapi", "mcp"),
    "medops.worker": ("medops.api", "medops.mcp", "medops.evals", "fastapi", "mcp"),
    "medops.api": ("medops.evals", "medops.mcp", "medops.worker"),
    "medops.mcp": ("medops.api", "medops.evals", "medops.worker", "fastapi"),
}


def matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    source: str
    target: str
    reason: str


def imports(tree: ast.AST, source: str, *, is_package: bool) -> list[tuple[int, str]]:
    """Includes function/TYPE_CHECKING imports and literal dynamic imports.

    Nonliteral dynamic imports cannot be proved safe and fail the boundary check.
    ImportFrom also checks child names: `from medops import api` is not a loophole.
    """
    package = source if is_package else source.rpartition(".")[0]
    found: list[tuple[int, str]] = []
    dynamic_names = {"__import__", "import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            dynamic_names.update(name.asname or name.name for name in node.names if name.name == "import_module")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, name.name) for name in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name("." * node.level + base, package)
            found.append((node.lineno, base))
            found.extend((node.lineno, base + "." + name.name) for name in node.names if name.name != "*")
        elif isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name)
            and node.func.id in dynamic_names
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                target = node.args[0].value
                if target.startswith("."):
                    selected = (
                        node.args[1]
                        if len(node.args) > 1
                        else next((item.value for item in node.keywords if item.arg == "package"), None)
                    )
                    if isinstance(selected, ast.Constant) and isinstance(selected.value, str):
                        target = importlib.util.resolve_name(target, selected.value)
                    else:
                        target = "<nonliteral-dynamic-import>"
                found.append((node.lineno, target))
            else:
                found.append((node.lineno, "<nonliteral-dynamic-import>"))
    return found


def check(root: Path) -> tuple[list[Violation], int]:
    violations: list[Violation] = []
    used: set[tuple[str, str]] = set()
    count = 0
    for path in sorted((root / "medops").rglob("*.py")):
        relative = path.relative_to(root)
        parts = list(relative.with_suffix("").parts)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts.pop()
        source = ".".join(parts)
        count += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative.as_posix())
        forbidden = next((targets for prefix, targets in RULES.items() if matches(source, prefix)), ())
        for line, target in imports(tree, source, is_package=is_package):
            edge = (source, target)
            if edge in ALLOWLIST:
                used.add(edge)
                continue
            if any(matches(target, prefix) for prefix in forbidden) or (
                forbidden and target == "<nonliteral-dynamic-import>"
            ):
                violations.append(Violation(relative.as_posix(), line, source, target, "forbidden import direction"))
    for source, target in sorted(set(ALLOWLIST) - used):
        violations.append(Violation("allowlist", 0, source, target, "stale exception; remove or justify it"))
    return sorted(set(violations), key=lambda row: (row.path, row.line, row.target)), count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=Path(__file__).resolve().parents[1] / "src")
    args = parser.parse_args(argv)
    if not (args.src / "medops").is_dir():
        parser.error("--src must contain medops/")
    violations, count = check(args.src)
    for row in violations:
        print(f"{row.path}:{row.line}: {row.source} -> {row.target}: {row.reason}", file=sys.stderr)
    print(f"architecture-check: {count} modules, {len(violations)} violations, {len(ALLOWLIST)} exceptions")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
