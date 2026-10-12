"""Shared frozen datasets test support; no collected test cases."""

import json

from medops.evals.datasets import sha256_file


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def frozen(path, rows, dataset_id):
    path.mkdir()
    write_rows(path / "samples.jsonl", rows)
    files = {"samples.jsonl": sha256_file(path / "samples.jsonl")}
    (path / "SHA256SUMS").write_text(f"{files['samples.jsonl']}  samples.jsonl\n")
    manifest = {
        "dataset_id": dataset_id,
        "dataset_version": path.name,
        "dataset_hash": sha256_file(path / "SHA256SUMS"),
        "status": "frozen",
        "files": files,
    }
    (path / "manifest.json").write_text(json.dumps(manifest))
    return manifest
