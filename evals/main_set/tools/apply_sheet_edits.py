"""Apply annotator-01's decisions from the confirmation sheets back to the draft sample files (spec-m1 §4 step 2).

    python evals/main_set/tools/apply_sheet_edits.py [MA PV CO EN NA] [--dry-run]

The annotator edits drafts/main-v1/samples_draft_<batch>.md: either the 结论 column (`OK`, `DROP`, or directives
`query=…; key_text=…; span=…; slices=a,b,c; query_en=…; topic=…` separated by `;`) or the query / key_text / slices
cells in place. For every changed answerable sample the tool re-locates key_text and span in the norm-v1 page text,
recomputes offsets, re-checks page uniqueness, recomputes `mixed_zh_en` / `long_context` mechanically and rejects an
edit that no longer anchors (the row is reported and left unchanged). Twins (EN batch) follow their parent for
gold and slices (spec-v1.1 family rule); a DROPped parent drops its twin. The updated JSON files keep the ids; the
sheets are regenerated with the decisions recorded in a `已确认` column so a second pass starts from the confirmed state.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

BATCHES = ("MA", "PV", "CO", "EN", "NA")
DIRECTIVE = re.compile(r"^(query|key_text|span|slices|query_en|topic)\s*=\s*(.+)$")


def unescape(cell: str) -> str:
    return cell.replace("\\|", "|").strip()


def parse_sheet(path: pathlib.Path) -> dict[str, dict]:
    """Rows keyed by sample id -> {columns by header}. Only table rows are read; the header defines the columns."""
    rows: dict[str, dict] = {}
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [unescape(c) for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        if header is None:
            header = cells
            continue
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        if len(cells) != len(header):
            print(f"{path.name}: malformed row skipped: {line[:80]}")
            continue
        row = dict(zip(header, cells, strict=True))
        rows[row["ID"]] = row
    return rows


def decisions(row: dict) -> tuple[str, dict[str, str]]:
    verdict = row.get("结论", "").strip()
    if not verdict:
        return "pending", {}
    if verdict.upper() == "OK":
        return "ok", {}
    if verdict.upper().startswith("DROP"):
        return "drop", {}
    edits: dict[str, str] = {}
    for part in re.split(r"[;；]\s*(?=(?:query|key_text|span|slices|query_en|topic)\s*=)", verdict):
        m = DIRECTIVE.match(part.strip())
        if m:
            edits[m.group(1)] = m.group(2).strip().strip("“”\"'")
    return ("edit" if edits else "note"), edits


def cell_edits(row: dict, sample: dict) -> dict[str, str]:
    """In-place edits of the query / key_text / slices cells (compared with the current sample values)."""
    edits: dict[str, str] = {}
    if (
        "query" in row
        and row["query"]
        and row["query"] != sample["query"][:200] + ("…" if len(sample["query"]) > 200 else "")
    ):
        edits["query"] = row["query"]
    if (
        "英文问题" in row
        and row["英文问题"]
        and row["英文问题"] != sample["query"][:200] + ("…" if len(sample["query"]) > 200 else "")
    ):
        edits["query"] = row["英文问题"]
    g = sample["required_gold_evidence"][0] if sample["required_gold_evidence"] else None
    if (
        g
        and "key_text" in row
        and row["key_text"]
        and row["key_text"] != g["key_text"][:120] + ("…" if len(g["key_text"]) > 120 else "")
    ):
        edits["key_text"] = row["key_text"]
    if "切片" in row and row["切片"]:
        current = ", ".join(sample["slices"])
        if row["切片"].replace(" ", "") != current.replace(" ", ""):
            edits["slices"] = row["切片"]
    return edits


def reanchor(sample: dict, edits: dict[str, str], doc: dict) -> list[str]:
    """Apply edits to an answerable sample; returns problems (empty means applied)."""
    problems: list[str] = []
    g = sample["required_gold_evidence"][0]
    text = dc.page_text(g["source_hash"], g["page"])
    if text is None:
        return ["page text missing"]
    key, span = g["key_text"], g["evidence_span"]["text"]
    if "key_text" in edits:
        status, _pos, key = dc.locate(text, edits["key_text"])
        if not status.startswith(("exact", "tolerant")):
            problems.append(f"key_text {status}")
    if "span" in edits:
        status, pos, span = dc.locate(text, edits["span"])
        if not status.startswith(("exact", "tolerant")):
            problems.append(f"span {status}")
    if problems:
        return problems
    if key not in span:
        return ["key_text is not inside the evidence span"]
    if not 2 <= len(key) <= 200 or not 2 <= len(span) <= 2000:
        return ["key_text or span length out of range"]
    start = text.index(span)
    if text.count(span) != 1:
        return ["span is not unique on the page"]
    query = edits.get("query", sample["query"]).strip()
    if not 4 <= len(query) <= 300 or dc.normalize_text(query) == key:
        return ["query length out of range or equals key_text"]
    slices = [s.strip() for s in re.split(r"[,，]", edits["slices"])] if "slices" in edits else list(sample["slices"])
    slices = [s for s in slices if s in dc.SLICES + dc.NEW_SLICES]
    slices = [s for s in slices if s not in ("mixed_zh_en", "long_context")]
    if not sample.get("derived_from") and dc.mixed_zh_en(query, key):
        slices.append("mixed_zh_en")
    elif sample.get("derived_from") and "mixed_zh_en" in sample["slices"]:
        slices.append("mixed_zh_en")  # twins inherit the parent's mechanical label
    if len(span) > dc.LONG_CONTEXT_CHARS:
        slices.append("long_context")
    if sample.get("conflict") and "version_conflict" not in slices:
        slices.append("version_conflict")
    if not slices:
        return ["no slices left"]
    sample["query"] = query
    sample["slices"] = list(dict.fromkeys(slices))
    if not sample.get("derived_from"):
        sample["language"] = "mixed" if "mixed_zh_en" in slices else "zh"
    g["key_text"] = key
    g["evidence_span"] = {"text": span, "char_start": start, "char_end": start + len(span)}
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="*", default=list(BATCHES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    corpus = dc.load_corpus()
    by_hash = {d["source_hash"]: d for d in corpus.values()}
    drafts = {
        b: json.loads((dc.DRAFTS / f"samples_draft_{b}.json").read_text(encoding="utf-8"))
        for b in BATCHES
        if (dc.DRAFTS / f"samples_draft_{b}.json").exists()
    }
    twins_of = {}
    for t in drafts.get("EN", []):
        twins_of.setdefault(t["derived_from"], []).append(t)
    report = {"ok": 0, "drop": 0, "edit": 0, "pending": 0, "rejected": [], "note": 0}
    dropped: set[str] = set()
    for b in args.batches:
        sheet = dc.DRAFTS / f"samples_draft_{b}.md"
        if b not in drafts or not sheet.exists():
            continue
        rows = parse_sheet(sheet)
        for s in drafts[b]:
            row = rows.get(s["sample_id"])
            if row is None:
                continue
            kind, edits = decisions(row)
            if kind in ("ok", "note", "pending"):
                edits = cell_edits(row, s)
                if edits:
                    kind = "edit"
            if kind == "drop":
                dropped.add(s["sample_id"])
                dropped.update(t["sample_id"] for t in twins_of.get(s["sample_id"], []))
                report["drop"] += 1
                s["_draft"]["decision"] = "DROP"
                continue
            if kind == "edit":
                if s.get("answerable", True) is False:
                    if "query" in edits:
                        s["query"] = edits["query"].strip()
                    if "topic" in edits:
                        s["abstention"]["topic"] = edits["topic"][:200]
                    s["_draft"]["decision"] = "edited"
                    report["edit"] += 1
                    continue
                doc = by_hash[s["required_gold_evidence"][0]["source_hash"]]
                problems = reanchor(s, {k: v for k, v in edits.items() if k != "query_en"}, doc)
                if problems:
                    report["rejected"].append((s["sample_id"], problems))
                    s["_draft"]["decision"] = f"edit rejected: {problems}"
                    continue
                if "query_en" in edits:
                    for t in twins_of.get(s["sample_id"], []):
                        t["query"] = edits["query_en"].strip()
                # family rule: gold and slices propagate to twins
                for t in twins_of.get(s["sample_id"], []):
                    t["required_gold_evidence"][0] = dict(
                        s["required_gold_evidence"][0], gold_id=t["required_gold_evidence"][0]["gold_id"]
                    )
                    t["slices"] = list(s["slices"])
                s["_draft"]["decision"] = "edited"
                report["edit"] += 1
            else:
                s["_draft"]["decision"] = (
                    "OK" if kind == "ok" else ("pending" if kind == "pending" else row.get("结论", ""))
                )
                report[kind] += 1
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    for b, samples in drafts.items():
        kept = [s for s in samples if s["sample_id"] not in dropped]
        (dc.DRAFTS / f"samples_draft_{b}.json").write_text(
            json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("sheets are regenerated by make_sheets.py from the updated JSON (decisions kept in _draft.decision)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
