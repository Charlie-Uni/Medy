"""CLI: python -m medops.evals.probe <version_dir> [--mode draft|frozen] [--pages DIR] [--schema-dir DIR] [--json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medops.evals.probe")
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--mode", choices=("draft", "frozen"), default="draft")
    parser.add_argument("--pages", type=Path, default=None, help="<dir>/<source_hash>/<page>.txt raw page texts")
    parser.add_argument("--schema-dir", type=Path, default=Path("evals/probe/precise_clause/schema"))
    parser.add_argument(
        "--approval-records-root",
        type=Path,
        default=None,
        help="repository root containing hashed human PII approval records (defaults to source checkout)",
    )
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    validator = ProbeSetValidator(
        args.schema_dir,
        PageTextProvider(args.pages) if args.pages else None,
        approval_records_root=args.approval_records_root,
    )
    report = validator.validate(args.version_dir, mode=args.mode)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            print(f"[{f.level.upper():7}] {f.rule} {f.location}: {f.message}")
        print(
            f"{'PASS' if report.passed else 'FAIL'} ({args.mode}); errors={len(report.errors)} warnings={len(report.findings) - len(report.errors)}"
        )
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
