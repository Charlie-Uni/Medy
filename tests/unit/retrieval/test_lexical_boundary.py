import math

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.contracts import ChunkRecord, LexicalCandidate, LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.bm25_offline import OfflineBM25Index
from medops.retrieval.lexical.boundary import MAX_K, run_lexical_search
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, RegexTokenizerV1

CORPUS = [ChunkRecord(chunk_id="c1", text="孕妇禁用。"), ChunkRecord(chunk_id="c2", text="每次 0.5 g，每日 2 次。")]


@pytest.fixture
def index():
    idx = OfflineBM25Index(RegexTokenizerV1())
    idx.index(CORPUS)
    return idx


def _ok(index, query="孕妇禁用", k=5):
    return run_lexical_search(index, query, k, expected=index.versions)


def test_request_bounds_and_strict_integer_k(index):
    for bad_k in (0, MAX_K + 1, True, 1.5, "5"):
        with pytest.raises(BusinessError) as exc:
            run_lexical_search(index, "孕妇", bad_k, expected=index.versions)  # type: ignore[arg-type]
        assert exc.value.code is ErrorCode.invalid_request, bad_k
    with pytest.raises(BusinessError, match="empty after normalization"):
        run_lexical_search(index, "   　 ", 5, expected=index.versions)


def test_expected_versions_are_mandatory_and_checked_against_the_index_build(index):
    with pytest.raises(TypeError):
        run_lexical_search(index, "孕妇禁用", 5)  # type: ignore[call-arg]
    drifted = index.versions.model_copy(update={"tokenizer_version": "tok-jieba-v1"})
    with pytest.raises(BusinessError) as exc:
        run_lexical_search(index, "孕妇禁用", 5, expected=drifted)
    assert exc.value.code is ErrorCode.version_conflict and "index=" in (exc.value.detail or "")
    assert _ok(index).candidates[0].chunk_id == "c1"


def test_tokenizer_swap_without_rebuild_is_refused_and_rebuild_updates_versions(index):
    pytest.importorskip("jieba")
    built = index.versions
    index.tokenizer = JiebaTokenizerV1()  # configuration drift without index()
    assert index.versions == built  # declared versions stay bound to the build
    with pytest.raises(InfrastructureError) as exc:
        index.search("孕妇禁用", 5)
    assert exc.value.code is ErrorCode.internal_error and exc.value.retryable is False
    index.index(CORPUS)  # rebuild with the new tokenizer
    assert index.versions != built and index.versions.tokenizer_version == "tok-jieba-v1"
    assert run_lexical_search(index, "孕妇禁用", 5, expected=index.versions).candidates[0].chunk_id == "c1"


class _Adapter:
    def __init__(self, base: OfflineBM25Index, behaviour: str) -> None:
        self.base, self.behaviour = base, behaviour

    @property
    def versions(self) -> LexicalVersions:
        return self.base.versions

    def search(self, query: str, k: int) -> LexicalSearchResult:
        real = self.base.search(query, k)
        if self.behaviour == "versions":
            return real.model_copy(update={"dictionary_version": "someone-elses-dict"})
        if self.behaviour == "requested_k":
            return real.model_copy(update={"requested_k": k + 1, "candidate_exhausted": True})
        if self.behaviour == "count":  # constructed without validation: claims 1 but carries 2
            return LexicalSearchResult.model_construct(
                **{**real.model_dump(), "candidates": real.candidates + real.candidates, "returned_count": 1}
            )
        return real  # type: ignore[unreachable]


@pytest.mark.parametrize("behaviour", ["versions", "requested_k", "count"])
def test_adapter_contract_violations_fail_closed(index, behaviour):
    with pytest.raises(InfrastructureError) as exc:
        run_lexical_search(_Adapter(index, behaviour), "孕妇禁用", 5, expected=index.versions)
    assert exc.value.code is ErrorCode.internal_error and exc.value.retryable is False


