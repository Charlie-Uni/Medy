"""Ingest the external AI-assisted review documents that annotator-01 submitted for the MA, PV and EN sheets
(external_review/*_review_audit_2026-09-21.md) and apply their per-sample decisions to the draft sample files.

    python evals/main_set/tools/apply_external_review.py [--dry-run]

Every proposed value is re-anchored in the norm-v1 page text before it is accepted: key_text must locate exactly
once (whitespace/quote tolerant), the evidence span must locate once and contain the key, offsets are recomputed,
`mixed_zh_en` and `long_context` are recomputed mechanically and the twin family rule is applied (gold and slices
of a parent propagate to its EN twin; a dropped parent drops its twin). PV entries that changed the span without
giving its text are reconstructed from the reported span length around the new key and flagged when the
reconstruction is not exact. EN `PENDING_PARENT` suggestions are recorded, not applied, because the CO review they
depend on was not supplied. Nothing here marks a sample as annotator-confirmed: decisions land in
`_draft.decision` / `_draft.external_review` and the sheets are regenerated for the annotator's final pass.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

EXT = dc.DRAFTS / "external_review"
FILES = {
    "MA": EXT / "MA_review_audit_2026-09-21.md",
    "PV": EXT / "PV_review_audit_2026-09-21.md",
    "EN": EXT / "EN_review_audit_2026-09-21.md",
}
BATCHES = ("MA", "PV", "CO", "EN", "NA")
FIELD = re.compile(r"^\*\*(query|key_text|evidence_span|slices|section)\*\*$")
SENT_END = re.compile(r"(?<=[。！？；])|(?<=[.!?;])(?=\s)")


# ----------------------------------------------------------------------------- parsing
def blocks(text: str, header: re.Pattern) -> list[tuple[re.Match, str]]:
    out = []
    matches = list(header.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m, text[m.end() : end]))
    return out


def parse_ma(text: str) -> dict[str, dict]:
    """§8 blocks: `### ms-XXXX — OK|REVISE|DROP` with **field** / 原值 / 新值 pairs."""
    result: dict[str, dict] = {}
    for m, body in blocks(text, re.compile(r"^### (ms-\d{4}) — (OK|REVISE|DROP)\s*$", re.M)):
        sid, verdict = m.group(1), m.group(2)
        edits: dict[str, str] = {}
        field = None
        lines = body.splitlines()
        for i, line in enumerate(lines):
            fm = FIELD.match(line.strip())
            if fm:
                field = fm.group(1)
                continue
            if field and line.startswith("新值："):
                value = line[len("新值：") :]
                j = i + 1
                while j < len(lines) and lines[j].strip() and not lines[j].startswith(("原值：", "**", "自审：")):
                    value += "\n" + lines[j]
                    j += 1
                edits[field] = value.strip()
                field = None
        reason = next((ln[len("裁决理由：") :].strip() for ln in lines if ln.startswith("裁决理由：")), "")
        result[sid] = {"verdict": verdict, "edits": edits, "reason": reason}
    return result


def parse_pv(text: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    header = re.compile(r"^### (ms-\d{4}) — (更新后建议接受|原样建议接受|建议删除当前样本)\s*$", re.M)
    for m, body in blocks(text, header):
        sid, kind = m.group(1), m.group(2)
        entry: dict = {
            "verdict": {"更新后建议接受": "REVISE", "原样建议接受": "OK", "建议删除当前样本": "DROP"}[kind],
            "edits": {},
        }
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("定位："):
                mm = re.search(r"物理第(\d+)页；(.*)。$", s)
                if mm:
                    entry["page"] = int(mm.group(1))
                    entry["section"] = mm.group(2).strip()
            elif s.startswith("建议问题："):
                entry["edits"]["query"] = s[len("建议问题：") :].strip()
            elif s.startswith("更新字段："):
                entry["updated_fields"] = re.findall(r"`([a-z_]+)`", s)
            elif s.startswith("切片："):
                parts = s[len("切片：") :].split("→")
                entry["slices"] = [x.strip() for x in re.sub(r"[`。]", "", parts[-1]).split(",") if x.strip()]
            elif s.startswith("五项核查："):
                mm = re.search(r"key (\d+)字符，span (\d+)字符", s)
                if mm:
                    entry["key_len"], entry["span_len"] = int(mm.group(1)), int(mm.group(2))
            elif s.startswith("最终key："):
                mm = re.match(r"最终key：`(.*)`。?$", s)
                entry["edits"]["key_text"] = (mm.group(1) if mm else s[len("最终key：") :]).strip()
            elif s.startswith("裁决理由："):
                entry["reason"] = s[len("裁决理由：") :].strip()
        result[sid] = entry
    return result


def parse_en(text: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    header = re.compile(r"^### (ms-\d{4}) ← (ms-\d{4}) — (OK|PENDING_PARENT|DROP)\s*$", re.M)
    for m, body in blocks(text, header):
        sid, parent, verdict = m.group(1), m.group(2), m.group(3)
        entry: dict = {"verdict": verdict, "parent": parent, "edits": {}}
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("建议英文："):
                entry["edits"]["query"] = s[len("建议英文：") :].strip()
            elif s.startswith("保留英文："):
                entry["kept_query"] = s[len("保留英文：") :].strip()
            elif s.startswith("语言建议："):
                entry["reason"] = s[len("语言建议：") :].strip()
        result[sid] = entry
    return result


# ----------------------------------------------------------------------------- anchoring
def sentence_window(text: str, start: int, end: int) -> tuple[int, int]:
    cuts = [m.start() for m in SENT_END.finditer(text) if 0 < m.start() < len(text)]
    a = max((c for c in cuts if c <= start), default=0)
    b = min((c for c in cuts if c >= end), default=len(text))
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return a, b


def window_by_length(text: str, key_start: int, key_end: int, length: int) -> tuple[int, int] | None:
    """Best window of exactly `length` characters containing the key, preferring sentence-like boundaries."""
    if length < key_end - key_start:
        return None
    best, best_score = None, -1
    for s in range(max(0, key_end - length), min(key_start, len(text) - length) + 1):
        e = s + length
        score = 0
        score += 2 if s == 0 or text[s - 1] in " \n" else 0
        score += 2 if e == len(text) or text[e - 1] in "。.;；!?！？)）]」』:" or text[e] in " \n" else 0
        score += 1 if not text[s].isspace() and not text[e - 1].isspace() else 0
        if score > best_score:
            best, best_score = (s, e), score
    return best


def derive_anchor(text: str, clause: str) -> str | None:
    """Longest page-unique prefix of the clause (<= 200 chars) cut at a clause boundary, at least 20 chars."""
    limit = min(200, len(clause))
    candidates = [
        i for i in range(20, limit + 1) if i == len(clause) or clause[i - 1] in "。.;；,，:：)）]" or clause[i] == " "
    ]
    for i in sorted(candidates, reverse=True):
        prefix = clause[:i].rstrip()
        if len(prefix) >= 20 and text.count(prefix) == 1:
            return prefix
    prefix = clause[:limit].rstrip()
    return prefix if text.count(prefix) == 1 else None


def apply_edits(sample: dict, edits: dict, *, span_len: int | None = None) -> tuple[list[str], list[str]]:
    """Apply query/key_text/span/slices/section edits with re-anchoring. Returns (applied, problems)."""
    applied: list[str] = []
    problems: list[str] = []
    g = sample["required_gold_evidence"][0]
    text = dc.page_text(g["source_hash"], g["page"])
    if text is None:
        return applied, ["page text missing"]
    key, span = g["key_text"], g["evidence_span"]["text"]
    if "key_text" in edits and len(dc.normalize_text(edits["key_text"])) > 200:
        # The reviewer's "key" is a whole clause: it becomes the evidence span; the anchor stays minimal (P1).
        status, _pos, clause = dc.locate(text, edits["key_text"])
        if not status.startswith(("exact", "tolerant")):
            return applied, [f"reviewer clause {status}"]
        cpos = text.index(clause)
        if span_len and len(clause) < span_len <= 2000:
            window = window_by_length(text, cpos, cpos + len(clause), span_len)
            span = text[window[0] : window[1]] if window else clause
        else:
            span = clause
        anchor = key if (key in span and text.count(key) == 1) else None
        how = "kept"
        if anchor is not None and anchor.rstrip().endswith((":", "：")):
            # a bare lead-in ("The following points should be considered:") carries no object/constraint (P1):
            # anchor on the first content clause after it instead
            rest = clause[len(anchor) :].lstrip(" •-") if clause.startswith(anchor) else clause
            derived = derive_anchor(text, rest)
            if derived:
                anchor, how = derived, "derived (lead-in replaced)"
        if anchor is None:
            anchor, how = derive_anchor(text, clause), "derived"
        if anchor is None:
            return applied, ["no page-unique anchor of <= 200 characters inside the reviewer clause"]
        applied.append(f"reviewer key > 200 chars used as evidence span; anchor {how}")
        key = anchor
        edits = {k: v for k, v in edits.items() if k != "key_text"}
        span_len = None
    if "key_text" in edits:
        status, _pos, located = dc.locate(text, edits["key_text"])
        if not status.startswith(("exact", "tolerant")):
            problems.append(f"key_text {status}")
        else:
            key = located
    if "evidence_span" in edits:
        status, _pos, located = dc.locate(text, edits["evidence_span"])
        if not status.startswith(("exact", "tolerant")):
            problems.append(f"span {status}")
        else:
            span = located
    if problems:
        return applied, problems
    if key not in span:
        kpos = text.index(key)
        window = window_by_length(text, kpos, kpos + len(key), span_len) if span_len else None
        if window is None:
            window = sentence_window(text, kpos, kpos + len(key))
            applied.append("span rebuilt around the new key (sentence window)")
        else:
            applied.append(f"span rebuilt from the reported length {span_len}")
        span = text[window[0] : window[1]]
        if key not in span:
            return applied, ["rebuilt span does not contain key_text"]
    elif span_len and "evidence_span" not in edits and abs(len(span) - span_len) > 3 and span_len >= len(key):
        kpos = text.index(key)
        window = window_by_length(text, kpos, kpos + len(key), span_len)
        if window and key in text[window[0] : window[1]]:
            span = text[window[0] : window[1]]
            applied.append(f"span rebuilt from the reported length {span_len}")
    if text.count(span) != 1:
        return applied, ["span is not unique on the page"]
    if text.count(key) != 1:
        return applied, ["key_text is not unique on the page"]
    if not 2 <= len(key) <= 200:
        return applied, [f"key_text length {len(key)} out of range"]
    if not 2 <= len(span) <= 2000:
        return applied, [f"span length {len(span)} out of range"]
    query = edits.get("query", sample["query"]).strip()
    if not 4 <= len(query) <= 300:
        return applied, [f"query length {len(query)} out of range"]
    if dc.normalize_text(query) == key:
        return applied, ["query equals key_text"]
    if "query" in edits and query != sample["query"]:
        applied.append("query")
    if key != g["key_text"]:
        applied.append("key_text")
    start = text.index(span)
    if span != g["evidence_span"]["text"]:
        applied.append("evidence_span")
    if "section" in edits and edits["section"] and edits["section"] != g["section"]:
        g["section"] = edits["section"][:200]
        applied.append("section")
    sample["query"] = query
    g["key_text"] = key
    g["evidence_span"] = {"text": span, "char_start": start, "char_end": start + len(span)}
    return applied, []


def apply_slices(sample: dict, proposed: list[str] | None) -> list[str]:
    """Take the reviewer's non-mechanical labels, recompute the mechanical ones, report the differences."""
    before = list(sample["slices"])
    base = [s for s in (proposed if proposed is not None else before) if s in dc.SLICES + dc.NEW_SLICES]
    base = [s for s in base if s not in ("mixed_zh_en", "long_context")]
    g = sample["required_gold_evidence"][0]
    if dc.mixed_zh_en(sample["query"], g["key_text"]):
        base.append("mixed_zh_en")
    if len(g["evidence_span"]["text"]) > dc.LONG_CONTEXT_CHARS:
        base.append("long_context")
    if sample.get("conflict") and "version_conflict" not in base:
        base.append("version_conflict")
    slices = list(dict.fromkeys(base))
    if not slices:
        slices = before
    sample["slices"] = slices
    sample["language"] = "mixed" if "mixed_zh_en" in slices else "zh"
    notes = []
    if proposed is not None:
        mech = {"mixed_zh_en", "long_context"}
        if set(proposed) & mech != set(slices) & mech:
            notes.append(
                f"mechanical labels recomputed: reviewer {sorted(set(proposed) & mech)} -> tool {sorted(set(slices) & mech)}"
            )
    return notes


