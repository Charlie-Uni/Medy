"""M5-04 answer-context layout (record 113): `off` is byte-identical to the historical prompt, `compact-v1` only
swaps UUIDs for aliases, `sentfocus-v1` keeps the best sentences under a token budget — and in every mode the
verifier judges the full chunk and citations come back as chunk ids."""

from __future__ import annotations

import pytest

from medops.harness.evidence_focus import (
    ELISION,
    EVIDENCE_FOCUS_COMPACT,
    EVIDENCE_FOCUS_SENTENCE,
    KEEP_RATIO,
    MAX_UNIT_CHARS,
    focus_texts,
    render_evidence,
    split_units,
)
from medops.harness.nodes import HarnessDeps
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import estimate_tokens
from medops.retrieval.rerank import OverlapReranker
from tests.unit.harness._fixtures import evidence
from tests.unit.harness.test_run_ask import FakeRetrieval, make_deps, state

SCORER = OverlapReranker().score
DOSE = (
    "本品用於成人高血壓之治療。年齡 6 至 12 歲的孩童：口服，100 mg，一天三次；或 300 mg 當作一個單一劑量，一天一次。"
    "腎功能不全者應依肌酸酐清除率調整劑量。本品應置於兒童伸手不及之處。儲存於攝氏 25 度以下，避免陽光直射及潮濕。"
    "使用前請詳閱說明書，如有疑問請洽詢醫師或藥師。"
)
ENGLISH = (
    "The sponsor should notify the regulatory authority of fatal or life-threatening unexpected adverse reactions "
    "as soon as possible, but no later than 7 calendar days after first knowledge, e.g. by telephone. "
    "A complete report should follow within 8 additional calendar days. The dose was 0.05 mg/kg in study No. 12. "
    "Other serious unexpected reactions should be reported no later than 15 calendar days."
)


def units(text: str) -> list[str]:
    return [text[a:b] for a, b in split_units(text)]


def test_units_partition_the_text_and_respect_decimals_and_abbreviations():
    for text in (DOSE, ENGLISH, "", "no terminator at all"):
        assert "".join(units(text)) == text
    en = [u.strip() for u in units(ENGLISH)]
    assert en[0].endswith("e.g. by telephone.")  # "e.g." is not a sentence end
    assert any("0.05 mg/kg in study No. 12." in u for u in en)  # neither a decimal nor "No." splits
    assert en[-1].startswith("Other serious unexpected reactions")
    zh = [u.strip() for u in units(DOSE)]
    assert zh[0] == "本品用於成人高血壓之治療。"
    assert "年齡 6 至 12 歲的孩童：口服，100 mg，一天三次；" in zh  # the full-width semicolon ends a unit


def test_short_fragments_merge_forward_and_long_runs_are_cut_at_a_clause():
    assert [
        u.strip() for u in units("1. Scope of this guideline is limited. 2. It applies to all sponsors of trials.")
    ] == [
        "1. Scope of this guideline is limited.",
        "2. It applies to all sponsors of trials.",
    ]
    table = " ".join(f"Drug{i} {i * 10} mg {i}%," for i in range(60))  # a flattened table: no sentence end
    cut = units(table)
    assert "".join(cut) == table and len(cut) > 1 and all(len(u) <= MAX_UNIT_CHARS for u in cut)


def test_focus_keeps_the_best_unit_of_every_chunk_and_fills_to_the_budget():
    other = "臨床試驗的監查計畫應依風險訂定。試驗主持人應保存受試者同意書。稽核報告不提供給試驗機構。資料管理計畫應事先核准。"
    rendered, stats = focus_texts("6 至 12 歲 孩童 口服 劑量 100 mg", [DOSE, other], SCORER)
    assert "100 mg，一天三次" in rendered[0]  # the answer sentence survives
    assert ELISION in rendered[0] and "儲存於攝氏" not in rendered[0]
    assert rendered[1].replace(ELISION, "").strip()  # an irrelevant chunk still shows its best unit
    full = stats["full_tokens"]  # summed per unit, so it may exceed the whole-text estimate by rounding
    assert estimate_tokens(DOSE) + estimate_tokens(other) <= full <= estimate_tokens(DOSE + other) + stats["units"]
    assert KEEP_RATIO * full <= stats["kept_tokens"] < full
    assert stats["kept_units"] < stats["units"]
    assert focus_texts("6 至 12 歲 孩童 口服 劑量 100 mg", [DOSE, other], SCORER) == (rendered, stats)  # deterministic


