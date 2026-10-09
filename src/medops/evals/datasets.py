"""Read-only integrity checks shared by frozen dataset audits and evaluation runners."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_SUM_LINE = re.compile(r"([0-9a-f]{64})  (\S+)")


def dataset_file(directory: Path, name: str) -> Path:
    """Keep manifest paths inside the dataset, including when a path is a symlink."""
    root = directory.resolve()
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root) or path == root:
        raise ValueError(f"dataset path escapes its directory: {name}")
    return path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}:{number}: expected a JSON object")
        rows.append(row)
    return rows


def load_frozen_dataset(directory: Path, *, expected_id: str | None = None) -> dict[str, Any]:
    """Verify files, manifest digests and review artifacts before loading models or spending.

    This checks integrity, not label correctness, source licensing or independent human review.
    Supports the existing probe/main, safety and replay manifest formats without rewriting them.
    """
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("status") != "frozen":
        raise ValueError("a frozen dataset manifest is required")
    if expected_id is not None and manifest.get("dataset_id") != expected_id:
        raise ValueError(f"dataset_id must be {expected_id}")
    if not manifest.get("dataset_version") or not manifest.get("dataset_id"):
        raise ValueError("dataset id and version are required")
    sums = (directory / "SHA256SUMS").read_bytes()
    if not sums.endswith(b"\n") or not sums.strip():
        raise ValueError("SHA256SUMS must be nonempty and end with a newline")
    if hashlib.sha256(sums).hexdigest() != manifest.get("dataset_hash"):
        raise ValueError("dataset_hash does not match SHA256SUMS")
    entries: dict[str, str] = {}
    for line in sums.decode("utf-8").splitlines():
        match = _SUM_LINE.fullmatch(line)
        if match is None:
            raise ValueError("malformed SHA256SUMS line")
        digest, name = match.groups()
        if name in entries:
            raise ValueError(f"duplicate checksum path: {name}")
        entries[name] = digest
        if sha256_file(dataset_file(directory, name)) != digest:
            raise ValueError(f"file digest mismatch: {name}")

    files = manifest.get("files")
    if isinstance(files, dict):
        declared = files
    elif isinstance(files, list):
        declared = {}
        for item in files:
            name = item if isinstance(item, str) else item["path"]
            if name in declared:
                raise ValueError(f"duplicate manifest path: {name}")
            declared[name] = entries.get(name) if isinstance(item, str) else item["sha256"]
    else:
        raise ValueError("manifest.files must list the frozen files")
    if declared != entries:
        raise ValueError("manifest.files differs from SHA256SUMS")
    required = (
        {"items.jsonl", "safety_items.jsonl", "subset.json"}
        if manifest["dataset_id"] == "loop_replay"
        else {"samples.jsonl"}
    )
    if not required <= entries.keys():
        raise ValueError(f"required data files absent from manifest: {sorted(required - entries.keys())}")
    for artifact in manifest.get("review_provenance", {}).get("artifacts", []):
        if sha256_file(dataset_file(directory, artifact["path"])) != artifact["sha256"]:
            raise ValueError(f"review artifact digest mismatch: {artifact['path']}")
    return manifest


def bind_run_dataset(out: Path, manifest: dict[str, Any]) -> None:
    """Refuse cross-dataset resumes; legacy rows without a binding need a new run directory."""
    binding = {k: manifest[k] for k in ("dataset_id", "dataset_version", "dataset_hash")}
    path = out / "dataset_binding.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != binding:
            raise ValueError("run is bound to another dataset; use a new output directory")
        return
    rows = out / "rows.jsonl"
    if rows.exists() and rows.stat().st_size:
        raise ValueError("existing rows have no dataset binding; use a new output directory")
    out.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(binding, ensure_ascii=False, indent=2) + "\n")
