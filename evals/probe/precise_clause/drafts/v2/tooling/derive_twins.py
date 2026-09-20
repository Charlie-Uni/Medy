# -*- coding: utf-8 -*-
"""Build the draft English twin samples (spec-v1.1 derived samples) from v1 samples + twins_queries.json.

    python evals/probe/precise_clause/drafts/v2/tooling/derive_twins.py

Writes drafts/v2/samples_draft_EN.json in the draft shape review_pack.py consumes: for every v1 sample whose
gold document language is `en`, one twin with the next free sample_id (pc-0076..), the English query,
language=en, identical dept/slices/gold (gold_id re-prefixed) and `derived_from`. Mechanical checks: parent
exists and is English-gold, query distinct after norm-v1 and not equal to any key_text, key_text page-unique.
"""

import json
import pathlib
import sys

from medops.retrieval.lexical.normalization import normalize_text

REPO = pathlib.Path(__file__).resolve().parents[6]
V1 = REPO / "evals/probe/precise_clause/v1"
PAGES = V1 / "pages"
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v2"


def main() -> int:
    corpus = {d["source_hash"]: d for d in json.loads((V1 / "corpus.json").read_text(encoding="utf-8"))["documents"]}
    samples = [json.loads(l) for l in (V1 / "samples.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    queries = json.loads((DRAFTS / "twins_queries.json").read_text(encoding="utf-8"))["queries"]
    by_id = {s["sample_id"]: s for s in samples}
    next_id = max(int(s["sample_id"][3:]) for s in samples) + 1
    keys = {normalize_text(g["key_text"]) for s in samples for g in s["required_gold_evidence"]}
    seen = {normalize_text(s["query"]) for s in samples}
    twins, problems = [], []
    for parent_id in sorted(queries):
        parent = by_id.get(parent_id)
        if parent is None:
            problems.append(f"{parent_id}: no such v1 sample")
            continue
        gold = parent["required_gold_evidence"]
        if any(corpus[g["source_hash"]]["language"] != "en" for g in gold):
            problems.append(f"{parent_id}: gold document is not English")
        query = queries[parent_id].strip()
        nq = normalize_text(query)
        if nq in seen:
            problems.append(f"{parent_id}: twin query duplicates another query")
        if nq in keys:
            problems.append(f"{parent_id}: twin query equals a key_text")
        if not 4 <= len(query) <= 300:
            problems.append(f"{parent_id}: query length {len(query)}")
        seen.add(nq)
        sid = f"pc-{next_id:04d}"
        next_id += 1
        for g in gold:
            page = normalize_text((PAGES / g["source_hash"] / f"{g['page']}.txt").read_text(encoding="utf-8"))
            if page.count(g["key_text"]) != 1:
                problems.append(f"{parent_id}: parent key_text not page-unique")
        twins.append(
            {
                "sample_id": sid,
                "query": query,
                "dept": parent["dept"],
                "language": "en",
                "slices": list(parent["slices"]),
                "required_gold_evidence": [{**g, "gold_id": g["gold_id"].replace(parent_id, sid, 1)} for g in gold],
                "notes": f"spec-v1.1 English query twin of {parent_id}; gold, dept and slices inherited unchanged",
                "derived_from": parent_id,
            }
        )
    if problems:
        print("PROBLEMS:", *problems, sep="\n  ")
        return 1
    out = DRAFTS / "samples_draft_EN.json"
    out.write_text(json.dumps(twins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"EN: {len(twins)} twins -> {out.relative_to(REPO)}; ids {twins[0]['sample_id']}..{twins[-1]['sample_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
