"""Shared checksum/manifest transition; each dataset CLI retains its approval rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medops.core.canonical import sha256_hex
from medops.evals.datasets import sha256_file
from medops.evals.files import atomic_write
from medops.evals.probe.validator import ProbeSetValidator, ValidationReport

SUMS_FILES = (
    "acl_probes.jsonl",
    "corpus.json",
    "pii_exceptions.json",
    "revision_provenance.json",
    "review_prompt.md",
    "samples.jsonl",
)


def freeze_version(
    version: Path,
    manifest: dict[str, Any],
    validator: ProbeSetValidator,
    *,
    frozen_at: str,
    sort_manifest: bool,
) -> ValidationReport:
    """Restore the exact draft manifest if post-freeze validation or writing fails.

    Callers must validate the draft and human approvals first. A checksum marker
    already present is never replaced. Concurrent writers and process death across
    the two replacements are outside this local command's transaction guarantee.
    """
    marker = version / "SHA256SUMS"
    if marker.exists():
        raise ValueError("already frozen (SHA256SUMS present)")
    manifest_path = version / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    names = sorted(name for name in SUMS_FILES if (version / name).is_file())
    files = [{"path": name, "sha256": sha256_file(version / name)} for name in names]
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in files)
    frozen_manifest = {
        **manifest,
        "files": files,
        "dataset_hash": sha256_hex(sums),
        "status": "frozen",
        "frozen_at": frozen_at,
    }
    try:
        atomic_write(marker, sums)
        atomic_write(
            manifest_path, json.dumps(frozen_manifest, ensure_ascii=False, indent=2, sort_keys=sort_manifest) + "\n"
        )
        frozen = validator.validate(version, mode="frozen")
        if frozen.errors:
            manifest_path.write_bytes(manifest_raw)
            marker.unlink(missing_ok=True)
        else:
            manifest.update(frozen_manifest)
        return frozen
    except BaseException:
        manifest_path.write_bytes(manifest_raw)
        marker.unlink(missing_ok=True)
        raise
