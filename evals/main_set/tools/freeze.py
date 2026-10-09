"""Freeze an assembled main-set draft directory (probe SPEC §9 procedure with the spec-m1 schemas): validate in draft
mode with page texts, write SHA256SUMS over the tracked data files, bind dataset_hash, set status=frozen and
frozen_at, then validate in frozen mode.

    python evals/main_set/tools/freeze.py evals/main_set/main-v1-provisional [--pages evals/main_set/pages] [--frozen-at YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

REPO = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO / "evals/main_set/schema"
SUMS_FILES = (
    "acl_probes.jsonl",
    "corpus.json",
    "pii_exceptions.json",
    "revision_provenance.json",
    "review_prompt.md",
    "samples.jsonl",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version_dir", type=pathlib.Path)
    ap.add_argument("--pages", type=pathlib.Path, default=REPO / "evals/main_set/pages")
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
    if manifest["derived_samples"]["human_confirmation"]["status"] != "confirmed":
        print("derived twins are not human-confirmed; refusing to freeze (spec-v1.1 §5.1)")
        return 2
    if manifest["second_human_review"]["status"] == "pending" and not manifest["dataset_version"].endswith(
        "-provisional"
    ):
        print("second human review pending: only a -provisional version may be frozen (spec-m1 §4)")
        return 2
    validator = ProbeSetValidator(SCHEMA_DIR, PageTextProvider(args.pages))
    draft = validator.validate(version, mode="draft")
    if draft.errors:
        for f in draft.errors[:30]:
            print(f"DRAFT ERROR {f.rule} {f.location}: {f.message}")
        return 1
    for f in [x for x in draft.findings if x.level == "warning"][:30]:
        print(f"DRAFT WARNING {f.rule} {f.location}: {f.message}")
    manifest_raw = (version / "manifest.json").read_bytes()
    names = sorted(n for n in SUMS_FILES if (version / n).is_file())
    sums = "".join(f"{hashlib.sha256((version / n).read_bytes()).hexdigest()}  {n}\n" for n in names)
    (version / "SHA256SUMS").write_text(sums, encoding="utf-8")
    manifest["files"] = [{"path": n, "sha256": hashlib.sha256((version / n).read_bytes()).hexdigest()} for n in names]
    manifest["dataset_hash"] = hashlib.sha256(sums.encode("utf-8")).hexdigest()
    manifest["status"] = "frozen"
    manifest["frozen_at"] = args.frozen_at
    (version / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    frozen = validator.validate(version, mode="frozen")
    if frozen.errors:
        (version / "manifest.json").write_bytes(manifest_raw)
        (version / "SHA256SUMS").unlink(missing_ok=True)
        for f in frozen.errors[:30]:
            print(f"FROZEN ERROR {f.rule} {f.location}: {f.message}")
        return 1
    print(
        f"frozen {manifest['dataset_version']} dataset_hash={manifest['dataset_hash']} counts={json.dumps(frozen.counts, ensure_ascii=False)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