def test_result_model_rejects_non_finite_scores_bad_order_and_is_immutable():
    common = dict(
        requested_k=5,
        returned_count=2,
        candidate_exhausted=True,
        retriever_version="r",
        tokenizer_version="t",
        dictionary_version="d",
        normalization_version="norm-v1",
    )
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            LexicalSearchResult(
                candidates=(LexicalCandidate(chunk_id="a", raw_score=bad, rank=1),), **{**common, "returned_count": 1}
            )
    with pytest.raises(ValueError, match="non-increasing"):
        LexicalSearchResult(
            candidates=(
                LexicalCandidate(chunk_id="a", raw_score=1.0, rank=1),
                LexicalCandidate(chunk_id="b", raw_score=2.0, rank=2),
            ),
            **common,
        )
    with pytest.raises(ValueError, match="chunk_id ascending"):
        LexicalSearchResult(
            candidates=(
                LexicalCandidate(chunk_id="z", raw_score=1.0, rank=1),
                LexicalCandidate(chunk_id="a", raw_score=1.0, rank=2),
            ),
            **common,
        )
    ok = LexicalSearchResult(
        candidates=(
            LexicalCandidate(chunk_id="a", raw_score=1.0, rank=1),
            LexicalCandidate(chunk_id="b", raw_score=1.0, rank=2),
        ),
        **common,
    )
    with pytest.raises(AttributeError):
        ok.candidates.append(ok.candidates[0])  # type: ignore[attr-defined]


class _MutatingAdapter:
    """Changes its declared versions DURING the call and stamps the result with the new ones."""

    def __init__(self, base: OfflineBM25Index) -> None:
        self.base, self._dict = base, base.versions.dictionary_version

    @property
    def versions(self) -> LexicalVersions:
        return self.base.versions.model_copy(update={"dictionary_version": self._dict})

    def search(self, query: str, k: int) -> LexicalSearchResult:
        self._dict = self._dict + "+swapped-mid-call"
        return self.base.search(query, k).model_copy(update={"dictionary_version": self._dict})


def test_versions_changed_during_the_call_are_rejected_against_the_pre_call_snapshot(index):
    adapter = _MutatingAdapter(index)
    with pytest.raises(InfrastructureError) as exc:
        run_lexical_search(adapter, "孕妇禁用", 5, expected=adapter.versions)
    assert exc.value.code is ErrorCode.internal_error and "declared" in (exc.value.detail or "")


class _InvalidConstructionAdapter:
    """Builds an invalid LexicalSearchResult through the normal constructor inside search()."""

    def __init__(self, base: OfflineBM25Index) -> None:
        self.base = base

    @property
    def versions(self) -> LexicalVersions:
        return self.base.versions

    def search(self, query: str, k: int) -> LexicalSearchResult:
        real = self.base.search(query, k)
        return LexicalSearchResult(**{**real.model_dump(), "returned_count": real.returned_count + 1})


def test_validation_error_inside_the_adapter_becomes_a_non_retryable_internal_error(index):
    with pytest.raises(InfrastructureError) as exc:
        run_lexical_search(_InvalidConstructionAdapter(index), "孕妇禁用", 5, expected=index.versions)
    assert exc.value.code is ErrorCode.internal_error and exc.value.retryable is False


class _RaisingAdapter:
    """Raises a domain-typed error from inside search(); the boundary must pass it through untouched."""

    def __init__(self, base: OfflineBM25Index, error: Exception) -> None:
        self.base, self.error = base, error

    @property
    def versions(self) -> LexicalVersions:
        return self.base.versions

    def search(self, query: str, k: int) -> LexicalSearchResult:
        raise self.error


@pytest.mark.parametrize(
    "error",
    [
        BusinessError(ErrorCode.forbidden, "no MA:read scope"),
        InfrastructureError(ErrorCode.dependency_timeout, detail="postgres statement timeout"),
    ],
)
def test_adapter_raised_business_and_infrastructure_errors_pass_through_unchanged(index, error):
    with pytest.raises(type(error)) as exc:
        run_lexical_search(_RaisingAdapter(index, error), "孕妇禁用", 5, expected=index.versions)
    assert exc.value is error  # same object, not re-wrapped
