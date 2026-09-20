# -*- coding: utf-8 -*-
"""Re-export the frozen v1 samples as per-department draft files for a full re-review under a new second
reviewer (owner decision 2026-09-20, option 2: one uniform LLM reviewer for all 107 v2 samples).

    python evals/probe/precise_clause/drafts/v2/tooling/make_original_drafts.py

Writes drafts/v2/samples_draft_{MA,PV,CO}.json with the v1 sample fields minus the v1 review block (the v1
verdicts stay archived in v1/review_evidence and are not reused). Nothing about the samples changes.
"""

import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[6]
V1 = REPO / "evals/probe/precise_clause/v1"
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v2"


def main() -> None:
    samples = [json.loads(l) for l in (V1 / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for dept in ("MA", "PV", "CO"):
        batch = [{k: v for k, v in s.items() if k != "review"} for s in samples if s["dept"] == dept]
        out = DRAFTS / f"samples_draft_{dept}.json"
        out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{dept}: {len(batch)} samples -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
