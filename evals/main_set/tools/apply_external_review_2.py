"""Second ingestion round (2026-09-22): the NA and CO external reviews and the EN twins that were pending them.

    python evals/main_set/tools/apply_external_review_2.py [--dry-run]

NA review (table): OK / DROP verdicts and slice removals are parsed from the table; the 13 narrowed questions are
taken from external_review/implementer_edits_2026-09-22.json (the review states the narrowing but not the text).
CO review (regenerated, no field diffs): OK / DROP from the table; the nine substantive revisions it describes are
carried out with the explicit values in the same JSON (parent Chinese rewrites come from the EN review's paired
proposals). ms-0300's proposed CO->PV move is not possible under PR-06 (dept must equal the document's owner_dept),
so it is dropped. EN twins previously marked PENDING_PARENT: parents that survive get the EN review's paired
Chinese rewrite when one was proposed, then the twin gets the suggested English; twins of dropped parents drop.
All values are re-anchored with the same helpers as round one; sheets are regenerated afterwards.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
from apply_external_review import EXT, apply_edits, apply_slices, blocks, sync_twin  # noqa: E402

BATCHES = ("MA", "PV", "CO", "EN", "NA")
EDITS = json.loads((EXT / "implementer_edits_2026-09-22.json").read_text(encoding="utf-8"))


def parse_na(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(r"^\| (ms-\d{4}) \| (OK|DROP) \| (MA|PV|CO) \| (.*?) \| (.*?) \| (.*?) \|$", text, re.M):
        sid, verdict, _dept, mods, _src, reason = m.groups()
        out[sid] = {
            "verdict": verdict,
            "slices_remove": re.findall(r"slices:-([a-z_]+)", mods),
            "query_topic": "query" in mods,
            "reason": reason.strip(),
        }
    return out


def parse_co(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(r"^\| (ms-\d{4}) \| `[^`]+` \| \d+ \| (OK|DROP) \| (.*?) \|$", text, re.M):
        sid, verdict, note = m.groups()
        out[sid] = {"verdict": verdict, "reason": note.strip()}
    return out


def parse_en_pending(text: str) -> dict[str, dict]:
    """PENDING_PARENT and DROP twins with their suggested English and, when marked, the proposed parent Chinese."""
    out: dict[str, dict] = {}
    header = re.compile(r"^### (ms-\d{4}) ← (ms-\d{4}) — (PENDING_PARENT|DROP)\s*$", re.M)
    for m, body in blocks(text, header):
        sid, parent, verdict = m.groups()
        lines = body.splitlines()
        entry: dict = {"parent": parent, "verdict": verdict}
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("比较基准中文："):
                nxt = next((x.strip() for x in lines[i + 1 :] if x.strip()), "")
                if nxt.startswith("上句为本轮新拟的中文配对建议"):
                    entry["parent_query_proposed"] = s[len("比较基准中文：") :].strip()
            elif s.startswith("建议英文："):
                entry["query_en"] = s[len("建议英文：") :].strip()
            elif s.startswith("语言建议："):
                entry["reason"] = s[len("语言建议：") :].strip()
        out[sid] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drafts = {b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    by_id = {s["sample_id"]: s for b in BATCHES for s in drafts[b]}
    twins_of: dict[str, list[dict]] = {}
    for t in drafts["EN"]:
        twins_of.setdefault(t["derived_from"], []).append(t)
    na = parse_na((EXT / "NA_review_audit_2026-09-21.md").read_text(encoding="utf-8"))
    co = parse_co((EXT / "CO_review_audit_2026-09-21.md").read_text(encoding="utf-8"))
    en = parse_en_pending((EXT / "EN_review_audit_2026-09-21.md").read_text(encoding="utf-8"))
    report: dict = {
        "parsed": {"NA": len(na), "CO": len(co), "EN_pending": len(en)},
        "applied": [],
        "dropped": [],
        "problems": [],
        "notes": [],
    }
    dropped: set[str] = set()

    def mark(
        sample: dict, source: str, verdict: str, applied: list[str], problems: list[str], reason: str, **extra
    ) -> None:
        sample["_draft"]["external_review"] = {
            "source": f"external_review/{source}_review_audit_2026-09-21.md",
            "reviewer": "ChatGPT (AI-assisted review submitted by annotator-01, 2026-09-21/22)",
            "verdict": verdict,
            "applied": applied,
            "problems": problems,
            "reason": reason[:500],
            **extra,
        }
        if problems:
            sample["_draft"]["decision"] = f"external edit rejected: {problems}"
            report["problems"].append({"sample_id": sample["sample_id"], "problems": problems})
        elif applied:
            sample["_draft"]["decision"] = "edited (external review)"
            report["applied"].append({"sample_id": sample["sample_id"], "source": source, "applied": applied})
        else:
            sample["_draft"]["decision"] = "OK (external review)"

    def drop(sid: str, source: str, reason: str) -> None:
        s = by_id.get(sid)
        if s is None:
            report["notes"].append(f"{source}: {sid} not in drafts")
            return
        dropped.add(sid)
        twins = [t["sample_id"] for t in twins_of.get(sid, [])]
        dropped.update(twins)
        s["_draft"]["decision"] = "DROP (external review)"
        s["_draft"]["external_review"] = {"source": source, "verdict": "DROP", "reason": reason[:500]}
        report["dropped"].append({"sample_id": sid, "source": source, "reason": reason[:160], "twins": twins})

    # ---- NA
    for sid, e in na.items():
        s = by_id.get(sid)
        if s is None:
            report["notes"].append(f"NA: {sid} not in drafts")
            continue
        if e["verdict"] == "DROP":
            drop(sid, "NA", EDITS["NA_drop"].get(sid, e["reason"]))
            continue
        applied: list[str] = []
        ed = EDITS["NA"].get(sid)
        if e["query_topic"] and not ed:
            report["notes"].append(f"NA: {sid} marked query/topic change but no implementer text")
        if ed:
            if ed["query"] != s["query"]:
                s["query"] = ed["query"]
                applied.append("query (narrowed per review)")
            if ed["topic"] != s["abstention"]["topic"]:
                s["abstention"]["topic"] = ed["topic"][:200]
                applied.append("topic")
            s["abstention"]["absence_check"] = (
                s["abstention"]["absence_check"] + "；2026-09-22 问题按外部审校收窄，缺席词未变"
            )[:800]
        if e["slices_remove"]:
            before = list(s["slices"])
            s["slices"] = [x for x in s["slices"] if x not in e["slices_remove"]]
            if s["slices"] != before:
                applied.append(f"slices -{e['slices_remove']}")
        mech = dc.mixed_zh_en(s["query"], "")
        if mech and "mixed_zh_en" not in s["slices"]:
            s["slices"].append("mixed_zh_en")
        if not mech and "mixed_zh_en" in s["slices"]:
            s["slices"].remove("mixed_zh_en")
        s["language"] = "mixed" if "mixed_zh_en" in s["slices"] else "zh"
        mark(s, "NA", e["verdict"], applied, [], e["reason"])

    # ---- CO
    for sid, e in co.items():
        s = by_id.get(sid)
        if s is None:
            report["notes"].append(f"CO: {sid} not in drafts")
            continue
        if e["verdict"] == "DROP":
            drop(sid, "CO", EDITS["CO_drop"].get(sid, e["reason"]))
            continue
        ed = dict(EDITS["CO"].get(sid, {}))
        reason = ed.pop("reason", e["reason"])
        removals = ed.pop("slices_remove", [])
        applied, problems = apply_edits(
            s, {k: v for k, v in ed.items() if k in ("query", "key_text", "evidence_span", "section")}
        )
        if not problems:
            proposed = [x for x in s["slices"] if x not in removals] if removals else None
            before = list(s["slices"])
            apply_slices(s, proposed)
            if s["slices"] != before:
                applied.append("slices")
        mark(s, "CO", e["verdict"], applied, problems, reason)

    # ---- EN twins that were pending the CO review
    for sid, e in en.items():
        t = by_id.get(sid)
        if t is None or sid in dropped:
            continue
        parent = by_id.get(e["parent"])
        if parent is None or e["parent"] in dropped:
            drop(sid, "EN", f"parent {e['parent']} dropped")
            continue
        if e["verdict"] == "DROP":
            # the EN review only mirrored a proposed parent drop; the parent survived the CO review -> keep the twin
            mark(t, "EN", "kept (parent not dropped by the CO review)", [], [], e.get("reason", ""))
            continue
        applied: list[str] = []
        problems: list[str] = []
        pq = e.get("parent_query_proposed")
        if pq and e["parent"] not in EDITS["CO"] and pq != parent["query"]:
            pa, pp = apply_edits(parent, {"query": pq})
            if pp:
                problems.append(f"parent rewrite rejected: {pp}")
            else:
                parent["_draft"]["decision"] = "edited (paired Chinese rewrite from the EN review)"
                parent["_draft"].setdefault("external_review", {})["paired_parent_rewrite"] = pq
                applied.append("parent query (paired rewrite)")
        q = e.get("query_en")
        if q and q != t["query"]:
            if 4 <= len(q) <= 300:
                t["query"] = q
                applied.append("query")
            else:
                problems.append(f"query length {len(q)}")
        mark(t, "EN", "PENDING_PARENT resolved", applied, problems, e.get("reason", ""))

    # family sync for every surviving twin (gold, slices, conflict, parent_query)
    for parent_id, twins in twins_of.items():
        parent = by_id.get(parent_id)
        if parent is None or parent_id in dropped:
            continue
        for t in twins:
            if t["sample_id"] not in dropped:
                sync_twin(parent, t)

    print(
        json.dumps(
            {
                "parsed": report["parsed"],
                "applied": len(report["applied"]),
                "dropped": len(report["dropped"]),
                "problems": len(report["problems"]),
                "notes": len(report["notes"]),
            },
            ensure_ascii=False,
        )
    )
    for p in report["problems"]:
        print("PROBLEM", p)
    for n in report["notes"]:
        print("NOTE", n)
    if args.dry_run:
        return 0
    for b in BATCHES:
        kept = [s for s in drafts[b] if s["sample_id"] not in dropped]
        (dc.DRAFTS / f"samples_draft_{b}.json").write_text(
            json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (EXT / "apply_report_2026-09-22.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
