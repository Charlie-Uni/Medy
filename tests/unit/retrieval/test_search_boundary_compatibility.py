"""Both channels preserve legacy adapters and reject result/version drift through their public boundaries."""

import pytest
from pydantic import ValidationError

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.boundary import run_lexical_search
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.contracts import VectorSearchResult, VectorVersions


@pytest.fixture(params=["lexical", "vector"])
def channel(request):
    fields = {"retriever_version": "test-v1", "normalization_version": "norm-v1"}
    if request.param == "lexical":
        return (
            run_lexical_search,
            LexicalSearchResult,
            LexicalVersions(**fields, tokenizer_version="tok-test", dictionary_version="dict-test"),
        )
    return run_vector_search, VectorSearchResult, VectorVersions(**fields, embedding_version="emb-test")


def empty_result(model, versions, k=1):
    return model(candidates=(), requested_k=k, returned_count=0, candidate_exhausted=True, **versions.model_dump())


def test_legacy_signature_gets_original_query_and_historical_flag_without_new_keyword(channel):
    run, model, versions = channel
    calls = []

    class LegacyAdapter:
        def search(self, query, k, *, allow_historical=False):
            calls.append((query, k, allow_historical))
            return empty_result(model, versions, k)

    adapter = LegacyAdapter()
    adapter.versions = versions
    assert run(adapter, "  Ａspirin　", 1, expected=versions, allow_historical=True).versions == versions
    assert calls == [("  Ａspirin　", 1, True)]


@pytest.mark.parametrize("doc_ids", [[], ["doc-a"]])
def test_explicit_document_filter_is_never_dropped_or_broadened(channel, doc_ids):
    run, model, versions = channel
    calls = []

    class Adapter:
        def search(self, query, k, *, allow_historical=False, doc_ids=None):
            calls.append(doc_ids)
            return empty_result(model, versions, k)

    adapter = Adapter()
    adapter.versions = versions
    run(adapter, "query", 1, expected=versions, doc_ids=doc_ids)
    assert len(calls) == 1 and calls[0] is doc_ids


def test_declared_versions_are_bound_before_the_adapter_can_mutate_them(channel):
    run, model, versions = channel

    class Adapter:
        def search(self, query, k, *, allow_historical=False):
            self.versions = versions.model_copy(update={"retriever_version": "swapped-v2"})
            return empty_result(model, self.versions, k)

    adapter = Adapter()
    adapter.versions = versions
    with pytest.raises(InfrastructureError) as caught:
        run(adapter, "query", 1, expected=versions)
    assert caught.value.code is ErrorCode.internal_error and caught.value.retryable is False
    assert "!= declared" in caught.value.detail


def test_invalid_result_constructed_inside_search_is_a_nonretryable_adapter_failure(channel):
    run, model, versions = channel

    class Adapter:
        def search(self, query, k, *, allow_historical=False):
            return model(**{**empty_result(model, versions, k).model_dump(), "returned_count": 2})

    adapter = Adapter()
    adapter.versions = versions
    with pytest.raises(InfrastructureError) as caught:
        run(adapter, "query", 1, expected=versions)
    assert isinstance(caught.value.__context__, ValidationError)
    assert caught.value.detail == "adapter produced an invalid result: 1 error(s)" and not caught.value.retryable


@pytest.mark.parametrize(
    "error",
    [BusinessError(ErrorCode.forbidden, "no scope"), InfrastructureError(ErrorCode.dependency_timeout)],
)
def test_domain_errors_propagate_as_the_same_object(channel, error):
    run, _, versions = channel

    class Adapter:
        def search(self, query, k, *, allow_historical=False):
            raise error

    adapter = Adapter()
    adapter.versions = versions
    with pytest.raises(type(error)) as caught:
        run(adapter, "query", 1, expected=versions)
    assert caught.value is error