def test_short_chunks_are_shown_whole_and_the_scorer_is_not_asked_about_them():
    asked: list[str] = []

    def scorer(query, texts):
        asked.extend(texts)
        return [0.0] * len(texts)

    short = "Losartan potassium 禁用於對本項產品任何組成過敏者。孕婦禁用。"
    rendered, stats = focus_texts("禁忌", [short], scorer)
    assert rendered == [short] and asked == [] and stats["kept_tokens"] == stats["full_tokens"]


def test_scorer_returning_the_wrong_number_of_scores_is_an_error():
    with pytest.raises(ValueError, match="score count"):
        focus_texts("q", [DOSE], lambda q, t: [1.0])


def test_off_is_the_historical_layout_and_compact_only_swaps_the_ids():
    items = [evidence("c1", DOSE, doc_id="doc-1"), evidence("c2", ENGLISH, doc_id="doc-2", historical=False)]
    off = render_evidence("q", items)
    assert off.blocks[0] == f"<<证据 1 | chunk=c1 | doc=doc-1 | version=v1 | page=1>>\n{DOSE}\n<<证据 1 结束>>"
    assert off.chunk_ids == {} and off.resolve("c1") == "c1"
    compact = render_evidence(
        "q", [*items, evidence("c3", "同一份文件的另一段，內容足夠長。", doc_id="doc-1")], mode=EVIDENCE_FOCUS_COMPACT
    )
    assert compact.blocks[0] == f"<<证据 | chunk=E1 | doc=D1 | version=v1 | page=1>>\n{DOSE}\n<<证据 E1 结束>>"
    assert "doc=D2" in compact.blocks[1] and "doc=D1" in compact.blocks[2]  # one alias per document
    assert "c1" not in "".join(compact.blocks) and compact.kept_tokens == compact.full_tokens
    assert compact.chunk_ids == {"E1": "c1", "E2": "c2", "E3": "c3"}
    assert compact.resolve("e2") == "c2" and compact.resolve("chunk=E3") == "c3" and compact.resolve("E9") == "E9"


def test_unknown_mode_and_missing_scorer_are_refused_before_any_run():
    with pytest.raises(ValueError, match="unknown evidence focus"):
        render_evidence("q", [], mode="sentfocus-v9")
    with pytest.raises(ValueError, match="needs a sentence scorer"):
        render_evidence("q", [evidence("c1", DOSE)], mode=EVIDENCE_FOCUS_SENTENCE)
    with pytest.raises(ValueError, match="needs a sentence scorer"):
        HarnessDeps(
            retrieval=FakeRetrieval(), gateway=FakeModelGateway(), answer_model_id="m", evidence_focus="sentfocus-v1"
        )
    with pytest.raises(ValueError, match="unknown evidence focus"):
        HarnessDeps(retrieval=FakeRetrieval(), gateway=FakeModelGateway(), answer_model_id="m", evidence_focus="x")


