"""Freeze a validated precise-clause probe draft without making model calls."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from medops.evals.freeze import freeze_version
from medops.evals.paths import REPO
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

SCHEMA_DIR = REPO / "evals/probe/precise_clause/schema"


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
    frozen = freeze_version(version, manifest, validator, frozen_at=args.frozen_at, sort_manifest=True)
    if frozen.errors:
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