def sync_twin(parent: dict, twin: dict) -> None:
    twin["required_gold_evidence"][0] = dict(
        parent["required_gold_evidence"][0], gold_id=twin["required_gold_evidence"][0]["gold_id"]
    )
    twin["slices"] = list(parent["slices"])
    if parent.get("conflict"):
        twin["conflict"] = json.loads(json.dumps(parent["conflict"]))
    twin["_draft"]["parent_query"] = parent["query"]


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    drafts = {b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8")) for b in BATCHES}
    by_id = {s["sample_id"]: (b, s) for b in BATCHES for s in drafts[b]}
    twins_of: dict[str, list[dict]] = {}
    for t in drafts["EN"]:
        twins_of.setdefault(t["derived_from"], []).append(t)
    parsed = {
        "MA": parse_ma(FILES["MA"].read_text(encoding="utf-8")),
        "PV": parse_pv(FILES["PV"].read_text(encoding="utf-8")),
        "EN": parse_en(FILES["EN"].read_text(encoding="utf-8")),
    }
    report: dict = {
        "parsed": {k: len(v) for k, v in parsed.items()},
        "applied": [],
        "dropped": [],
        "problems": [],
        "pending": [],
        "notes": [],
    }
    dropped: set[str] = set()

    def record(
        sample: dict,
        source: str,
        verdict: str,
        applied: list[str],
        problems: list[str],
        reason: str,
        extra: dict | None = None,
    ) -> None:
        sample["_draft"]["external_review"] = {
            "source": f"external_review/{source}_review_audit_2026-09-21.md",
            "reviewer": "ChatGPT (AI-assisted review submitted by annotator-01, 2026-09-21)",
            "verdict": verdict,
            "applied": applied,
            "problems": problems,
            "reason": reason[:500],
            **(extra or {}),
        }
        if problems:
            sample["_draft"]["decision"] = f"external edit rejected: {problems}"
            report["problems"].append({"sample_id": sample["sample_id"], "source": source, "problems": problems})
        elif verdict == "OK" and not applied:
            sample["_draft"]["decision"] = "OK (external review)"
        else:
            sample["_draft"]["decision"] = "edited (external review)"
            report["applied"].append({"sample_id": sample["sample_id"], "source": source, "applied": applied})

    for source in ("MA", "PV"):
        for sid, entry in parsed[source].items():
            if sid not in by_id:
                report["notes"].append(f"{source}: {sid} not in drafts")
                continue
            batch, sample = by_id[sid]
            if entry["verdict"] == "DROP":
                dropped.add(sid)
                dropped.update(t["sample_id"] for t in twins_of.get(sid, []))
                sample["_draft"]["decision"] = "DROP (external review)"
                sample["_draft"]["external_review"] = {
                    "source": source,
                    "verdict": "DROP",
                    "reason": entry.get("reason", "")[:500],
                }
                report["dropped"].append(
                    {
                        "sample_id": sid,
                        "source": source,
                        "reason": entry.get("reason", "")[:160],
                        "twins": [t["sample_id"] for t in twins_of.get(sid, [])],
                    }
                )
                continue
            edits = dict(entry["edits"])
            if source == "PV" and "section" in entry.get("updated_fields", []) and entry.get("section"):
                edits["section"] = entry["section"]
            if source == "PV" and "key_text" not in entry.get("updated_fields", []):
                edits.pop("key_text", None)  # 最终key is only a restatement when key_text was not updated
            if source == "PV" and "query" not in entry.get("updated_fields", []):
                edits.pop("query", None)
            span_len = (
                entry.get("span_len") if source == "PV" and "evidence_span" in entry.get("updated_fields", []) else None
            )
            applied, problems = apply_edits(sample, edits, span_len=span_len)
            notes: list[str] = []
            if not problems:
                proposed = None
                if source == "MA" and "slices" in edits:
                    proposed = [x.strip() for x in edits["slices"].split(",") if x.strip()]
                elif source == "PV" and "slices" in entry.get("updated_fields", []):
                    proposed = entry.get("slices")
                if proposed is not None:
                    before = list(sample["slices"])
                    notes = apply_slices(sample, proposed)
                    if sample["slices"] != before:
                        applied.append("slices")
                else:
                    notes = apply_slices(sample, None)
                for t in twins_of.get(sid, []):
                    sync_twin(sample, t)
            record(
                sample,
                source,
                entry["verdict"],
                applied,
                problems,
                entry.get("reason", ""),
                {"notes": notes} if notes else None,
            )

    for sid, entry in parsed["EN"].items():
        if sid not in by_id:
            report["notes"].append(f"EN: {sid} not in drafts")
            continue
        _batch, twin = by_id[sid]
        parent_id = entry["parent"]
        if twin.get("derived_from") != parent_id:
            report["notes"].append(f"EN: {sid} parent mismatch ({twin.get('derived_from')} vs {parent_id})")
        if sid in dropped:
            continue  # follows a dropped parent
        if entry["verdict"] == "DROP":
            twin["_draft"]["external_review"] = {
                "source": "EN",
                "verdict": "DROP",
                "reason": entry.get("reason", "")[:500],
                "applied": [],
                "problems": [],
                "pending": "parent drop comes from the CO review, which was not supplied",
            }
            twin["_draft"]["decision"] = "pending: CO review not supplied (twin DROP proposed)"
            report["pending"].append({"sample_id": sid, "parent": parent_id, "kind": "drop_awaiting_co_review"})
            continue
        suggested = entry["edits"].get("query")
        if entry["verdict"] == "PENDING_PARENT":
            twin["_draft"]["external_review"] = {
                "source": "EN",
                "verdict": "PENDING_PARENT",
                "reason": entry.get("reason", "")[:500],
                "suggested_query": suggested,
                "applied": [],
                "problems": [],
            }
            twin["_draft"]["decision"] = "pending: CO parent review not supplied" + (
                " (English rewrite suggested)" if suggested else ""
            )
            report["pending"].append(
                {"sample_id": sid, "parent": parent_id, "kind": "pending_parent", "suggested": bool(suggested)}
            )
            continue
        applied: list[str] = []
        problems: list[str] = []
        if suggested and suggested != twin["query"]:
            if 4 <= len(suggested) <= 300:
                twin["query"] = suggested
                applied.append("query")
            else:
                problems.append(f"query length {len(suggested)}")
        record(twin, "EN", entry["verdict"], applied, problems, entry.get("reason", ""))

    # PR-08 sanity across the whole draft set after edits
    seen: dict[str, str] = {}
    for b in BATCHES:
        for s in drafts[b]:
            if s["sample_id"] in dropped:
                continue
            q = dc.normalize_text(s["query"])
            if q in seen:
                report["notes"].append(f"duplicate query after edits: {s['sample_id']} == {seen[q]}")
            seen[q] = s["sample_id"]
    summary = {
        "applied": len(report["applied"]),
        "dropped": len(report["dropped"]),
        "problems": len(report["problems"]),
        "pending": len(report["pending"]),
        "notes": len(report["notes"]),
    }
    print(json.dumps({"parsed": report["parsed"], **summary}, ensure_ascii=False))
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
    (EXT / "apply_report_2026-09-21.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"written: drafts updated; report -> {(EXT / 'apply_report_2026-09-21.json').relative_to(dc.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
