"""Build the DEC-003 verifier comparison set from frozen, already-reviewed data (no new annotation).

    python evals/verifier/tools/build_pairs.py --out evals/verifier/dec003/pairs.jsonl [--seed 20260923]

Each answerable sample of `main-v1-provisional` whose gold maps to a chunk yields:
  supported            statement = gold key_text, evidence = the mapped gold chunk text
  not_supported/same   statement = key_text, evidence = the nearest chunk of the same document that does not contain it
  not_supported/other  statement = key_text, evidence = a chunk of another document (seeded random)
  contradicted/numeric statement = key_text with its first dose/time/frequency number changed, evidence = gold chunk
  contradicted/negation statement = key_text with its negation flipped, evidence = gold chunk
Labels are mechanical (containment, number edit, negation edit); the transformation is recorded per pair so a
reviewer can audit any label. Slices, dept and language come from the sample. Page texts never enter Git: this
file is regenerated locally (`evals/verifier/dec003/` is gitignored except for the reports).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/main_set/tools"))
import draft_common as dc  # noqa: E402

from medops.domain.verification import ElementKind  # noqa: E402
from medops.verification.elements import extract, normalize_for_match  # noqa: E402
from medops.verification.rules import negated  # noqa: E402

DATASET = REPO / "evals/main_set/main-v1-provisional"
SNAPSHOT = REPO / "evals/experiments/e2e/main-v1-provisional/chunks.snapshot.json"
MAPPING = REPO / "evals/experiments/e2e/main-v1-provisional/chunk_mapping.chunker-v2.main-v1-provisional.json"

_ZH_NEG = ("不得", "不可", "不應", "不应", "不宜", "禁止", "禁用", "不建議", "不建议", "無需", "无需", "不需要", "不要", "不能", "避免")
_EN_NEG = (" should not ", " must not ", " do not ", " does not ", " cannot ", " not ", " no ", " never ", " without ")


def chunk_texts(snapshot: dict) -> dict[str, dict]:
    out = {}
    for c in snapshot["chunks"]:
        parts = []
        for sp in c["spans"]:
            page = dc.page_text(c["source_hash"], sp["page"])
            if page is None:
                parts = []
                break
            parts.append(page[sp["char_start"] : sp["char_end"]])
        if parts:
            out[c["chunk_id"]] = {
                "text": "\n".join(parts),
                "source_hash": c["source_hash"],
                "page": c["spans"][0]["page"],
                "start": c["spans"][0]["char_start"],
            }
    return out


def perturb_number(statement: str) -> tuple[str, str] | None:
    for el in extract(statement):
        if el.kind not in (ElementKind.dose, ElementKind.time_window, ElementKind.frequency):
            continue
        m = re.search(r"\d+(?:[.,]\d+)?", el.text)
        if not m:
            continue
        raw = m.group(0)
        try:
            value = float(raw.replace(",", "")) if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw) else float(raw.replace(",", "."))
        except ValueError:
            continue
        new_value = value * 2 if value > 0 else 1
        new_raw = str(int(new_value)) if float(new_value).is_integer() else f"{new_value:g}"
        new_el = el.text[: m.start()] + new_raw + el.text[m.end() :]
        return statement[: el.start] + new_el + statement[el.end :], f"{el.kind.value}:{raw}->{new_raw}"
    return None


def flip_negation(statement: str) -> tuple[str, str] | None:
    if negated(statement):
        for cue in _ZH_NEG:
            if cue in statement:
                return statement.replace(cue, "", 1), f"remove:{cue}"
        for cue in _EN_NEG:
            if cue in statement:
                return statement.replace(cue, " ", 1), f"remove:{cue.strip()}"
        return None
    m = re.search(r"(應|应|須|须|需要|可以|可|should|must|may|can)\s", statement)
    if m:
        insert = " not " if m.group(1).isascii() else "不"
        return statement[: m.end(1)] + insert + statement[m.end(1) :], f"insert:{insert.strip()}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/pairs.jsonl")
    ap.add_argument("--seed", type=int, default=20260923)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    samples = [json.loads(l) for l in (DATASET / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    mapping = {e["gold_id"]: e for e in json.load(open(MAPPING, encoding="utf-8"))["entries"]}
    chunks = chunk_texts(json.load(open(SNAPSHOT, encoding="utf-8")))
    by_source: dict[str, list[str]] = {}
    for cid, c in chunks.items():
        by_source.setdefault(c["source_hash"], []).append(cid)
    pairs = []
    stats = {"samples": 0, "unmapped": 0, "no_text": 0}
    for s in samples:
        if s.get("answerable", True) is False:
            continue
        gold = s["required_gold_evidence"][0]
        entry = mapping.get(gold["gold_id"])
        if not entry or entry["status"] != "mapped":
            stats["unmapped"] += 1
            continue
        gold_chunk = entry["chunk_ids"][0]
        if gold_chunk not in chunks:
            stats["no_text"] += 1
            continue
        stats["samples"] += 1
        statement = gold["key_text"]
        needle = normalize_for_match(statement)
        base = {"sample_id": s["sample_id"], "slices": s["slices"], "dept": s["dept"], "language": s["language"], "document_source_hash": gold["source_hash"]}

        def add(kind: str, text: str, chunk_id: str, transformation: str = "") -> None:
            pairs.append({
                **base,
                "pair_id": f"{s['sample_id']}:{kind}",
                "kind": kind,
                "label": kind.split("/")[0],
                "statement": text,
                "evidence_chunk_id": chunk_id,
                "evidence_text": chunks[chunk_id]["text"],
                "transformation": transformation,
            })

        add("supported", statement, gold_chunk)
        same = [
            cid for cid in by_source[gold["source_hash"]]
            if cid != gold_chunk and needle not in normalize_for_match(chunks[cid]["text"])
        ]
        if same:
            g = chunks[gold_chunk]
            same.sort(key=lambda cid: (abs(chunks[cid]["page"] - g["page"]), abs(chunks[cid]["start"] - g["start"])))
            add("not_supported/same_doc", statement, same[0])
        others = [h for h in by_source if h != gold["source_hash"]]
        if others:
            pool = by_source[rng.choice(others)]
            cand = [cid for cid in pool if needle not in normalize_for_match(chunks[cid]["text"])]
            if cand:
                add("not_supported/other_doc", statement, rng.choice(cand))
        num = perturb_number(statement)
        if num:
            add("contradicted/numeric", num[0], gold_chunk, num[1])
        neg = flip_negation(statement)
        if neg and neg[0] != statement:
            add("contradicted/negation", neg[0], gold_chunk, neg[1])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    kinds: dict[str, int] = {}
    for p in pairs:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    summary = {**stats, "pairs": len(pairs), "by_kind": kinds}
    (args.out.parent / "pairs_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
