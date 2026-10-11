"""Reranker stage: operates on re-checked Evidence only, bounded input/output, deterministic tie-break."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from medops.domain import Citation, DocStatus, Evidence
from medops.retrieval.rerank import MAX_INPUT, OverlapReranker, RerankerView, rank_evidence, rerank_evidence


def ev(chunk_id: str, text: str) -> Evidence:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Evidence(
        citation=Citation(
            doc_id="d1", version="v1", effective_date=date(2026, 1, 1), page=1, section="s", chunk_id=chunk_id
        ),
        text=text,
        evidence_text_hash=h,
        chunk_content_hash=h,
        status=DocStatus.active,
    )


def test_rerank_orders_by_score_breaks_ties_by_chunk_id_and_caps_output():
    r = OverlapReranker(output=2)
    items = [ev("c3", "无关内容"), ev("c2", "阿司匹林 每日 2 次"), ev("c1", "阿司匹林 每日 2 次"), ev("c4", "阿司匹林")]
    ranked = rerank_evidence(r, "阿司匹林 每日 2 次", items)
    assert [(x.evidence.citation.chunk_id, x.rank) for x in ranked] == [("c1", 1), ("c2", 2)]
    assert ranked[0].score == ranked[1].score == 1.0
    assert rerank_evidence(r, "q", []) == ()
    with pytest.raises(ValueError, match="exceeds"):
        rerank_evidence(r, "q", [ev(f"c{i}", "x") for i in range(MAX_INPUT + 1)])
    assert r.spec.rerank_params()["max_input"] == MAX_INPUT and r.spec.output == 2


def test_score_count_mismatch_is_refused():
    class Broken(OverlapReranker):
        def score(self, query, texts):
            return [1.0]

    with pytest.raises(ValueError, match="score count"):
        rerank_evidence(Broken(), "q", [ev("a", "x"), ev("b", "y")])


def test_output_views_share_scores_preserve_ties_and_never_mutate_other_configuration():
    scorer = OverlapReranker(output=8)
    small, large = RerankerView(scorer, output=2), RerankerView(scorer, output=4)
    items = [ev("c3", "minor"), ev("c2", "audit"), ev("c1", "audit"), ev("c4", "audit critical")]
    expected = rank_evidence(scorer, "audit critical", items)
    assert rank_evidence(small, "audit critical", items) == expected == rank_evidence(large, "audit critical", items)
    assert rerank_evidence(small, "audit critical", items) == expected[:2]
    assert rerank_evidence(large, "audit critical", items) == expected[:4]
    assert [e.evidence.citation.chunk_id for e in expected] == ["c4", "c1", "c2", "c3"]
    assert small._scorer is large._scorer is scorer
    assert scorer.spec.output == 8 and small.spec.output == 2 and large.spec.output == 4
    with pytest.raises(FrozenInstanceError):
        small.spec = large.spec


@pytest.mark.parametrize("output", [0, 21, True, 8.5, "8"])
def test_invalid_output_view_is_rejected(output):
    with pytest.raises(ValueError, match="invalid reranker output"):
        RerankerView(OverlapReranker(), output=output)
