"""Freeze the safety-set drafts into a versioned, hashed directory (spec-s1 §6 step 5, reusing the main set's shape).

    python evals/safety_set/tools/freeze.py --version safety-v2-provisional --frozen-at 2026-10-06 \
        --confirmed-by "决策人（2026-10-06 答复「可以 按照建议来」）" [--second-human-review pending]

Refuses when `check_safety.py` reports a problem, when a sample's review is still pending, or when the drafts' own
`dataset_version` differs from the requested one. Writes `samples.jsonl` (the active drafts, verbatim),
`withdrawn.jsonl` + `withdrawn_manifest.json` (samples taken out, verbatim, for stored runs and frozen replay sets),
`manifest.json` (counts, synthetic documents and canaries, review provenance, confirmation, supersedes) and
`SHA256SUMS`; `dataset_hash` is the SHA-256 of the SHA256SUMS text, as for the main set.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from medops.evals.datasets import read_rows, sha256_file  # noqa: E402
from medops.evals.safety_data import (  # noqa: E402
    CATEGORIES,
    CORPUS_SAFETY,
    DATASET_VERSION,
    DRAFTS,
    MIN_PER_DEPT,
    MIN_PER_LANGUAGE,
    REPO,
    SAFETY,
    TOTAL_MIN,
    WITHDRAWN,
    load_drafts,
    write_jsonl,
)

TRACKED = (
    "samples.jsonl",
    "withdrawn.jsonl",
    "withdrawn_manifest.json",
    "review_verdicts.jsonl",
    "review_prompt_safety.md",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=DATASET_VERSION)
    ap.add_argument("--frozen-at", default=dt.date.today().isoformat())
    ap.add_argument("--confirmed-by", required=True, help="who confirmed the sheets, and when")
    ap.add_argument("--second-human-review", default="pending")
    ap.add_argument("--supersedes", default="safety-v1-provisional（草案，未冻结）")
    ap.add_argument("--record", default="记录 124")
    args = ap.parse_args()

    out = SAFETY / args.version
    if out.exists():
        raise SystemExit(f"{out} exists; a frozen version is never rewritten")
    check = subprocess.run(
        [sys.executable, str(SAFETY / "tools/check_safety.py")], capture_output=True, text=True, cwd=REPO
    )
    if check.returncode != 0 or " 0 problems" not in check.stdout.splitlines()[-1]:
        raise SystemExit("check_safety.py reports problems; fix them before freezing:\n" + check.stdout[-2000:])

    samples = load_drafts()
    pending = [s["sample_id"] for s in samples if s["review"].get("status") == "pending"]
    if pending:
        raise SystemExit(f"review pending for {pending}; run run_review.py --apply first")
    versions = {s["dataset_version"] for s in samples}
    if versions != {args.version}:
        raise SystemExit(f"drafts carry dataset_version {sorted(versions)}, not {args.version}")
    withdrawn = [s for s in load_drafts(include_withdrawn=True) if s not in samples]
    wd_manifest = (
        json.loads((WITHDRAWN / "manifest.json").read_text(encoding="utf-8"))
        if (WITHDRAWN / "manifest.json").exists()
        else {}
    )
    corpus = json.loads(CORPUS_SAFETY.read_text(encoding="utf-8"))
    verdicts = read_rows(DRAFTS / "review_verdicts.jsonl")
    prompt_hash = hashlib.sha256(
        (DRAFTS / "review_prompt_safety.md").read_text(encoding="utf-8").rstrip("\n").encode("utf-8")
    ).hexdigest()

    out.mkdir(parents=True)
    write_jsonl(out / "samples.jsonl", samples)
    write_jsonl(out / "withdrawn.jsonl", withdrawn)
    (out / "withdrawn_manifest.json").write_text(
        json.dumps(wd_manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name in ("review_verdicts.jsonl", "review_prompt_safety.md"):
        (out / name).write_bytes((DRAFTS / name).read_bytes())
    sheets = sorted(p.name for p in (DRAFTS / "sheets").glob("*.md"))
    (out / "sheets").mkdir()
    for name in sheets:
        (out / "sheets" / name).write_bytes((DRAFTS / "sheets" / name).read_bytes())

    by = lambda key: dict(sorted(collections.Counter(s[key] for s in samples).items()))  # noqa: E731
    review_models = sorted(
        {s["review"]["second_reviewer"]["model"] for s in samples if s["review"].get("second_reviewer")}
    )
    manifest = {
        "dataset_id": "safety_set",
        "dataset_version": args.version,
        "spec_version": "spec-s1 v0.3",
        "status": "frozen",
        "provisional": True,
        "frozen_at": args.frozen_at,
        "record": args.record,
        "purpose": "安全评测集：高风险、注入、越权、无依据、数字陷阱、组合、版本守卫九类；v2 替换了语料扩展后不再属于语料外的无依据样本（记录 112、114）",
        "counts": {
            "samples": len(samples),
            "withdrawn": len(withdrawn),
            "by_category": by("category"),
            "by_language": by("language"),
            "by_dept": by("dept"),
        },
        "minimums": {
            "total": TOTAL_MIN,
            "per_category": CATEGORIES,
            "per_language": MIN_PER_LANGUAGE,
            "per_dept": MIN_PER_DEPT,
        },
        "synthetic_documents": [
            {k: d[k] for k in ("document_key", "source_hash", "owner_dept")} for d in corpus["documents"]
        ],
        "canaries": [
            {"sample_id": c["sample_id"], "canary": c["canary"], "sf_key": c["sf_key"]} for c in corpus["canaries"]
        ],
        "safety_database": "medops_v2_safety",
        "reviewers": [
            {"id": "drafter-safety-01", "kind": "llm", "model": "claude-fable-5-1", "role": "drafter"},
            {
                "id": "reviewer-safety-llm-01",
                "kind": "llm",
                "model": ",".join(review_models),
                "prompt_hash": prompt_hash,
                "role": "independent_reviewer",
            },
            {"id": "annotator-01", "kind": "human", "role": "annotator"},
        ],
        "review_provenance": {
            "verdict_rows": len(verdicts),
            "statuses": dict(sorted(collections.Counter(s["review"]["status"] for s in samples).items())),
            "verdicts": dict(
                sorted(collections.Counter(s["review"].get("reviewer_verdict", "") for s in samples).items())
            ),
        },
        "confirmation": {
            "sheets": sheets,
            "confirmed_by": args.confirmed_by,
            "note": "D2 的六条由记录 84 回填；v2 变动样本见 sheets/safety-v2-changes.md；其余样本以决策人对记录 114 建议的批准为准",
        },
        "second_human_review": args.second_human_review,
        "supersedes": args.supersedes,
        "withdrawn_policy": "撤下样本原文保留在 withdrawn.jsonl，旧编号不复用；冻结的回放集与存档运行按原预期引用它们",
        "files": TRACKED + tuple(f"sheets/{n}" for n in sheets),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = "".join(f"{sha256_file(out / name)}  {name}\n" for name in manifest["files"])
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    manifest["dataset_hash"] = hashlib.sha256(sums.encode("utf-8")).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"frozen {args.version} dataset_hash={manifest['dataset_hash']} samples={len(samples)} withdrawn={len(withdrawn)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
