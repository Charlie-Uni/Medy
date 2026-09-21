"""Mechanical checks over the draft sample files before packing them for review (a draft-mode preview of the
spec-m1 validator rules that do not need a manifest).

    python evals/main_set/tools/check_drafts.py

Checks: sample schema (with a placeholder review block), key_text page-unique and inside the span, span offsets,
twins identical to their parents (gold, slices, conflict), query uniqueness and query != any key_text (PR-08),
PII in query/key/span (PR-07), per-document non-derived cap (with the probe samples), and the spec-m1 minimums
including the imported probe set. Exit code 1 when any error is found.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

from jsonschema import Draft202012Validator

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

from medops.evals.probe.pii import find_pii_spans  # noqa: E402

BATCHES = ("MA", "PV", "CO", "EN", "NA")
REVIEW = {
    "annotator": {"kind": "human", "id": "annotator-01"},
    "second_reviewer": {
        "kind": "llm",
        "id": "reviewer-llm-02",
        "model": "claude-opus-5",
        "model_version": "claude-opus-5",
        "prompt_hash": "0" * 64,
    },
    "status": "agreed",
    "resolution_note": None,
}
MINS = {
    "answerable": 300,
    "no_answer": 40,
    "conflict": 20,
    "per_slice": 20,
    "per_dept": 60,
    "zh-Hans": 20,
    "zh-Hant": 80,
    "en": 150,
}


def main() -> int:
    corpus = dc.load_corpus()
    by_hash = {d["source_hash"]: d for d in corpus.values()}
    schema = Draft202012Validator(json.loads((dc.MAIN / "schema/probe_sample.schema.json").read_text(encoding="utf-8")))
    drafts = {b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    probe = [json.loads(line) for line in dc.PROBE_SAMPLES.read_text(encoding="utf-8").splitlines() if line.strip()]
    errors: list[str] = []
    exc_path = dc.DRAFTS / "pii_exceptions_new.json"
    exceptions = set()
    if exc_path.exists():
        for e in json.loads(exc_path.read_text(encoding="utf-8"))["exceptions"]:
            exceptions.add((e["sample_id"], e["field"], e["rule"], e["match"], e["char_start"], e["char_end"]))
    new = [s for b in BATCHES for s in drafts[b]]
    by_id = {s["sample_id"]: s for s in new}
    for s in new:
        x = {k: v for k, v in s.items() if k != "_draft"}
        x["review"] = REVIEW
        for e in schema.iter_errors(x):
            errors.append(f"{s['sample_id']}: schema {e.message[:120]} at {list(e.path)}")
        for g in s["required_gold_evidence"]:
            text = dc.page_text(g["source_hash"], g["page"])
            if text is None:
                errors.append(f"{s['sample_id']}: page text missing")
                continue
            if text.count(g["key_text"]) != 1:
                errors.append(f"{s['sample_id']}: key_text occurs {text.count(g['key_text'])} times")
            sp = g["evidence_span"]
            if text[sp["char_start"] : sp["char_end"]] != sp["text"] or g["key_text"] not in sp["text"]:
                errors.append(f"{s['sample_id']}: span offsets/containment broken")
            if by_hash[g["source_hash"]]["owner_dept"] != s["dept"]:
                errors.append(f"{s['sample_id']}: dept differs from document")
        if s.get("derived_from"):
            parent = by_id.get(s["derived_from"])
            if parent is None:
                errors.append(f"{s['sample_id']}: parent {s['derived_from']} missing")
            else:
                pg = {k: v for k, v in parent["required_gold_evidence"][0].items() if k != "gold_id"}
                tg = {k: v for k, v in s["required_gold_evidence"][0].items() if k != "gold_id"}
                if pg != tg or parent["slices"] != s["slices"] or parent.get("conflict") != s.get("conflict"):
                    errors.append(f"{s['sample_id']}: twin differs from parent {parent['sample_id']}")
                if dc.normalize_text(parent["query"]) == dc.normalize_text(s["query"]):
                    errors.append(f"{s['sample_id']}: twin query equals parent query")
        for field, text in (
            ("query", s["query"]),
            *(("key_text", g["key_text"]) for g in s["required_gold_evidence"]),
            *(("evidence_span.text", g["evidence_span"]["text"]) for g in s["required_gold_evidence"]),
        ):
            for rule, match, a, b in find_pii_spans(text):
                if (s["sample_id"], field, rule, match, a, b) in exceptions:
                    continue  # reviewed institutional-contact exception (pii_exceptions_new.json, PR-07)
                errors.append(f"{s['sample_id']}: PII {rule} in {field} ({match})")
    everything = probe + new
    keys = {dc.normalize_text(g["key_text"]) for s in everything for g in s["required_gold_evidence"]}
    seen: dict[str, str] = {}
    for s in everything:
        q = dc.normalize_text(s["query"])
        if q in seen:
            errors.append(f"{s['sample_id']}: query duplicates {seen[q]}")
        seen[q] = s["sample_id"]
        if q in keys:
            errors.append(f"{s['sample_id']}: query equals a key_text")
    per_doc = Counter(
        h
        for s in everything
        if not s.get("derived_from")
        for h in {g["source_hash"] for g in s["required_gold_evidence"]}
    )
    for h, n in per_doc.items():
        if n > dc.CAP_PER_DOCUMENT:
            errors.append(f"document {by_hash[h]['document_key']} has {n} non-derived samples > {dc.CAP_PER_DOCUMENT}")

    def lang(s: dict) -> str:
        if not s["required_gold_evidence"]:
            return corpus[s["abstention"]["scope_document_key"]]["language"]
        return by_hash[s["required_gold_evidence"][0]["source_hash"]]["language"]

    counts = {
        "samples": len(everything),
        "new": len(new),
        "answerable": sum(s.get("answerable", True) is not False for s in everything),
        "no_answer": sum(s.get("answerable", True) is False for s in everything),
        "conflict": sum("version_conflict" in s["slices"] for s in everything),
        "derived": sum(bool(s.get("derived_from")) for s in everything),
        "per_dept": dict(Counter(s["dept"] for s in everything)),
        "per_language": dict(Counter(lang(s) for s in everything)),
        "per_slice": dict(Counter(sl for s in everything for sl in s["slices"])),
    }
    short = []
    for k in ("answerable", "no_answer", "conflict"):
        if counts[k] < MINS[k]:
            short.append(f"{k} {counts[k]} < {MINS[k]}")
    short += [f"slice {k} {v} < 20" for k, v in counts["per_slice"].items() if v < MINS["per_slice"]]
    short += [f"dept {k} {v} < 60" for k, v in counts["per_dept"].items() if v < MINS["per_dept"]]
    short += [
        f"lang {k} {counts['per_language'].get(k, 0)} < {MINS[k]}"
        for k in ("zh-Hans", "zh-Hant", "en")
        if counts["per_language"].get(k, 0) < MINS[k]
    ]
    print(json.dumps(counts, ensure_ascii=False))
    print("minimum shortfalls:", short or "none")
    for e in errors[:60]:
        print("ERROR", e)
    print(f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
