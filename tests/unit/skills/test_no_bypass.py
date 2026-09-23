"""Structural guard for INV-AUTH-03: skill implementations are reachable only through the Registry — no module
outside `medops.skills` imports a skill module, and every handler is module-private and scope-guarded."""

from __future__ import annotations

import ast
from pathlib import Path

from medops.skills.catalog import default_registry

SRC = Path(__file__).resolve().parents[3] / "src" / "medops"
PUBLIC = {"medops.skills", "medops.skills.registry", "medops.skills.catalog", "medops.skills.production"}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_no_module_outside_the_skills_package_imports_a_skill_implementation():
    offenders = []
    for path in SRC.rglob("*.py"):
        if "skills" in path.relative_to(SRC).parts:
            continue
        for name in _imports(path):
            if name.startswith("medops.skills") and name not in PUBLIC:
                offenders.append(f"{path.relative_to(SRC)} imports {name}")
    assert offenders == []


def test_delivered_skills_have_private_handlers_scopes_and_bounded_timeouts():
    reg = default_registry()
    assert reg.version_set() == ("citation_verification@1.0.0", "label_query@1.0.0")
    for entry in reg.entries():
        assert entry.handler.__name__.startswith("_"), entry.spec.name
        assert entry.spec.required_scopes and entry.spec.timeout_s <= 120
        assert entry.spec.risk.value == "low"  # M2-12: only the two low-risk skills are delivered
