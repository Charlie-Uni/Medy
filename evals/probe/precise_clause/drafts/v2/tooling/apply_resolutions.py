# -*- coding: utf-8 -*-
"""Apply the annotator's decisions from disputes_sheet.md (column 决定) to the v2 drafts and review records.

    python evals/probe/precise_clause/drafts/v2/tooling/apply_resolutions.py [--dry-run] [--no-rereview]

Decision syntax per disputed sample (last table column):
  保留：<理由>                       -> resolutions.json entry (status disputed_resolved); nothing else changes
  接受                               -> apply the reviewer's suggestion when it is mechanical: `删除 X 标签` removes
                                        slice X; `key_text 改为 "…"` / “…” sets key_text (must stay page-unique and
                                        inside the evidence_span). Anything else needs an explicit override:
  接受：key_text=<text>               -> set key_text
  接受：slices=a,b,c                  -> set slices
  接受：query=<text>                  -> set query (only the disputed sample)
Family rule (SPEC 5.1 / PR-15): gold and slices changes apply to the parent AND its twin together. Changed
samples are re-packed and re-reviewed with --only (unless --no-rereview); their old resolutions are dropped.
"""

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

from medops.retrieval.lexical.normalization import normalize_text

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("v2_codex_tooling", HERE / "run_codex_review.py")
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
REPO, REVIEW, DRAFTS, PAGES = codex.REPO, codex.REVIEW, HERE.parent, codex.PAGES
BATCHES = ("MA", "PV", "CO", "EN")
SHEET = REVIEW / "disputes_sheet.md"


def load_drafts() -> dict[str, list[dict]]:
    return {b: json.loads((DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}


def save_drafts(drafts: dict[str, list[dict]]) -> None:
    for b, rows in drafts.items():
        (DRAFTS / f"samples_draft_{b}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_sheet() -> dict[str, str]:
    decisions = {}
    for line in SHEET.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| pc-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        sid, decision = cells[0], cells[-1]
        if decision:
            decisions[sid] = decision
    return decisions


def page_text(g: dict) -> str:
    return normalize_text((PAGES / g["source_hash"] / f"{g['page']}.txt").read_text(encoding="utf-8"))


def parse_accept(decision: str, suggestion: str) -> dict:
    """Return {'key_text': ..} / {'slices': [...]} / {'query': ..} or raise."""
    body = decision[len("接受"):].lstrip("：:").strip()
    if body:
        change = {}
        for part in re.split(r"\s*\|\s*", body):
            key, _, value = part.partition("=")
            key, value = key.strip(), value.strip()
            if key == "slices":
                change["slices"] = [x.strip() for x in value.split(",") if x.strip()]
            elif key in ("key_text", "query"):
                change[key] = value
            else:
                raise ValueError(f"unknown override {key!r}")
        return change
    m = re.search(r"删除\s*([a-z_]+)\s*标签", suggestion)
    if m:
        return {"remove_slice": m.group(1)}
    m = re.search(r"key_text\s*改为\s*[\"“]([^\"”]+)[\"”]", suggestion)
    if m:
        return {"key_text": m.group(1)}
    raise ValueError("suggestion is not mechanical; write an explicit override (接受：key_text=… / slices=… / query=…)")


def apply_change(sample: dict, change: dict) -> list[str]:
    fields = []
    if "remove_slice" in change:
        if change["remove_slice"] in sample["slices"]:
            sample["slices"] = [s for s in sample["slices"] if s != change["remove_slice"]]
            fields.append("slices")
        if not sample["slices"]:
            raise ValueError(f"{sample['sample_id']}: removing the slice leaves no slice")
    if "slices" in change:
        sample["slices"] = list(change["slices"]); fields.append("slices")
    if "key_text" in change:
        g = sample["required_gold_evidence"][0]
        new = normalize_text(change["key_text"])
        text = page_text(g)
        if text.count(new) != 1:
            raise ValueError(f"{sample['sample_id']}: new key_text occurs {text.count(new)} times on the page")
        if new not in g["evidence_span"]["text"]:
            raise ValueError(f"{sample['sample_id']}: new key_text is not inside the evidence_span")
        g["key_text"] = new; fields.append("key_text")
    if "query" in change:
        sample["query"] = change["query"].strip(); fields.append("query")
    return fields


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-rereview", action="store_true")
    args = ap.parse_args()
    drafts = load_drafts()
    by_id = {s["sample_id"]: (b, s) for b, rows in drafts.items() for s in rows}
    twin_of = {s["sample_id"]: s["derived_from"] for _, s in by_id.values() if s.get("derived_from")}
    parent_to_twin = {v: k for k, v in twin_of.items()}
    runs = {b: json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    verdicts = {}
    for b in BATCHES:
        verdicts.update(codex.current_verdicts(runs[b]))
    disputed = {sid for sid, v in verdicts.items() if v["verdict"] == "dispute"}
    decisions = parse_sheet()
    missing = sorted(disputed - set(decisions))
    print(f"disputed {len(disputed)}, decided {len(decisions & disputed) if isinstance(decisions, set) else len(set(decisions) & disputed)}, undecided {len(missing)}: {missing}")
    res_path = REVIEW / "resolutions.json"
    resolutions = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    changed: dict[str, list[str]] = {}
    for sid, decision in sorted(decisions.items()):
        if sid not in disputed:
            print(f"  {sid}: decision present but sample is not disputed; ignored")
            continue
        v = verdicts[sid]
        b, s = by_id[sid]
        if decision.startswith("保留"):
            note = decision[len("保留"):].lstrip("：:").strip()
            if len(note) < 5:
                print(f"  {sid}: 保留 needs a reason of at least 5 characters"); return 1
            latest = runs[b]["latest"][sid]
            resolutions[sid] = {
                "sample_input_sha256": latest["sample_input_sha256"],
                "verdict_sha256": latest["verdict_sha256"],
                "resolution_note": note,
                "issue_scope": sorted(k for k, x in v["items"].items() if x == "issue"),
                "approval_source": "drafts/v2/review/disputes_sheet.md（annotator-01 决定列）",
            }
            print(f"  {sid}: 保留 -> resolution recorded")
        elif decision.startswith("接受"):
            try:
                change = parse_accept(decision, v["suggestion"])
                fields = apply_change(s, change)
                targets = [sid]
                if any(f in ("slices", "key_text") for f in fields):
                    other = twin_of.get(sid) or parent_to_twin.get(sid)
                    if other:
                        ob, os_ = by_id[other]
                        apply_change(os_, {k: val for k, val in change.items() if k != "query"})
                        targets.append(other)
                for t in targets:
                    changed[t] = fields
                    resolutions.pop(t, None)
                print(f"  {sid}: 接受 -> {fields} applied to {targets}")
            except ValueError as exc:
                print(f"  {sid}: cannot apply: {exc}"); return 1
        else:
            print(f"  {sid}: unknown decision {decision!r} (use 接受 / 保留：理由)"); return 1
    if args.dry_run:
        print("dry run: nothing written"); return 0
    res_path.write_text(json.dumps(resolutions, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if changed:
        save_drafts(drafts)
        batches = sorted({by_id[t][0] for t in changed})
        subprocess.run([sys.executable, str(HERE / "review_pack.py"), *batches], check=True)
        if not args.no_rereview:
            for b in batches:
                ids = sorted(t for t in changed if by_id[t][0] == b)
                subprocess.run([sys.executable, str(HERE / "run_claude_review.py"), b, "--only", *ids], check=True)
    print(f"resolutions: {len(resolutions)}; changed samples: {sorted(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
