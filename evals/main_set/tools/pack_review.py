"""Package confirmed draft samples for the LLM second reviewer (spec-m1 §4 step 3).

    python evals/main_set/tools/pack_review.py MA PV CO EN NA

Writes drafts/main-v1/review/input_<batch>.jsonl (gitignored: contains page text). Record shapes are exactly the
ones `medops.evals.probe.review_provenance._current_records` rebuilds at validation time: answerable samples get
the gold page text (twins add `parent_query`); no-answer samples get the scope document's packed pages
(`abstention.document_pages`) as `document_text`.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_common as dc  # noqa: E402

from medops.evals.probe.review_inputs import multi_gold_review_record  # noqa: E402
from medops.evals.probe.review_provenance import no_answer_document_text  # noqa: E402
from medops.evals.probe.validator import PageTextProvider  # noqa: E402

OUT = dc.DRAFTS / "review"


class _Pages(PageTextProvider):
    def __init__(self) -> None:  # noqa: D107 - both page roots are searched
        pass

    def page_text(self, source_hash: str, page: int) -> str | None:  # type: ignore[override]
        return dc.page_text(source_hash, page)


def pack(samples: list[dict], corpus_by_key: dict[str, dict], parents: dict[str, dict]) -> list[dict]:
    by_hash = {d["source_hash"]: d for d in corpus_by_key.values()}
    pages = _Pages()
    records = []
    for s in samples:
        if s.get("answerable", True) is False:
            ab = s["abstention"]
            d = corpus_by_key[ab["scope_document_key"]]
            text = no_answer_document_text(pages, d["source_hash"], list(ab["document_pages"]))
            if text is None:
                raise ValueError(f"{s['sample_id']}: page text missing for {d['document_key']}")
            records.append(
                {
                    "sample_id": s["sample_id"],
                    "query": s["query"],
                    "dept": s["dept"],
                    "language": s["language"],
                    "slices": s["slices"],
                    "answerable": False,
                    "abstention": {k: ab[k] for k in ("scope_document_key", "topic", "absence_check")},
                    "document": {k: d[k] for k in ("document_key", "title", "doc_type", "language")},
                    "document_text": text,
                }
            )
            continue
        if len(s["required_gold_evidence"]) > 1:
            record = multi_gold_review_record(s, by_hash, dc.page_text, parents.get(s.get("derived_from")))
            if record is None:
                raise ValueError(f"{s['sample_id']}: reviewer page missing")
            records.append(record)
            continue
        if len(s["required_gold_evidence"]) != 1:
            raise ValueError(f"{s['sample_id']}: answerable reviewer pack requires gold")
        g = s["required_gold_evidence"][0]
        d = by_hash[g["source_hash"]]
        page_text = dc.page_text(g["source_hash"], g["page"])
        if page_text is None or page_text.count(g["key_text"]) != 1:
            raise ValueError(f"{s['sample_id']}: key_text is not page-unique or page missing")
        span = g["evidence_span"]
        if page_text[span["char_start"] : span["char_end"]] != span["text"] or g["key_text"] not in span["text"]:
            raise ValueError(f"{s['sample_id']}: evidence span mismatch")
        rec = {
            "sample_id": s["sample_id"],
            "query": s["query"],
            "dept": s["dept"],
            "language": s["language"],
            "slices": s["slices"],
            "gold": {"page": g["page"], "section": g["section"], "key_text": g["key_text"], "evidence_span": span},
            "document": {k: d[k] for k in ("document_key", "title", "doc_type", "language")},
            "page_text": page_text,
        }
        if s.get(
            "conflict"
        ):  # spec-m1: the reviewer sees the family/current-version declaration and the synthetic note
            rec["conflict"] = s["conflict"]
        if s.get("notes"):
            rec["notes"] = s["notes"]
        if s.get("derived_from"):
            rec["parent_query"] = parents[s["derived_from"]]["query"]
        records.append(rec)
    return records


def main(batches: list[str]) -> None:
    corpus = dc.load_corpus()
    OUT.mkdir(parents=True, exist_ok=True)
    parents: dict[str, dict] = {}
    for b in ("MA", "PV", "CO"):
        p = dc.DRAFTS / f"samples_draft_{b}.json"
        if p.exists():
            parents.update({s["sample_id"]: s for s in json.loads(p.read_text(encoding="utf-8"))})
    for batch in batches:
        samples = json.loads((dc.DRAFTS / f"samples_draft_{batch}.json").read_text(encoding="utf-8"))
        lines = [json.dumps(r, ensure_ascii=False) for r in pack(samples, corpus, parents)]
        path = OUT / f"input_{batch}.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{batch}: {len(lines)} samples -> {path.relative_to(dc.REPO)}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["MA", "PV", "CO", "EN", "NA"])
