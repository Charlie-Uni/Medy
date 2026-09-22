"""Pre-freeze check: list main-set samples whose latest review verdict is bound to a chunk that also contained an input
which has since changed (PR-09 "latest invocation also contains superseded input").

    python evals/main_set/tools/review_binding_check.py [--json OUT]

A verdict is evidence only together with the exact prompt the reviewer saw; that prompt hashed every sample of the
chunk. When one member is edited and re-reviewed on its own, the other members stay bound to a prompt that can no
longer be rebuilt from the current samples, so they must be re-reviewed too (one sample per call avoids the cascade).
Exit code 1 when any sample is affected. Dropped samples (review/dropped_after_review.json) are ignored.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def affected(run: dict, dropped: set[str]) -> list[str]:
    chunks, latest, current = run["chunks"], run["latest"], run["sample_input_sha256"]
    out = []
    for sid, ref in latest.items():
        if sid in dropped:
            continue
        chunk = chunks[ref["chunk_index"]]
        stale = [
            m for m in chunk["sample_ids"] if m not in dropped and chunk["sample_input_sha256"].get(m) != current.get(m)
        ]
        if stale:
            out.append(sid)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=pathlib.Path, help="write {batch: [sample_id, ...]} here")
    args = ap.parse_args()
    dropped_path = REVIEW / "dropped_after_review.json"
    dropped = set(json.loads(dropped_path.read_text(encoding="utf-8"))) if dropped_path.exists() else set()
    result: dict[str, list[str]] = {}
    for b in BATCHES:
        path = REVIEW / f"run_{b}.json"
        if not path.exists():
            continue
        result[b] = affected(json.loads(path.read_text(encoding="utf-8")), dropped)
        print(f"{b}: {len(result[b])} bound to a chunk with superseded inputs")
    total = sum(len(v) for v in result.values())
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"total {total}" + ("" if total == 0 else " -> rerun them with run_review.py <batch> --chunk 1 --only ..."))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
