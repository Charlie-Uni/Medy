"""chunker-v1 (M1-10): page-anchored, deterministic, lossless, bounded, with best-effort sections."""

import hashlib

from medops.ingestion.chunker import (
    CHUNKER_VERSION,
    MAX_CHARS,
    MIN_TAIL_CHARS,
    TARGET_CHARS,
    chunk_pages,
    chunker_record,
)
from medops.retrieval.lexical.normalization import normalize_text

ZH_SENTENCE = "成人常用量：口服，每次 0.5 g，每日 2 次，疗程 7 天。"
EN_SENTENCE = "Adults: 500 mg orally twice daily for seven days. "


def _covered(text: str, spans) -> bool:
    """Every non-space character of the normalised page lies in exactly one span."""
    hit = [0] * len(text)
    for s in spans:
        for i in range(s.char_start, s.char_end):
            hit[i] += 1
    return all((hit[i] == 1) if not text[i].isspace() else hit[i] <= 1 for i in range(len(text)))


def test_chunks_are_exact_slices_of_the_normalised_page_and_cover_it():
    raw = "第 3 节  用法用量\n" + " ".join(
        ZH_SENTENCE for _ in range(40)
    )  # extraction whitespace + full-width punctuation
    chunks = chunk_pages([raw])
    text = normalize_text(raw)
    assert text != raw and "：" not in text  # norm-v1 changed the coordinates: chunks must use the normalised ones
    assert len(chunks) > 1
    for c in chunks:
        (span,) = c.spans
        assert span.page == 1 and c.page == 1
        assert c.content == text[span.char_start : span.char_end]
        assert c.content == c.content.strip()
        assert c.content_hash == hashlib.sha256(c.content.encode("utf-8")).hexdigest()
        assert len(c.content) <= MAX_CHARS
    assert [c.seq for c in chunks] == list(range(len(chunks)))
    spans = [c.spans[0] for c in chunks]
    assert all(a.char_end <= b.char_start for a, b in zip(spans, spans[1:], strict=False))
    assert _covered(text, spans)


def test_boundaries_fall_on_sentence_ends_and_sizes_are_bounded():
    raw = "".join(EN_SENTENCE for _ in range(60))
    chunks = chunk_pages([raw])
    assert len(chunks) >= 4
    for c in chunks[:-1]:
        assert c.content.endswith("."), c.content[-30:]
        assert TARGET_CHARS <= len(c.content) <= MAX_CHARS
    assert len(chunks[-1].content) >= MIN_TAIL_CHARS or len(chunks) == 1


def test_short_tail_is_merged_into_previous_chunk():
    raw = "".join(EN_SENTENCE for _ in range(9)) + "Tail."  # ~450 chars then a 5-char tail
    chunks = chunk_pages([raw])
    assert len(chunks) == 1
    assert chunks[0].content.endswith("Tail.")


def test_unbreakable_runs_are_split_at_whitespace_within_max():
    raw = " ".join(f"token{i:04d}" for i in range(400))  # no sentence punctuation at all
    chunks = chunk_pages([raw])
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHARS for c in chunks)
    assert all(not c.content.startswith(" ") and not c.content.endswith(" ") for c in chunks)
    assert _covered(normalize_text(raw), [c.spans[0] for c in chunks])


def test_no_whitespace_at_all_is_hard_cut():
    raw = "x" * (MAX_CHARS * 2 + 50)
    chunks = chunk_pages([raw])
    assert [len(c.content) for c in chunks] == [MAX_CHARS, MAX_CHARS, 50] or sum(len(c.content) for c in chunks) == len(
        raw
    )
    assert all(len(c.content) <= MAX_CHARS for c in chunks)


def test_pages_never_mix_and_empty_pages_are_skipped():
    chunks = chunk_pages(["第一页。" * 30, "", "   \n ", "第四页。" * 30])
    assert {c.page for c in chunks} == {1, 4}
    assert all(c.spans[0].page == c.page for c in chunks)
    assert chunk_pages([]) == [] and chunk_pages(["", "\n"]) == []


def test_sections_are_detected_and_carried_across_pages():
    page1 = (
        "【適應症】高血壓。\n"
        + "本品用於治療原發性高血壓。" * 10
        + "\n用法用量：成人每日一次 50 mg。\n"
        + "餐前餐後皆可服用。" * 60
    )
    page2 = "續前頁內容，仍屬用法用量。" * 20
    page3 = (
        "4.2 Posology and Method of Administration\nAdults take one tablet daily. " + "Do not exceed the dose. " * 20
    )
    chunks = chunk_pages([page1, page2, page3])
    first = [c for c in chunks if c.page == 1]
    assert first[0].section == "適應症"
    assert any(c.section == "用法用量" for c in first)
    assert all(c.section == "用法用量" for c in chunks if c.page == 2), "section label carries over to the next page"
    assert all(c.section == "4.2 Posology and Method of Administration" for c in chunks if c.page == 3)


def test_deterministic_and_versioned():
    raw = ["".join(EN_SENTENCE for _ in range(25)), ZH_SENTENCE * 30]
    assert chunk_pages(raw) == chunk_pages(list(raw))
    assert chunker_record() == {"chunker_version": CHUNKER_VERSION, "normalization": "norm-v1"}


def test_v2_semicolon_is_a_clause_mark_not_a_sentence_end():
    clause = (
        "The DSUR should discuss it in the text; however, it should not be used to provide the initial notification. "
    )
    raw = clause * 8
    chunks = chunk_pages([raw])
    for c in chunks:
        assert "text; however" in c.content or not c.content.startswith("however"), c.content[:60]
        assert not c.content.startswith("however"), "a chunk must not start right after the semicolon"
    assert CHUNKER_VERSION == "chunker-v2"


def test_v2_long_runs_are_split_after_a_clause_mark_before_falling_back_to_whitespace():
    # no sentence terminator at all; commas every ~90 chars -> cuts land right after a comma
    piece = "definitions of protocol deviation and important protocol deviation are adopted from E3 R1 guidance, "
    raw = piece * 12
    chunks = chunk_pages([raw])
    assert len(chunks) > 1
    for c in chunks[:-1]:
        assert c.content.endswith(","), c.content[-40:]
        assert len(c.content) <= MAX_CHARS
    assert _covered(normalize_text(raw), [c.spans[0] for c in chunks])
    # a run without clause marks still splits at whitespace, and one without whitespace is hard cut (v1 behaviour kept)
    words = " ".join(f"token{i:04d}" for i in range(400))
    assert all(len(c.content) <= MAX_CHARS and " " not in (c.content[0], c.content[-1]) for c in chunk_pages([words]))
