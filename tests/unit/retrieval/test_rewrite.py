"""M1-13 rule-based query rewrite: bounded 1..3 append-only text queries; doses, units, negations, time
windows and identifiers survive verbatim; entities come from the call only; glossary is versioned; user
text can never become a filter."""

from __future__ import annotations

import json

import pytest

from medops.core.errors import BusinessError, ErrorCode
from medops.domain import Entity
from medops.retrieval.rewrite import (
    MAX_ENTITY_TERMS,
    MAX_GLOSSARY_TERMS,
    MAX_QUERY_CHARS,
    REWRITER_VERSION,
    Glossary,
    GlossaryEntry,
    RewriteResult,
    load_glossary,
    protected_spans,
    rewrite,
)

GLOSSARY = Glossary(
    version="glossary-test-1",
    entries=(
        GlossaryEntry(term="阿司匹林", synonyms=("aspirin", "乙酰水杨酸"), kind="generic"),
        GlossaryEntry(term="esomeprazole", synonyms=("埃索美拉唑", "Nexium"), kind="generic"),
        GlossaryEntry(term="ACEI", synonyms=("血管紧张素转换酶抑制剂",), kind="abbreviation"),
        GlossaryEntry(term="g", synonyms=("gram",), kind="abbreviation"),  # must never match a unit
        GlossaryEntry(term="U", synonyms=("unit",), kind="abbreviation"),
    ),
)

PROTECTED_QUERIES = [
    "阿司匹林每次 0.5 g，每日 2 次，连用 7 天内不得超过 3 g",
    "孕妇禁用阿司匹林吗？哺乳期不推荐吗",
    "按照 ICH E8(R1) 与 PROT-2024-017，给药后 24 小时内 SAE 必须在 15 天内报告",
    "esomeprazole 40 mg 可以和 nelfinavir 一起服用吗，不能的话为什么",
    "衛署藥製字第 048564 號的藥品 100 IU/mL 每週 3 次",
    "Do not exceed 4 g/day; avoid in patients under 12 years without renal data",
]


def test_query_one_is_the_normalized_query_and_the_result_is_bounded_and_versioned():
    result = rewrite("  阿司匹林　用法用量 ")
    assert result.queries == ("阿司匹林用法用量",)
    assert (result.rewriter_version, result.glossary_version, result.normalization_version) == (
        REWRITER_VERSION,
        "glossary-none",
        "norm-v1",
    )
    assert result.added_entities == () and result.added_terms == ()


def test_empty_or_oversized_queries_are_refused():
    with pytest.raises(BusinessError) as exc:
        rewrite(" 　 ")
    assert exc.value.code is ErrorCode.invalid_request
    with pytest.raises(BusinessError, match="exceeds"):
        rewrite("a" * (MAX_QUERY_CHARS + 1))


@pytest.mark.parametrize("query", PROTECTED_QUERIES)
def test_protected_spans_survive_verbatim_in_every_rewritten_query(query):
    entities = (Entity(kind="drug", value="美洛醣"), Entity(kind="protocol", value="SOP-QA-001"))
    result = rewrite(query, entities=entities, glossary=GLOSSARY)
    base = result.queries[0]
    spans = protected_spans(base)
    assert spans, "each fixture query carries at least one protected span"
    for q in result.queries:
        assert q.startswith(base)  # append-only: nothing removed, replaced or reordered
        for start, end, _ in spans:
            assert base[start:end] in q
    assert 1 <= len(result.queries) <= 3


def test_protected_span_kinds_cover_doses_negations_time_windows_and_identifiers():
    kinds = {kind for _, _, kind in protected_spans(rewrite(PROTECTED_QUERIES[2]).queries[0])}
    assert kinds == {"number_unit", "identifier"}
    text = rewrite(PROTECTED_QUERIES[0]).queries[0]
    covered = [text[s:e] for s, e, _ in protected_spans(text)]
    assert "0.5 g" in covered and "2 次" in covered and "7 天" in covered and "不得" in covered and "3 g" in covered
    text = rewrite(PROTECTED_QUERIES[5]).queries[0]
    covered = [text[s:e] for s, e, _ in protected_spans(text)]
    assert (
        "Do not" in covered
        and "4 g/day" in covered
        and "avoid" in covered
        and "without" in covered
        and "12 years" in covered
    )


