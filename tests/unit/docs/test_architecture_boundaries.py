"""ARCH-08: executable import constraints, including common bypass shapes."""

from pathlib import Path

import pytest
from scripts import check_architecture as boundaries


def test_current_production_imports_follow_the_documented_boundary():
    violations, count = boundaries.check(Path(__file__).resolve().parents[3] / "src")
    assert count >= 200
    assert violations == []


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "ALLOWLIST", {})
    folder = tmp_path / "medops/application"
    folder.mkdir(parents=True)
    return tmp_path, folder / "example.py"


@pytest.mark.parametrize(
    "code,target",
    [
        ("from medops.api.contracts import AskRequest", "medops.api.contracts"),
        ("import medops.api", "medops.api"),
        ("from medops import api", "medops.api"),
        ("from ..api import responses", "medops.api.responses"),
        ("def f():\n    from medops.api import auth", "medops.api.auth"),
        ("if TYPE_CHECKING:\n    import medops.api.contracts", "medops.api.contracts"),
        ('__import__("medops.api.contracts")', "medops.api.contracts"),
        ('importlib.import_module("medops.api.contracts")', "medops.api.contracts"),
        ('from importlib import import_module as load\nload("medops.api.contracts")', "medops.api.contracts"),
        ('importlib.import_module("..api.contracts", package="medops.application")', "medops.api.contracts"),
        ('importlib.import_module("..api.contracts", package=unknown_package)', "<nonliteral-dynamic-import>"),
        ("importlib.import_module(configured_module)", "<nonliteral-dynamic-import>"),
        ("from fastapi import Request", "fastapi"),
    ],
)
def test_forbidden_dependencies_fail_without_importing_code(source, code, target):
    root, path = source
    path.write_text(code + "\n")
    violations, count = boundaries.check(root)
    assert count == 1
    assert any(row.target == target for row in violations)
    assert boundaries.main(["--src", str(root)]) == 1


def test_compatible_shared_contract_and_relative_imports_pass(source):
    root, path = source
    path.write_text("from .contracts import AskRequest\nfrom medops.knowledge import pdf\n")
    assert boundaries.check(root) == ([], 1)


def test_exact_exception_does_not_allow_a_new_dependency_and_stale_entries_fail(source, monkeypatch):
    root, path = source
    allowed = ("medops.application.example", "medops.api.contracts")
    monkeypatch.setattr(boundaries, "ALLOWLIST", {allowed: "test-only exception"})
    path.write_text("import medops.api.contracts\nimport medops.api.runtime\n")
    violations, _ = boundaries.check(root)
    assert [row.target for row in violations] == ["medops.api.runtime"]
    path.write_text("from medops.domain import identity\n")
    violations, _ = boundaries.check(root)
    assert violations[0].reason.startswith("stale exception")


def test_missing_source_tree_is_an_error(tmp_path):
    with pytest.raises(SystemExit) as exc:
        boundaries.main(["--src", str(tmp_path)])
    assert exc.value.code == 2
