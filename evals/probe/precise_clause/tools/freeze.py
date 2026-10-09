"""Freeze a validated precise-clause probe draft without making model calls."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

REPO = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO / "evals/probe/precise_clause/schema"
SUMS_FILES = (
    "acl_probes.jsonl",
    "corpus.json",
    "pii_exceptions.json",
    "revision_provenance.json",
    "review_prompt.md",
    "samples.jsonl",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--frozen-at", default=dt.date.today().isoformat())
    args = parser.parse_args()
    version = args.version_dir.resolve()
    if (version / "SHA256SUMS").exists():
        raise SystemExit("already frozen (SHA256SUMS present)")
    manifest = json.loads((version / "manifest.json").read_text())
    if manifest.get("status") != "draft":
        raise SystemExit("manifest is not a draft")
    derived = manifest.get("derived_samples")
    if derived and derived["human_confirmation"]["status"] != "confirmed":
        raise SystemExit("derived twins are not human-confirmed")
    validator = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(args.pages.resolve()))
    draft = validator.validate(version, mode="draft")
    if draft.errors:
        raise SystemExit(
            "\n".join(f"DRAFT ERROR {row.rule} {row.location}: {row.message}" for row in draft.errors[:20])
        )
    manifest_raw = (version / "manifest.json").read_bytes()
    names = sorted(name for name in SUMS_FILES if (version / name).is_file())
    sums = "".join(f"{hashlib.sha256((version / name).read_bytes()).hexdigest()}  {name}\n" for name in names)
    (version / "SHA256SUMS").write_text(sums)
    manifest.update(
        files=[{"path": name, "sha256": hashlib.sha256((version / name).read_bytes()).hexdigest()} for name in names],
        dataset_hash=hashlib.sha256(sums.encode()).hexdigest(),
        status="frozen",
        frozen_at=args.frozen_at,
    )
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    frozen = validator.validate(version, mode="frozen")
    if frozen.errors:
        (version / "manifest.json").write_bytes(manifest_raw)
        (version / "SHA256SUMS").unlink(missing_ok=True)
        raise SystemExit(
            "\n".join(f"FROZEN ERROR {row.rule} {row.location}: {row.message}" for row in frozen.errors[:20])
        )
    print(
        json.dumps(
            {
                "status": "frozen",
                "dataset_hash": manifest["dataset_hash"],
                "frozen_at": args.frozen_at,
                "samples": frozen.counts.get("samples"),
                "warnings": len(frozen.findings) - len(frozen.errors),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
