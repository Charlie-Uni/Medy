"""Give the LLM reviewer enough of each no-answer scope document to judge absence (record 50 §12).

    python evals/main_set/tools/na_pages_relevant.py [--max-chars 100000] [--dry-run]

The drafting-time page selection (≤ 14 pages chosen for clause density) is a poor basis for an absence verdict: the
reviewer rightly disputed samples whose most relevant pages were missing. For every no-answer sample this sets
`abstention.document_pages` to all pages when the document fits in --max-chars, otherwise to the drafting pages plus
the pages ranked highest by overlap with the query, topic and absence terms, within the budget. Samples whose page
list changes are written to review/na_changed_ids.txt for a targeted re-review (--only).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

OUT_IDS = dc.DRAFTS / "review/na_changed_ids.txt"


def query_terms(s: dict) -> list[str]:
    text = " ".join([s["query"], s["abstention"]["topic"], " ".join(s["_draft"].get("absence_hits", {}).keys())])
    latin = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)]
    cjk = re.findall(r"[一-鿿]{2,}", text)
    bigrams = {c[i : i + 2] for c in cjk for i in range(len(c) - 1)}
    return sorted(set(latin) | bigrams)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chars", type=int, default=100000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    corpus = dc.load_corpus()
    path = dc.DRAFTS / "samples_draft_NA.json"
    na = json.loads(path.read_text(encoding="utf-8"))
    changed = []
    for s in na:
        d = corpus[s["abstention"]["scope_document_key"]]
        texts = {p: dc.page_text(d["source_hash"], p) or "" for p in range(1, d["pages"] + 1)}
        total = sum(len(t) for t in texts.values())
        before = list(s["abstention"]["document_pages"])
        if total <= args.max_chars:
            pages = [p for p, t in texts.items() if t.strip()]
        else:
            terms = query_terms(s)
            scored = sorted(texts, key=lambda p: (-sum(texts[p].lower().count(t) for t in terms), p))
            keep = set(before)
            used = sum(len(texts[p]) for p in keep)
            for p in scored:
                if p in keep:
                    continue
                if used + len(texts[p]) > args.max_chars:
                    continue
                keep.add(p)
                used += len(texts[p])
            pages = sorted(keep)
        if pages != before:
            s["abstention"]["document_pages"] = pages
            s["_draft"]["decision"] = (s["_draft"].get("decision", "") + "; reviewer pages widened").lstrip("; ")
            changed.append((s["sample_id"], d["document_key"], len(before), len(pages), d["pages"]))
    for c in changed:
        print(f"{c[0]} {c[1]}: pages {c[2]} -> {c[3]} of {c[4]}")
    print(f"{len(changed)} samples changed")
    if not args.dry_run:
        path.write_text(json.dumps(na, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUT_IDS.parent.mkdir(exist_ok=True)
        OUT_IDS.write_text("\n".join(c[0] for c in changed) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
