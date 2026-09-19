import pytest

from medops.retrieval.contracts import ChunkRecord, LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.bm25_offline import OfflineBM25Index
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, RegexTokenizerV1
from tests.unit.retrieval.lexical_contract import assert_lexical_adapter_contract


@pytest.mark.parametrize("tokenizer_factory", [RegexTokenizerV1, JiebaTokenizerV1], ids=["regex", "jieba"])
def test_offline_bm25_satisfies_the_adapter_contract(tokenizer_factory):
    pytest.importorskip("jieba")

    def build(corpus):
        idx = OfflineBM25Index(tokenizer_factory())
        idx.index(list(corpus))
        return idx

    assert_lexical_adapter_contract(build)


class _FirstOnlyAdapter:
    """Always returns at most the first matching chunk and claims exhaustion: must FAIL the contract."""

    def __init__(self, corpus):
        self.base = OfflineBM25Index(RegexTokenizerV1())
        self.base.index(list(corpus))

    @property
    def versions(self) -> LexicalVersions:
        return self.base.versions

    def search(self, query: str, k: int) -> LexicalSearchResult:
        real = self.base.search(query, k)
        first = real.candidates[:1]
        return real.model_copy(
            update={"candidates": first, "returned_count": len(first), "candidate_exhausted": len(first) < k}
        )


def test_contract_harness_detects_undercounting_adapters():
    with pytest.raises(AssertionError, match="returned 1, expected"):
        assert_lexical_adapter_contract(lambda corpus: _FirstOnlyAdapter(corpus))


def test_fixture_corpus_is_well_formed():
    from tests.unit.retrieval.lexical_contract import FIXTURE_TERMS, build_fixture_corpus

    corpus = build_fixture_corpus()
    assert len(corpus) == max(FIXTURE_TERMS.values()) and len({c.chunk_id for c in corpus}) == len(corpus)
    assert sum("beta" in c.text.split() for c in corpus) == FIXTURE_TERMS["beta"]
    assert isinstance(corpus[0], ChunkRecord)
