"""Package confirmed draft samples for the LLM second reviewer (SPEC section 8).

    python evals/probe/precise_clause/drafts/v1/tooling/review_pack.py MA PV CO

Writes drafts/v1/review/input_<batch>.jsonl: one line per sample with the fields the reviewer judges plus
the norm-v1 page text of the gold page, so the reviewer needs nothing else besides v1/review_prompt.md.
The reviewer answers in drafts/v1/review/verdicts_<batch>.jsonl (format fixed by review_prompt.md).
"""

import json
import pathlib
import sys

from medops.retrieval.lexical.normalization import normalize_text

REPO = pathlib.Path(__file__).resolve().parents[6]
V1 = REPO / "evals/probe/precise_clause/v1"
DRAFTS = REPO / "evals/probe/precise_clause/drafts/v1"
OUT = DRAFTS / "review"


def pack_samples(samples: list[dict], corpus: dict, pages_dir: pathlib.Path) -> list[dict]:
    records = []
    for s in samples:
        if len(s["required_gold_evidence"]) != 1:
            raise ValueError(f"{s['sample_id']}: reviewer pack currently requires exactly one gold")
        g = s["required_gold_evidence"][0]
        d = corpus[g["source_hash"]]
        page_text = normalize_text((pages_dir / g["source_hash"] / f"{g['page']}.txt").read_text(encoding="utf-8"))
        if page_text.count(g["key_text"]) != 1:
            raise ValueError(f"{s['sample_id']}: key_text is not page-unique")
        span = g["evidence_span"]
        if page_text[span["char_start"] : span["char_end"]] != span["text"] or g["key_text"] not in span["text"]:
            raise ValueError(f"{s['sample_id']}: evidence span mismatch")
        records.append(
            {
                "sample_id": s["sample_id"],
                "query": s["query"],
                "dept": s["dept"],
                "language": s["language"],
                "slices": s["slices"],
                "gold": {"page": g["page"], "section": g["section"], "key_text": g["key_text"], "evidence_span": span},
                "document": {
                    "document_key": d["document_key"],
                    "title": d["title"],
                    "doc_type": d["doc_type"],
                    "language": d["language"],
                },
                "page_text": page_text,
            }
        )
    return records


def main(batches: list[str]) -> None:
    corpus = {d["source_hash"]: d for d in json.loads((V1 / "corpus.json").read_text(encoding="utf-8"))["documents"]}
    OUT.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        samples = json.loads((DRAFTS / f"samples_draft_{batch}.json").read_text(encoding="utf-8"))
        lines = [json.dumps(r, ensure_ascii=False) for r in pack_samples(samples, corpus, V1 / "pages")]
        path = OUT / f"input_{batch}.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{batch}: {len(lines)} samples -> {path.relative_to(REPO)}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["MA", "PV", "CO"])