def test_glossary_never_matches_inside_a_protected_span_or_inside_another_word():
    # "g" and "U" are glossary abbreviations but here only appear as units / inside words
    result = rewrite("每次 0.5 g，100 U 皮下注射，Unit dose", glossary=GLOSSARY)
    assert result.added_terms == () and len(result.queries) == 1
    result = rewrite("ACEI 与 ARB 可以合用吗", glossary=GLOSSARY)
    assert result.added_terms == ("血管紧张素转换酶抑制剂",)
    assert rewrite("PLACEIN 研究", glossary=GLOSSARY).added_terms == ()  # no word boundary -> no match


def test_glossary_synonyms_are_appended_case_insensitively_and_bounded():
    result = rewrite("Esomeprazole 与阿司匹林合用", glossary=GLOSSARY)
    assert result.queries[0] == "Esomeprazole 与阿司匹林合用"
    assert result.added_terms == ("aspirin", "乙酰水杨酸", "埃索美拉唑", "Nexium")
    assert result.queries[-1] == "Esomeprazole 与阿司匹林合用 aspirin 乙酰水杨酸 埃索美拉唑 Nexium"
    many = Glossary(
        version="g",
        entries=tuple(GlossaryEntry(term=f"t{i}", synonyms=(f"s{i}a", f"s{i}b")) for i in range(6)),
    )
    result = rewrite("t0 t1 t2 t3 t4 t5", glossary=many)
    assert len(result.added_terms) == MAX_GLOSSARY_TERMS
    assert rewrite("阿司匹林 aspirin", glossary=GLOSSARY).added_terms == (
        "乙酰水杨酸",
    )  # present synonyms not repeated


def test_session_entities_are_appended_once_bounded_and_never_remembered():
    a = (
        Entity(kind="drug", value="美洛醣"),
        Entity(kind="protocol", value="PROT-2024-017"),
        Entity(kind="other", value="ignored"),
    )
    first = rewrite("每日最高剂量是多少", entities=a)
    assert first.added_entities == ("美洛醣", "PROT-2024-017")
    assert first.queries == ("每日最高剂量是多少", "每日最高剂量是多少 美洛醣 PROT-2024-017")
    second = rewrite("每日最高剂量是多少")  # a different session: nothing carried over
    assert second.queries == ("每日最高剂量是多少",) and second.added_entities == ()
    third = rewrite("美洛醣每日最高剂量", entities=a)
    assert third.added_entities == ("PROT-2024-017",)  # already present -> not appended
    many = tuple(Entity(kind="drug", value=f"药{i}") for i in range(5))
    assert len(rewrite("剂量", entities=many).added_entities) == MAX_ENTITY_TERMS
    dirty = (Entity(kind="drug", value="bad\x00value"), Entity(kind="drug", value="　"))
    assert rewrite("剂量", entities=dirty).added_entities == ()


def test_three_queries_at_most_and_all_distinct():
    result = rewrite("阿司匹林 剂量", entities=(Entity(kind="drug", value="美洛醣"),), glossary=GLOSSARY)
    assert len(result.queries) == 3 and len(set(result.queries)) == 3
    assert result.queries[1].endswith("美洛醣") and result.queries[2].endswith("aspirin 乙酰水杨酸")


def test_user_text_can_only_become_text_never_a_filter():
    hostile = "dept:CO OR status:draft; as_of=2020-01-01 -- drop table documents"
    result = rewrite(hostile, entities=(Entity(kind="drug", value="x' or 1=1"),))
    assert result.queries[0] == hostile
    assert set(RewriteResult.model_fields) == {
        "queries",
        "rewriter_version",
        "glossary_version",
        "normalization_version",
        "added_entities",
        "added_terms",
    }
    with pytest.raises(ValueError):
        RewriteResult(queries=("q",), rewriter_version="v", glossary_version="g", normalization_version="n", dept="CO")  # type: ignore[call-arg]


def test_glossary_validation_and_loading(tmp_path):
    with pytest.raises(ValueError, match="normalized"):
        GlossaryEntry(term="阿司匹林 ", synonyms=("aspirin",))
    with pytest.raises(ValueError, match="distinct"):
        GlossaryEntry(term="aspirin", synonyms=("aspirin",))
    with pytest.raises(ValueError, match="unique"):
        Glossary(
            version="g", entries=(GlossaryEntry(term="a", synonyms=("b",)), GlossaryEntry(term="a", synonyms=("c",)))
        )
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(GLOSSARY.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
    assert load_glossary(path) == GLOSSARY
    assert Glossary.empty().entries == () and Glossary.empty().version == "glossary-none"
