"""Shared harness test support; no collected test cases."""

from __future__ import annotations

from datetime import UTC, datetime

from medops.domain.state import MAX_CANDIDATES, CandidateRef, SourceRank
from medops.harness.contracts import NodeSpec
from medops.harness.dependencies import HarnessDeps, default_specs
from medops.harness.retrieval_port import RetrievalOutcome, RetrievalRequest
from medops.harness.runtime import initial_state
from tests.support.harness_data import user, versions

LABEL = "年齡 6 至 12 歲的孩童：口服，100 mg，一天三次；或 300 mg 當作一個單一劑量，一天一次。"


CONTRA = "Losartan potassium 禁用於對本項產品任何組成過敏者。"


class FakeRetrieval:
    def __init__(self, *evidence_items, degraded=False):
        self.items = tuple(evidence_items)
        self.degraded = degraded
        self.requests: list[RetrievalRequest] = []

    def model_requests(self, request):
        return ()  # this fixture never invokes a hosted model

    def retrieve(self, request):
        self.requests.append(request)
        cands = tuple(
            CandidateRef(chunk_id=e.citation.chunk_id, source_ranks=(SourceRank(source="lexical", rank=i),))
            for i, e in enumerate(self.items, 1)
        )
        return RetrievalOutcome(
            rewritten_queries=(request.query,),
            candidates=cands[:MAX_CANDIDATES],
            evidence=self.items,
            degraded=self.degraded,
        )


def fast_specs():
    return {
        k: NodeSpec(name=k, timeout_s=v.timeout_s, max_retries=v.max_retries, backoff_base_s=0)
        for k, v in default_specs().items()
    }


def make_deps(retrieval, gateway, **kw):
    return HarnessDeps(
        retrieval=retrieval,
        gateway=gateway,
        answer_model_id="gpt-6-sol",
        specs=fast_specs(),
        sleep=lambda s: None,
        clock=lambda: datetime(2026, 9, 23, tzinfo=UTC),
        **kw,
    )


def state(query="拔痛酸錠用於6至12歲兒童時口服劑量如何給予？", **kw):
    return initial_state(user=user(), query=query, versions=versions(), trace_id="a" * 32, **kw)
