# -*- coding: utf-8 -*-
"""Freeze an assembled draft version directory (SPEC section 9): validate in draft mode with page texts, write
SHA256SUMS over the tracked data files, bind dataset_hash = SHA-256(SHA256SUMS bytes), set status=frozen and
frozen_at, then validate in frozen mode. Refuses when the draft has errors, when the twins are not yet
human-confirmed, or when the directory is already frozen.

    python evals/probe/precise_clause/drafts/v2/tooling/freeze_v2.py evals/probe/precise_clause/v2 \
        --pages evals/probe/precise_clause/v1/pages [--frozen-at YYYY-MM-DD]
"""

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

REPO = pathlib.Path(__file__).resolve().parents[6]
SCHEMA_DIR = REPO / "evals/probe/precise_clause/schema"
SUMS_FILES = ("acl_probes.jsonl", "corpus.json", "pii_exceptions.json", "review_prompt.md", "samples.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version_dir", type=pathlib.Path)
    ap.add_argument("--pages", type=pathlib.Path, required=True)
    ap.add_argument("--frozen-at", default=dt.date.today().isoformat())
    args = ap.parse_args()
    version = args.version_dir
    if (version / "SHA256SUMS").exists():
        print("already frozen (SHA256SUMS present)")
        return 2
    manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "draft":
        print("manifest is not a draft")
        return 2
    derived = manifest.get("derived_samples")
    if derived and derived["human_confirmation"]["status"] != "confirmed":
        print("derived twins are not human-confirmed; refusing to freeze (SPEC 5.1)")
        return 2
    validator = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(args.pages))
    draft = validator.validate(version, mode="draft")
    if draft.errors:
        for f in draft.errors[:20]:
            print(f"DRAFT ERROR {f.rule} {f.location}: {f.message}")
        return 1
    names = [n for n in SUMS_FILES if (version / n).is_file()]
    sums = "".join(f"{hashlib.sha256((version / n).read_bytes()).hexdigest()}  {n}\n" for n in names)
    (version / "SHA256SUMS").write_bytes(sums.encode("utf-8"))
    manifest["files"] = [{"path": n, "sha256": hashlib.sha256((version / n).read_bytes()).hexdigest()} for n in names]
    manifest["dataset_hash"] = hashlib.sha256(sums.encode("utf-8")).hexdigest()
    manifest["status"] = "frozen"
    manifest["frozen_at"] = args.frozen_at
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    frozen = validator.validate(version, mode="frozen")
    if frozen.errors:
        for f in frozen.errors[:20]:
            print(f"FROZEN ERROR {f.rule} {f.location}: {f.message}")
        return 1
    print(json.dumps({"status": "frozen", "dataset_hash": manifest["dataset_hash"], "frozen_at": args.frozen_at, "samples": frozen.counts.get("samples"), "warnings": len(frozen.findings) - len(frozen.errors)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
