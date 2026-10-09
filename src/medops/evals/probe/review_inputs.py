"""Explicit multi-gold reviewer inputs, shared by packing and provenance reconstruction."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from medops.core.canonical import canonical_json


def multi_gold_review_record(
    sample: Mapping[str, Any],
    documents: Mapping[str, dict],
    page_text: Callable[[str, int], str | None],
    parent: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Pack every gold and unique full page. Single-gold historical bytes stay on the old path.

    No prior verdicts, owner approvals, proposal rationale or chunk rankings enter this input.
    A missing page returns None for the provenance validator's existing offline semantics.
    """
    golds = sample["required_gold_evidence"]
    if len(golds) < 2:
        raise ValueError("multi-gold reviewer input needs at least two gold units")
    if sample.get("derived_from") and (parent is None or parent["sample_id"] != sample["derived_from"]):
        raise ValueError(f"{sample['sample_id']}: derived_from parent missing from the review scope")
    sources, pages, ids = {}, {}, set()
    packed = []
    for gold in golds:
        gid, source, number = gold["gold_id"], gold["source_hash"], gold["page"]
        if gid in ids:
            raise ValueError("duplicate gold id in reviewer input")
        ids.add(gid)
        doc = documents[source]
        if gold["version_label"] != doc["version_label"]:
            raise ValueError(f"{gid}: source version mismatch")
        text = page_text(source, number)
        if text is None:
            return None
        span, key = gold["evidence_span"], gold["key_text"]
        if (
            text.count(key) != 1
            or text[span["char_start"] : span["char_end"]] != span["text"]
            or key not in span["text"]
        ):
            raise ValueError(f"{gid}: key uniqueness or evidence span mismatch")
        sources[source] = {
            k: doc[k] for k in ("source_hash", "document_key", "title", "doc_type", "language", "version_label")
        }
        pages[(source, number)] = {"source_hash": source, "page": number, "text": text}
        packed.append(
            {
                k: gold[k]
                for k in ("gold_id", "source_hash", "version_label", "page", "section", "key_text", "evidence_span")
            }
        )
    record = {
        "record_format": "multi-gold-review-v1",
        **{k: sample[k] for k in ("sample_id", "query", "dept", "language", "slices")},
        "golds": packed,
        "evidence_rule": "all_gold_units_required; equivalent chunk mappings are alternatives within each unit",
        "documents": [sources[k] for k in sorted(sources)],
        "page_texts": [pages[k] for k in sorted(pages)],
    }
    if sample.get("conflict"):
        record["conflict"] = sample["conflict"]
    if sample.get("derived_from") and parent is not None:
        record["parent_query"] = parent["query"]
    # One wire order for new records; old one-gold order/variants remain unchanged.
    return json.loads(canonical_json(record))
