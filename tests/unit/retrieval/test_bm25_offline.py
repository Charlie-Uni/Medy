import pytest

from medops.retrieval.contracts import ChunkRecord, LexicalSearchResult
from medops.retrieval.lexical.bm25_offline import OfflineBM25Index
from medops.retrieval.lexical.tokenizer import RegexTokenizerV1

CORPUS = [
    ChunkRecord(chunk_id="c1", text="成人常用量：口服，每次 0.5 g，每日 2 次，疗程 7 天。"),
    ChunkRecord(chunk_id="c2", text="对本品过敏者禁用；孕妇禁用。"),
    ChunkRecord(chunk_id="c3", text="研究者在获知 SAE 后应在 24 小时内向申办方报告，方案编号 PROT-2024-017。"),
    ChunkRecord(chunk_id="c4", text="严重不良事件应在获知后 14 天内提交随访报告。"),
]


@pytest.fixture
def index():
    idx = OfflineBM25Index(RegexTokenizerV1())
    idx.index(CORPUS)
    return idx


def test_precise_clause_queries_hit_expected_chunk(index):
    assert index.search("PROT-2024-017 报告", k=2).candidates[0].chunk_id == "c3"
    assert index.search("孕妇禁用", k=1).candidates[0].chunk_id == "c2"
    assert index.search("14 天内", k=1).candidates[0].chunk_id == "c4"


def test_result_contract_and_exhaustion(index):
    result = index.search("孕妇禁用", k=20)
    assert isinstance(result, LexicalSearchResult)
    assert result.requested_k == 20 and result.returned_count == len(result.candidates) < 20
    assert result.candidate_exhausted is True
    assert [c.rank for c in result.candidates] == list(range(1, result.returned_count + 1))
    assert result.retriever_version.startswith("bm25-offline-v1") and result.tokenizer_version == "tok-regex-v1"
    full = index.search("报告", k=1)
    assert full.returned_count == 1 and full.candidate_exhausted is False


def test_ties_break_by_chunk_id_deterministically():
    idx = OfflineBM25Index(RegexTokenizerV1())
    idx.index(
        [
            ChunkRecord(chunk_id="b", text="孕妇禁用"),
            ChunkRecord(chunk_id="a", text="孕妇禁用"),
            ChunkRecord(chunk_id="c", text="孕妇禁用"),
        ]
    )
    ids = [c.chunk_id for c in idx.search("孕妇禁用", k=3).candidates]
    assert ids == ["a", "b", "c"]
    assert ids == [c.chunk_id for c in idx.search("孕妇禁用", k=3).candidates]


def test_duplicate_chunk_id_and_bad_k_rejected(index):
    with pytest.raises(ValueError):
        OfflineBM25Index(RegexTokenizerV1()).index(
            [ChunkRecord(chunk_id="x", text="a"), ChunkRecord(chunk_id="x", text="b")]
        )
    with pytest.raises(ValueError):
        index.search("x", k=0)
    with pytest.raises(ValueError):
        index.search("x", k=True)  # type: ignore[arg-type]


def test_empty_query_or_index_returns_exhausted_result(index):
    empty = OfflineBM25Index(RegexTokenizerV1())
    assert empty.search("孕妇", k=5).candidate_exhausted is True
    assert index.search("", k=5).returned_count == 0


def test_failed_first_build_leaves_an_empty_queryable_index():
    idx = OfflineBM25Index(RegexTokenizerV1())
    with pytest.raises(ValueError, match="duplicate"):
        idx.index([ChunkRecord(chunk_id="x", text="孕妇禁用"), ChunkRecord(chunk_id="x", text="孕妇禁用")])
    assert idx.size == 0
    result = idx.search("孕妇", k=5)  # no ZeroDivisionError, nothing leaked from the partial build
    assert result.returned_count == 0 and result.candidate_exhausted is True


def test_failed_rebuild_keeps_the_previous_index_and_versions_intact():
    idx = OfflineBM25Index(RegexTokenizerV1())
    idx.index(CORPUS)
    before_versions, before = idx.versions, idx.search("孕妇禁用", k=5)
    with pytest.raises(ValueError, match="duplicate"):
        idx.index([ChunkRecord(chunk_id="n1", text="新文档 孕妇禁用"), ChunkRecord(chunk_id="n1", text="重复")])
    assert idx.size == len(CORPUS) and idx.versions == before_versions
    after = idx.search("孕妇禁用", k=5)
    assert after == before and all(c.chunk_id != "n1" for c in after.candidates)
