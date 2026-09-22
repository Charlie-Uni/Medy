"""Re-bind annotator resolutions after a sample was re-reviewed WITHOUT being changed (e.g. the one-sample-per-call
re-review that repairs chunk bindings) and the reviewer raised the same objection again.

    python evals/main_set/tools/carry_forward_resolutions.py [--dry-run]

For every entry of review/resolutions.json whose verdict hash no longer matches the sample's current verdict:
  - current verdict `agree`                      -> the resolution is dropped (nothing left to resolve);
  - `dispute` whose issue items are a subset of the recorded issue_scope -> the same decision is carried forward:
    the entry is re-bound to the new verdict (sample input unchanged), `carried_forward_from` keeps the old hash;
  - `dispute` with a new issue item              -> the entry is dropped and the sample goes back to the sheet.
A carried-forward decision is still the annotator's decision on that objection; the report lists every case.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    res_path = REVIEW / "resolutions.json"
    resolutions = json.loads(res_path.read_text(encoding="utf-8"))
    latest: dict[str, dict] = {}
    verdicts: dict[str, dict] = {}
    for b in BATCHES:
        run = json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8"))
        latest.update(run["latest"])
        verdicts.update(codex.current_verdicts(run))
    kept = carried = dropped_agree = dropped_new = 0
    for sid in sorted(resolutions):
        r = resolutions[sid]
        if sid not in latest:
            print(f"  {sid}: no current verdict (pending re-review?) -> left untouched")
            continue
        if latest[sid]["verdict_sha256"] == r["verdict_sha256"]:
            kept += 1
            continue
        v = verdicts[sid]
        issues = sorted(k for k, x in v["items"].items() if x == "issue")
        if v["verdict"] != "dispute":
            print(f"  {sid}: now agree -> resolution dropped")
            resolutions.pop(sid)
            dropped_agree += 1
        elif set(issues) <= set(r["issue_scope"]) and latest[sid]["sample_input_sha256"] == r["sample_input_sha256"]:
            print(f"  {sid}: same objection {issues} on unchanged input -> decision carried forward")
            r["carried_forward_from"] = r["verdict_sha256"]
            r["verdict_sha256"] = latest[sid]["verdict_sha256"]
            carried += 1
        else:
            print(f"  {sid}: new objection {issues} (was {r['issue_scope']}) -> resolution dropped, back to the sheet")
            resolutions.pop(sid)
            dropped_new += 1
    print(
        f"kept {kept}, carried forward {carried}, dropped (agree) {dropped_agree}, dropped (new objection) {dropped_new}"
    )
    if not args.dry_run:
        res_path.write_text(
            json.dumps(resolutions, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
