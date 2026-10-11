"""Content bindings shared by offline measurements and restricted online execution records.

Source hashes describe files on disk, including dirty edits. They are not a signed
image identity or proof that every loaded Python object came from those bytes.
"""

from __future__ import annotations

import platform
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash, sha256_hex
from medops.core.deadline import check_deadline

PACKAGES = (
    "psycopg",
    "pgvector",
    "pydantic",
    "openai",
    "langgraph",
    "jieba",
    "numpy",
    "torch",
    "transformers",
    "sentence-transformers",
)


def runtime_files(package: Path) -> set[Path]:
    return {
        path
        for path in package.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".json", ".yaml", ".yml", ".txt", ".stop"}
    }


def file_manifest(root: Path, paths: Iterable[Path]) -> dict[str, Any]:
    root = root.resolve()
    files = {}
    for path in sorted(paths):
        check_deadline()
        files[str(path.resolve().relative_to(root))] = sha256_hex(path.read_bytes())
    check_deadline()
    return {"files": files, "sha256": canonical_hash(files)}


def environment_snapshot() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for package in PACKAGES:
        check_deadline()
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": versions,
    }


def online_artifacts() -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    paths = runtime_files(package)
    root = package.parent.parent
    if (root / "pyproject.toml").is_file():
        paths.update(root.glob("requirements*.lock"))
        paths.update((root / "schemas").glob("*.json"))
        paths.add(root / "pyproject.toml")
    else:
        root = package.parent
    return {
        "source": file_manifest(root, paths),
        "environment": environment_snapshot(),
        "source_scope": "files_on_disk_not_attested_loaded_image",
    }