def test_answer_node_shows_focused_text_cites_aliases_and_verifies_against_the_full_chunk():
    from medops.harness.runtime import run_ask

    retrieval = FakeRetrieval(evidence("c1", DOSE), evidence("c2", ENGLISH))
    gateway = FakeModelGateway(
        {"answer": [{"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["E1"]}]}]}
    )
    deps = make_deps(retrieval, gateway, evidence_focus=EVIDENCE_FOCUS_SENTENCE, sentence_scorer=SCORER)
    run = run_ask(state(), deps)
    assert run.outcome == "answered"
    assert [c.chunk_id for c in run.state.answer.citations] == ["c1"]
    assert run.state.answer.claims[0].citation_chunk_ids == ("c1",)
    prompt = gateway.calls[0].messages[1].content
    assert "chunk=E1" in prompt and "chunk=c1" not in prompt and ELISION in prompt
    assert "100 mg，一天三次" in prompt
    full_prompt = "\n\n".join(render_evidence(state().query, run.state.evidence, mode=EVIDENCE_FOCUS_COMPACT).blocks)
    assert len(prompt) < len(full_prompt)  # something was left out, and the model was told where
    assert run.state.evidence[0].text == DOSE  # the state keeps the full, hash-checked chunk text


def test_an_invented_alias_fails_grounding_like_a_forged_chunk_id():
    from medops.domain.common import ReasonCode
    from medops.harness.runtime import run_ask

    retrieval = FakeRetrieval(evidence("c1", DOSE))
    gateway = FakeModelGateway(
        {"answer": [{"claims": [{"text": "孩童 100 mg 一天三次", "citation_chunk_ids": ["E7"]}]}]}
    )
    run = run_ask(state(), make_deps(retrieval, gateway, evidence_focus=EVIDENCE_FOCUS_COMPACT))
    assert run.outcome == "escalated" and run.state.escalation.reason_codes == (ReasonCode.unsupported_conclusion,)


def test_v2_keeps_neighbours_the_first_chunk_whole_and_scores_rewritten_queries_too():
    from medops.harness.evidence_focus import EVIDENCE_FOCUS_SENTENCE_V2, FOCUS_PARAMS

    other = "臨床試驗的監查計畫應依風險訂定。試驗主持人應保存受試者同意書。稽核報告不提供給試驗機構。資料管理計畫應事先核准。"
    params = FOCUS_PARAMS[EVIDENCE_FOCUS_SENTENCE_V2]
    asked: list[str] = []

    def scorer(query, texts):
        asked.append(query)
        return SCORER(query, texts)

    # chunk 1 (reranker order) is shown whole; the glossary-rich rewritten query is scored as a second variant
    rendered, stats = focus_texts(
        "監查計畫", [DOSE, other, ENGLISH], scorer, params=params, rewritten=("監查計畫", "監查計畫 monitoring plan")
    )
    assert rendered[0] == DOSE and ELISION not in rendered[0]
    assert asked == ["監查計畫", "監查計畫 monitoring plan"]
    # the best unit of chunk 2 is kept together with its neighbours
    assert "臨床試驗的監查計畫應依風險訂定。試驗主持人應保存受試者同意書。" in rendered[1]
    # a variant that only the rewritten query matches still lifts that unit
    v1, _ = focus_texts("監查計畫", [DOSE, other, ENGLISH], SCORER, params=FOCUS_PARAMS["sentfocus-v1"])
    v2, _ = focus_texts("xyz", [DOSE, other, ENGLISH], SCORER, params=params, rewritten=("xyz", "xyz 7 calendar days"))
    assert "7 calendar days" in v2[2]
    assert stats["kept_tokens"] >= params.keep_ratio * stats["full_tokens"]


def test_deps_accept_every_sentence_version_and_the_loader_lists_them():
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet
    from medops.harness.evidence_focus import ALLOWED_EVIDENCE_FOCUS, FOCUS_PARAMS

    assert set(FOCUS_PARAMS) == {"sentfocus-v1", "sentfocus-v2", "sentfocus-v3"}
    assert set(FOCUS_PARAMS) < ALLOWED_EVIDENCE_FOCUS
    for mode in FOCUS_PARAMS:
        make_deps(FakeRetrieval(), FakeModelGateway(), evidence_focus=mode, sentence_scorer=SCORER)
        rs = ReleasedPolicySet(
            (ReleasedPolicy("f", "retrieval_params", "hybrid", "v", {"evidence_focus": {"from": "off", "to": mode}}),)
        )
        assert rs.evidence_focus() == mode and rs.model_config_suffix() == f";ctx={mode}"
