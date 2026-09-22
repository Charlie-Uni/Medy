"""Apply annotator-01's decisions from review/disputes_sheet.md (column 决定) to the main-set drafts and review records.

    python evals/main_set/tools/apply_resolutions.py [--dry-run] [--no-rereview] [--explicit FILE] [--sweep FILE]

Decision syntax per disputed sample (last table column):
  保留：<理由>                          -> resolutions.json entry (status disputed_resolved); nothing else changes
  接受                                  -> apply the reviewer's suggestion when it is mechanical: `删除 X 标签` removes
                                           slice X; `key_text 改为 "…"` sets key_text (page-unique, inside the span).
  接受：key_text=… | slices=a,b | query=… | topic=… | span=… | section=… | absence_terms=a;b
                                        -> explicit overrides (topic / absence_terms only for no-answer samples)
  --explicit FILE                       -> implementer translation of prose decisions: {sid: {decision_sha256, change,
                                           implementer_note}}; used only when the sheet cell's SHA-256 matches, so the
                                           translation stays bound to the annotator's exact words.
  --sweep FILE                          -> consistency changes to NON-disputed samples that follow from the decisions
                                           ({sid: {change, reason}}); applied with the same family rule and re-reviewed.
Family rule (spec-v1.1 §5.1 / PR-15): gold and slices changes apply to the parent AND its twin; a parent's query
change updates the twin's `parent_query` (part of the twin's review input); changed samples are re-packed and
re-reviewed with --only (unless --no-rereview); their old resolutions are dropped. No-answer samples whose query or
topic changes must give `absence_terms`, which are re-checked (0 hits in the scope document) and re-recorded.
The list of changed samples is written to review/changed_<date>.json for the re-review step.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
import draft_noanswer as noanswer  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
HERE = pathlib.Path(__file__).resolve().parent
REVIEW = dc.DRAFTS / "review"
BATCHES = ("MA", "PV", "CO", "EN", "NA")
SHEET = REVIEW / "disputes_sheet.md"
SLICE_NAMES = set(dc.SLICES) | set(dc.NEW_SLICES)


def load_drafts() -> dict[str, list[dict]]:
    return {b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}


def save_drafts(drafts: dict[str, list[dict]]) -> None:
    for b, rows in drafts.items():
        (dc.DRAFTS / f"samples_draft_{b}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def parse_sheet(sheet: pathlib.Path = SHEET) -> dict[str, str]:
    decisions = {}
    for line in sheet.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ms-"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        sid, decision = cells[0], cells[-1]
        if decision:
            decisions[sid] = decision.replace("\\|", "|")
    return decisions


def parse_accept(decision: str, suggestion: str) -> dict:
    body = decision[len("接受") :].lstrip("：:").strip()
    if body:
        change: dict = {}
        for part in re.split(r"\s*\|\s*", body):
            key, _, value = part.partition("=")
            key, value = key.strip(), value.strip()
            if key == "slices":
                change["slices"] = [x.strip() for x in re.split(r"[,，]", value) if x.strip()]
            elif key == "absence_terms":
                change["absence_terms"] = [x.strip() for x in re.split(r"[;；]", value) if x.strip()]
            elif key in ("key_text", "query", "topic", "span", "section"):
                change[key] = value
            else:
                raise ValueError(f"unknown override {key!r}")
        return change
    m = re.search(r"删除\s*([a-z_]+)\s*标签", suggestion)
    if m:
        return {"remove_slice": m.group(1)}
    m = re.search(r"(?:缺|补回?|应加|加上|增加|添加|应标|补齐)\s*`?([a-z_]+)`?", suggestion)
    if m and m.group(1) in SLICE_NAMES:
        return {"add_slice": m.group(1)}
    m = re.search(r"(?:删除|去掉|移除|删去)\s*`?([a-z_]+)`?", suggestion)
    if m and m.group(1) in SLICE_NAMES:
        return {"remove_slice": m.group(1)}
    m = re.search(r"key_text\s*改为\s*[\"“]([^\"”]+)[\"”]", suggestion)
    if m:
        return {"key_text": m.group(1)}
    raise ValueError(
        "suggestion is not mechanical; write an explicit override (接受：key_text=… | slices=… | query=… | topic=…)"
    )


def apply_change(sample: dict, change: dict) -> list[str]:
    fields: list[str] = []
    if "remove_slice" in change and change["remove_slice"] in sample["slices"]:
        sample["slices"] = [s for s in sample["slices"] if s != change["remove_slice"]]
        fields.append("slices")
    if "add_slice" in change and change["add_slice"] not in sample["slices"]:
        sample["slices"] = sample["slices"] + [change["add_slice"]]
        fields.append("slices")
    if "slices" in change:
        sample["slices"] = list(dict.fromkeys(change["slices"]))
        fields.append("slices")
    if not sample["slices"]:
        raise ValueError(f"{sample['sample_id']}: no slice left")
    if sample["required_gold_evidence"]:
        g = sample["required_gold_evidence"][0]
        text = dc.page_text(g["source_hash"], g["page"]) or ""
        if "span" in change:
            status, pos, located = dc.locate(text, change["span"])
            if not status.startswith(("exact", "tolerant")):
                raise ValueError(f"{sample['sample_id']}: new span {status}")
            g["evidence_span"] = {"text": located, "char_start": pos, "char_end": pos + len(located)}
            fields.append("evidence_span")
        if "key_text" in change:
            status, _pos, new = dc.locate(text, change["key_text"])
            if not status.startswith(("exact", "tolerant")):
                raise ValueError(f"{sample['sample_id']}: new key_text {status}")
            if not 2 <= len(new) <= 200:
                raise ValueError(f"{sample['sample_id']}: new key_text length {len(new)} outside 2..200")
            if new not in g["evidence_span"]["text"]:
                raise ValueError(f"{sample['sample_id']}: new key_text is not inside the evidence_span")
            g["key_text"] = new
            fields.append("key_text")
        if "section" in change:
            g["section"] = change["section"].strip()[:200]
            fields.append("section")
        mech = dc.mixed_zh_en(change.get("query", sample["query"]), g["key_text"])
        if not sample.get("derived_from"):
            sample["slices"] = [s for s in sample["slices"] if s != "mixed_zh_en"] + (["mixed_zh_en"] if mech else [])
            sample["language"] = "mixed" if mech else "zh"
        sample["slices"] = [s for s in sample["slices"] if s != "long_context"] + (
            ["long_context"] if len(g["evidence_span"]["text"]) > dc.LONG_CONTEXT_CHARS else []
        )
    else:  # no-answer sample: query / topic changes must come with re-checked absence_terms
        if "topic" in change:
            sample["abstention"]["topic"] = change["topic"][:200]
            fields.append("topic")
        if ("query" in change or "topic" in change) and not change.get("absence_terms"):
            raise ValueError(f"{sample['sample_id']}: no-answer query/topic change needs absence_terms")
        if "absence_terms" in change:
            fields.append("absence_terms")
            recheck_absence(sample, change["absence_terms"])
        mech = dc.mixed_zh_en(change.get("query", sample["query"]), "")
        sample["slices"] = [s for s in sample["slices"] if s != "mixed_zh_en"] + (["mixed_zh_en"] if mech else [])
        sample["language"] = "mixed" if mech else "zh"
    if "query" in change:
        sample["query"] = change["query"].strip()
        fields.append("query")
    return fields


def recheck_absence(sample: dict, terms: list[str]) -> None:
    """Re-run the no-answer term check (draft_noanswer.verify semantics) for a re-worded question: every term must be
    absent from all pages of the scope document; corpus-wide hits are recorded for the reviewer."""
    corpus = dc.load_corpus()
    key = sample["abstention"]["scope_document_key"]
    doc = corpus[key]
    if len(terms) < 2:
        raise ValueError(f"{sample['sample_id']}: fewer than 2 absence_terms")
    hits = {t: noanswer.term_hits(t, corpus) for t in terms}
    present = [t for t, h in hits.items() if h.get(key)]
    if present:
        raise ValueError(f"{sample['sample_id']}: absence_terms present in scope document: {present}")
    elsewhere = {t: len([k for k in h if k != key]) for t, h in hits.items()}
    sample["abstention"]["absence_check"] = (
        f"absence_terms {terms} 在 {key} 全部 {doc['pages']} 页 norm-v1 页文本中出现 0 次"
        f"（工具核查 {dt.date.today().isoformat()}，裁决后改题重查）；语料内其他文档命中数 {elsewhere}"
    )[:800]
    sample["_draft"]["absence_hits"] = {t: len(h) for t, h in hits.items()}


def load_explicit(path: pathlib.Path | None, decisions: dict[str, str]) -> dict[str, dict]:
    """Implementer translations of prose decisions, each bound to the SHA-256 of the sheet cell it translates."""
    if not path:
        return {}
    out: dict[str, dict] = {}
    for sid, entry in json.loads(path.read_text(encoding="utf-8")).items():
        cell = decisions.get(sid, "")
        if hashlib.sha256(cell.encode("utf-8")).hexdigest() != entry["decision_sha256"]:
            raise SystemExit(f"{sid}: explicit translation does not match the sheet's decision text")
        out[sid] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-rereview", action="store_true")
    ap.add_argument("--explicit", type=pathlib.Path, help="implementer translation of prose decisions (see module doc)")
    ap.add_argument("--sweep", type=pathlib.Path, help="consistency changes to non-disputed samples (see module doc)")
    ap.add_argument("--sheet", type=pathlib.Path, default=SHEET, help="dispute sheet to read (round-2+ sheets)")
    args = ap.parse_args()
    drafts = load_drafts()
    by_id = {s["sample_id"]: (b, s) for b, rows in drafts.items() for s in rows}
    twin_of = {s["sample_id"]: s["derived_from"] for _, s in by_id.values() if s.get("derived_from")}
    parent_to_twin = {v: k for k, v in twin_of.items()}
    runs = {b: json.loads((REVIEW / f"run_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    verdicts: dict[str, dict] = {}
    for b in BATCHES:
        verdicts.update(codex.current_verdicts(runs[b]))
    disputed = {sid for sid, v in verdicts.items() if v["verdict"] == "dispute" and sid in by_id}
    decisions = parse_sheet(args.sheet)
    explicit = load_explicit(args.explicit, decisions)
    res_path = REVIEW / "resolutions.json"
    resolutions = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    already = {  # 保留 from an earlier round whose verdict has not changed since
        sid
        for sid, r in resolutions.items()
        if sid in disputed and r.get("verdict_sha256") == runs[by_id[sid][0]]["latest"][sid]["verdict_sha256"]
    }
    missing = sorted(disputed - set(decisions) - already)
    print(
        f"disputed {len(disputed)}, resolved earlier {len(already)}, decided now {len(set(decisions) & disputed)}, "
        f"undecided {len(missing)}: {missing[:20]}"
    )
    changed: dict[str, list[str]] = {}

    def note(target: str, fields: list[str]) -> None:
        changed[target] = sorted(set(changed.get(target, [])) | set(fields))
        resolutions.pop(target, None)

    def apply_family(sid: str, change: dict) -> tuple[list[str], list[str]]:
        _b, s = by_id[sid]
        fields = apply_change(s, change)
        targets = [sid]
        note(sid, fields)
        if any(f in ("slices", "key_text", "evidence_span", "section") for f in fields):
            other = twin_of.get(sid) or parent_to_twin.get(sid)
            if other:
                _ob, os_ = by_id[other]
                apply_change(os_, {k: val for k, val in change.items() if k != "query"})
                os_["slices"] = list(s["slices"])  # the pair stays identical (PR-15)
                if sid not in twin_of:  # parent changed -> the twin takes the parent's gold verbatim
                    os_["required_gold_evidence"][0] = dict(
                        s["required_gold_evidence"][0], gold_id=os_["required_gold_evidence"][0]["gold_id"]
                    )
                targets.append(other)
                note(other, [f for f in fields if f != "query"])
        if "query" in fields and sid in parent_to_twin:  # the twin's review input carries parent_query
            tw = parent_to_twin[sid]
            by_id[tw][1]["_draft"]["parent_query"] = s["query"]
            if tw not in targets:
                targets.append(tw)
            note(tw, ["parent_query"])
        return fields, targets

    for sid, decision in sorted(decisions.items()):
        if sid not in disputed:
            print(f"  {sid}: decision present but sample is not disputed; ignored")
            continue
        v = verdicts[sid]
        b, s = by_id[sid]
        if decision.startswith("保留"):
            reason = decision[len("保留") :].lstrip("：:").strip()
            if len(reason) < 5:
                print(f"  {sid}: 保留 needs a reason of at least 5 characters")
                return 1
            latest = runs[b]["latest"][sid]
            resolutions[sid] = {
                "sample_input_sha256": latest["sample_input_sha256"],
                "verdict_sha256": latest["verdict_sha256"],
                "resolution_note": reason,
                "issue_scope": sorted(k for k, x in v["items"].items() if x == "issue"),
                "approval_source": f"drafts/main-v1/review/{args.sheet.name}（annotator-01 决定列）",
            }
            print(f"  {sid}: 保留 -> resolution recorded")
        elif decision.startswith("接受"):
            try:
                if sid in explicit:
                    change = explicit[sid]["change"]
                    src = "explicit translation" + (
                        " (implementer note)" if explicit[sid].get("implementer_note") else ""
                    )
                else:
                    change = parse_accept(decision, v["suggestion"])
                    src = "sheet syntax"
                fields, targets = apply_family(sid, change)
                print(f"  {sid}: 接受 [{src}] -> {fields} applied to {targets}")
            except ValueError as exc:
                print(f"  {sid}: cannot apply: {exc}")
                return 1
        else:
            print(f"  {sid}: unknown decision {decision!r} (use 接受 / 保留：理由)")
            return 1
    if args.sweep:
        sweep = json.loads(args.sweep.read_text(encoding="utf-8"))["changes"]
        for sid, entry in sorted(sweep.items()):
            if sid in disputed:
                print(f"  {sid}: sweep entry for a disputed sample; decide it in the sheet instead")
                return 1
            try:
                fields, targets = apply_family(sid, entry["change"])
                print(f"  {sid}: sweep -> {fields} applied to {targets}")
            except ValueError as exc:
                print(f"  {sid}: sweep cannot apply: {exc}")
                return 1
    for t in changed:  # a sample that is re-reviewed cannot keep a resolution bound to the old verdict
        resolutions.pop(t, None)
    if args.dry_run:
        print(f"dry run: nothing written; would change {len(changed)} samples: {sorted(changed)}")
        return 0
    res_path.write_text(json.dumps(resolutions, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (REVIEW / f"changed_{dt.date.today().isoformat()}.json").write_text(
        json.dumps(changed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if changed:
        save_drafts(drafts)
        batches = sorted({by_id[t][0] for t in changed})
        subprocess.run([sys.executable, str(HERE / "pack_review.py"), *batches], check=True)
        if not args.no_rereview:
            for b in batches:
                ids = sorted(t for t in changed if by_id[t][0] == b)
                subprocess.run([sys.executable, str(HERE / "run_review.py"), b, "--only", *ids], check=True)
    print(f"resolutions: {len(resolutions)}; changed samples: {len(changed)} {sorted(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
