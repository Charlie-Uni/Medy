"""Output policy views are singleflight, immutable and tied to their runtime's scorer."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from tests.unit.bootstrap.test_composition import settings

from medops.bootstrap import retrieval as mod
from medops.bootstrap.retrieval import RetrievalServices
from medops.retrieval.rerank import OverlapReranker, RerankerView


def test_concurrent_policy_setup_constructs_one_view_and_reuses_the_same_scorer(monkeypatch):
    base = OverlapReranker(output=8)
    resources = RetrievalServices(settings(), None, base)
    calls = []
    barrier = threading.Barrier(8)

    def construct(scorer, *, output):
        calls.append((scorer, output))
        return RerankerView(scorer, output=output)

    monkeypatch.setattr(mod, "RerankerView", construct)

    def get(_):
        barrier.wait(timeout=2)
        return resources.reranker_for(4)

    with ThreadPoolExecutor(max_workers=8) as pool:
        views = list(pool.map(get, range(8)))
    assert all(view is views[0] for view in views)
    assert calls == [(base, 4)] and resources.reranker_for(8) is base
    assert resources.reranker_for(5)._scorer is base
    assert views[0].spec.output == 4 and base.spec.output == 8
    assert resources.reranker_for(4) is views[0]  # rollback/reselection does not initialize again


def test_view_initialization_failure_does_not_cache_a_broken_result(monkeypatch):
    resources = RetrievalServices(settings(), None, OverlapReranker())
    calls = []

    def construct(scorer, *, output):
        calls.append(output)
        if len(calls) == 1:
            raise RuntimeError("initialization failure")
        return RerankerView(scorer, output=output)

    monkeypatch.setattr(mod, "RerankerView", construct)
    with pytest.raises(RuntimeError):
        resources.reranker_for(4)
    assert 4 not in resources._rerankers
    assert resources.reranker_for(4).spec.output == 4 and calls == [4, 4]


@pytest.mark.parametrize("output", [0, 21, True, 8.0, "8"])
def test_invalid_configuration_cannot_alias_a_valid_cache_entry_or_grow_the_cache(output):
    resources = RetrievalServices(settings(), None, OverlapReranker())
    with pytest.raises(ValueError, match="invalid reranker output"):
        resources.reranker_for(output)
    assert list(resources._rerankers) == [8]


def test_owners_with_different_revisions_never_share_scorers():
    first, second = OverlapReranker(), OverlapReranker()
    second._spec = second.spec.model_copy(update={"model_revision": "other-revision"})
    a = RetrievalServices(settings(), None, first).reranker_for(4)
    b = RetrievalServices(settings(), None, second).reranker_for(4)
    assert a._scorer is first and b._scorer is second and a._scorer is not b._scorer
    assert a.spec.model_revision == "test" and b.spec.model_revision == "other-revision"
