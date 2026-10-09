"""PR-09 prompt rebuild: key-order variants of blocks the schema does not order (spec-m1 conflict block, no-answer
records without gold) must be recognised, and never crash the product over variants."""

from medops.evals.probe import review_provenance as provenance

PROMPT = "review prompt text"
GOLD = {
    "page": 3,
    "section": "S",
    "key_text": "k",
    "evidence_span": {"text": "t", "char_start": 0, "char_end": 1},
}


def _record(**extra):
    return {"sample_id": "ms-0001", "query": "q", "dept": "PV", "language": "mixed", "slices": ["mixed_zh_en"], **extra}


def test_conflict_block_in_drafting_or_canonical_order_both_rebuild_the_prompt():
    drafting = {"family_document_keys": ["a", "b"], "current_document_key": "a", "clause_topic": "t", "synthetic": True}
    canonical = {k: drafting[k] for k in sorted(drafting)}
    assert list(drafting) != list(canonical)
    sent = _record(gold=dict(GOLD), conflict=drafting)
    frozen = _record(gold=dict(GOLD), conflict=canonical)
    actual = provenance._actual_prompt_hash(PROMPT, [sent])
    assert actual in provenance._actual_prompt_hashes(PROMPT, [frozen])
    assert actual in provenance._actual_prompt_hashes(PROMPT, [sent])


def test_conflict_content_change_is_still_detected():
    sent = _record(gold=dict(GOLD), conflict={"family_document_keys": ["a"], "current_document_key": "a"})
    changed = _record(gold=dict(GOLD), conflict={"family_document_keys": ["a"], "current_document_key": "b"})
    assert provenance._actual_prompt_hash(PROMPT, [sent]) not in provenance._actual_prompt_hashes(PROMPT, [changed])


def test_no_answer_record_without_gold_yields_two_identical_variants_and_rebuilds():
    record = _record(answerable=False, abstention={"topic": "x"}, document_text="=== 第 1 页 ===\nabc")
    variants = provenance._span_variants(record)
    assert len(variants) == 2 and variants[0] == variants[1] == record
    assert provenance._actual_prompt_hash(PROMPT, [record]) in provenance._actual_prompt_hashes(PROMPT, [record])


def test_coordinate_first_span_order_rebuilds():
    record = _record(gold=dict(GOLD))
    span = record["gold"]["evidence_span"]
    record["gold"]["evidence_span"] = {
        "char_start": span["char_start"],
        "char_end": span["char_end"],
        "text": span["text"],
    }
    assert provenance._actual_prompt_hash(PROMPT, [record]) in provenance._actual_prompt_hashes(PROMPT, [record])


def test_probe_derived_record_accepts_frozen_parent_context_variant():
    record = _record(sample_id="pc-0002", gold=dict(GOLD))
    sample = {"sample_id": "pc-0002", "derived_from": "pc-0001", "notes": "English twin"}
    parent = {"sample_id": "pc-0001", "query": "父问题"}
    by_id = {"pc-0001": parent, "pc-0002": sample}

    variants = provenance._review_record_variants(record, sample, by_id, main_set=False)

    assert len(variants) == 2
    assert list(variants[1])[-2:] == ["notes", "parent_query"]
    assert variants[1]["notes"] == "English twin"
    assert variants[1]["parent_query"] == "父问题"
    assert provenance._review_record_variants(record, sample, by_id, main_set=True) == [record]


def test_mixed_chunk_of_gold_conflict_and_no_answer_records_is_covered():
    gold_only = _record(gold=dict(GOLD))
    with_conflict = dict(
        _record(
            gold=dict(GOLD),
            conflict={"family_document_keys": ["a", "b"], "current_document_key": "a", "synthetic": True},
        ),
        sample_id="ms-0002",
    )
    no_answer = dict(_record(answerable=False, abstention={"topic": "x"}, document_text="p"), sample_id="ms-0003")
    chunk = [gold_only, with_conflict, no_answer]
    hashes = provenance._actual_prompt_hashes(PROMPT, chunk)
    # 3 span orders * 6 (span x conflict order) * 2 duplicate no-answer variants, deduplicated by the set.
    assert provenance._actual_prompt_hash(PROMPT, chunk) in hashes
    assert 1 <= len(hashes) <= 36
