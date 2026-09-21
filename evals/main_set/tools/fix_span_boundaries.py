"""Repair evidence spans that the round-1 length-based reconstruction misaligned (record 50 §12).

    python evals/main_set/tools/fix_span_boundaries.py [--dry-run]

For every PV/EN sample the LLM reviewer disputed on `evidence_span` (boundary complaints: the span starts or ends
inside a sentence), the span is rebuilt as the smallest run of complete sentences containing the key_text, using
the same sentence-boundary rule as the probe drafting tool; twins are synced from their parents. Samples whose span
changes are listed in review/span_changed_ids_<batch>.txt for a targeted re-review (--only).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402
from apply_external_review import sentence_window, sync_twin  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "v2_codex_tooling", dc.REPO / "evals/probe/precise_clause/drafts/v2/tooling/run_codex_review.py"
)
assert _spec and _spec.loader
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)
REVIEW = dc.DRAFTS / "review"
ORIGINAL_DIR = dc.DRAFTS / "external_review/drafts_before_external_review"
QUOTED = re.compile(r"[“\"「『]([^”\"」』]{40,2000})[”\"」』]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batches", nargs="*", default=["PV", "CO", "MA"])
    args = ap.parse_args()
    drafts = {
        b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8"))
        for b in ("MA", "PV", "CO", "EN")
    }
    by_id = {s["sample_id"]: s for b in drafts for s in drafts[b]}
    twins_of: dict[str, list[dict]] = {}
    for t in drafts["EN"]:
        twins_of.setdefault(t["derived_from"], []).append(t)
    original: dict[str, str] = {}
    for b in ("MA", "PV", "CO"):
        p = ORIGINAL_DIR / f"samples_draft_{b}.json"
        if p.exists():
            for o in json.loads(p.read_text(encoding="utf-8")):
                original[o["sample_id"]] = o["required_gold_evidence"][0]["evidence_span"]["text"]
    changed: dict[str, list[str]] = {}
    for b in args.batches:
        rp = REVIEW / f"run_{b}.json"
        if not rp.exists():
            continue
        verdicts = codex.current_verdicts(json.loads(rp.read_text(encoding="utf-8")))
        for sid, v in verdicts.items():
            if v["verdict"] != "dispute" or v["items"].get("evidence_span") != "issue":
                continue
            s = by_id.get(sid)
            if s is None:
                continue
            g = s["required_gold_evidence"][0]
            text = dc.page_text(g["source_hash"], g["page"]) or ""
            kpos = text.find(g["key_text"])
            if kpos < 0 or text.count(g["key_text"]) != 1:
                print(f"{sid}: key not unique; skipped")
                continue
            span, how = None, ""
            # 1) the drafter's original span (before the external review's length-based rebuild), if it holds the key
            orig = original.get(sid)
            if orig and g["key_text"] in orig and text.count(orig) == 1:
                span, how = orig, "drafter's original span restored"
            # 2) a sentence the reviewer quoted in its suggestion
            if span is None:
                for quoted in QUOTED.findall(v.get("suggestion", "")):
                    status, _pos, located = dc.locate(text, quoted)
                    if status.startswith(("exact", "tolerant")) and g["key_text"] in located and len(located) >= 40:
                        span, how = located, "reviewer-quoted sentence"
                        break
            # 3) the smallest run of complete sentences around the key
            if span is None:
                a, z = sentence_window(text, kpos, kpos + len(g["key_text"]))
                span, how = text[a:z], "sentence window"
            if span == g["evidence_span"]["text"] or text.count(span) != 1 or not 2 <= len(span) <= 2000:
                print(f"{sid}: {how} unchanged/not unique/out of range; left for adjudication")
                continue
            a = text.index(span)
            old = g["evidence_span"]["text"]
            g["evidence_span"] = {"text": span, "char_start": a, "char_end": a + len(span)}
            s["slices"] = [x for x in s["slices"] if x != "long_context"] + (
                ["long_context"] if len(span) > dc.LONG_CONTEXT_CHARS else []
            )
            s["_draft"]["decision"] = (
                s["_draft"].get("decision", "") + "; span rebuilt on sentence boundaries after review"
            ).lstrip("; ")
            changed.setdefault(b, []).append(sid)
            for t in twins_of.get(sid, []):
                sync_twin(s, t)
                changed.setdefault("EN", []).append(t["sample_id"])
            print(f"{sid}: {len(old)} -> {len(span)} chars [{how}] | {span[:90]}")
    print({b: len(v) for b, v in changed.items()})
    if args.dry_run:
        return 0
    for b, rows in drafts.items():
        (dc.DRAFTS / f"samples_draft_{b}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    for b, ids in changed.items():
        (REVIEW / f"span_changed_ids_{b}.txt").write_text("\n".join(sorted(ids)) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
