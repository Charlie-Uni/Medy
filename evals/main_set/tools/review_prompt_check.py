"""Pre-freeze check mirroring PR-09's prompt binding: for every sample of the assembled main set, the prompt hash of
its latest review invocation must be rebuildable from the current samples (review_provenance._actual_prompt_hashes).
A mismatch means the record the reviewer saw differs in bytes (e.g. key order of a block) from what the frozen set
would rebuild, so the sample must be re-reviewed (one per call).

    python evals/main_set/tools/review_prompt_check.py <assembled_version_dir> [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

from medops.evals.probe import review_provenance as rp  # noqa: E402
from medops.evals.probe.validator import PageTextProvider  # noqa: E402

REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version_dir", type=pathlib.Path)
    ap.add_argument("--pages", type=pathlib.Path, default=dc.MAIN / "pages")
    ap.add_argument("--json", type=pathlib.Path)
    args = ap.parse_args()
    samples = [
        json.loads(line)
        for line in (args.version_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    samples = [s for s in samples if not rp.imported_sample(s)]
    records = rp._current_records(args.version_dir, samples, PageTextProvider(args.pages))
    assert records is not None, "page texts missing"
    prompt_text = (args.version_dir / "review_prompt.md").read_text(encoding="utf-8")
    dropped_path = REVIEW / "dropped_after_review.json"
    dropped = set(json.loads(dropped_path.read_text(encoding="utf-8"))) if dropped_path.exists() else set()
    result: dict[str, list[str]] = {}
    for b in BATCHES:
        run = json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8"))
        bad = []
        for sid, ref in run["latest"].items():
            if sid in dropped or sid not in records:
                continue
            chunk = run["chunks"][ref["chunk_index"]]
            members = [m for m in chunk["sample_ids"] if m not in dropped]
            if any(m not in records for m in members):
                bad.append(sid)
                continue
            inputs = [records[m] for m in chunk["sample_ids"] if m in records]
            if chunk["sample_input_sha256"] != {r["sample_id"]: rp._digest(r) for r in inputs}:
                bad.append(sid)
            elif chunk["prompt_sha256"] not in rp._actual_prompt_hashes(prompt_text, inputs):
                bad.append(sid)
        result[b] = sorted(bad)
        print(f"{b}: {len(bad)} samples whose latest invocation cannot be rebuilt from the current set")
    total = sum(len(v) for v in result.values())
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"total {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
