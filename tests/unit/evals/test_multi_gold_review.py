"""All gold pages must reach the reviewer and reproduce the recorded prompt."""

import copy
import json

import pytest

from medops.evals.probe import review_provenance as provenance
from medops.evals.probe.review_inputs import multi_gold_review_record


@pytest.fixture
def case():
    doc = {
        "source_hash": "a" * 64,
        "document_key": "doc",
        "title": "Doc",
        "doc_type": "guideline",
        "language": "en",
        "version_label": "Rev 1",
    }
    texts = {1: "Audit findings require risk grading.", 2: "Completion evidence must be recorded."}
    sample = {
        "sample_id": "ms-0001",
        "query": "What grading and follow-up are required?",
        "dept": "PV",
        "language": "en",
        "slices": ["long_context"],
        "required_gold_evidence": [
            {
                "gold_id": f"ms-0001-g{n}",
                "source_hash": doc["source_hash"],
                "version_label": "Rev 1",
                "page": n,
                "section": "Audit",
                "key_text": text,
                "evidence_span": {"text": text, "char_start": 0, "char_end": len(text)},
            }
            for n, text in texts.items()
        ],
        "review": {"status": "agreed"},
        "drafted_by": {"id": "drafter"},
    }
    return sample, {doc["source_hash"]: doc}, texts


def test_cross_page_input_and_provenance_have_identical_bytes_without_prior_approval(case, tmp_path):
    sample, docs, texts = case
    record = multi_gold_review_record(sample, docs, lambda h, p: texts.get(p))
    assert len(record["golds"]) == 2 and len(record["page_texts"]) == 2
    assert "review" not in record and "drafted_by" not in record
    (tmp_path / "corpus.json").write_text(json.dumps({"documents": list(docs.values())}))

    class Pages:
        def page_text(self, source, page):
            return texts.get(page)

    rebuilt = provenance._current_records(tmp_path, [sample], Pages())[sample["sample_id"]]
    assert json.dumps(record, ensure_ascii=False) == json.dumps(rebuilt, ensure_ascii=False)
    assert provenance._actual_prompt_hash("multi-gold rules", [record]) in provenance._actual_prompt_hashes(
        "multi-gold rules", [rebuilt]
    )
    changed = copy.deepcopy(rebuilt)
    changed["page_texts"][1]["text"] += " Changed context."
    assert provenance._actual_prompt_hash("multi-gold rules", [record]) not in provenance._actual_prompt_hashes(
        "multi-gold rules", [changed]
    )


def test_same_page_golds_keep_both_units_but_deduplicate_page_text(case):
    sample, docs, texts = case
    text = texts[1] + " " + texts[2]
    sample["required_gold_evidence"][1]["page"] = 1
    span = sample["required_gold_evidence"][1]["evidence_span"]
    span["char_start"] = len(texts[1]) + 1
    span["char_end"] = len(text)
    rec = multi_gold_review_record(sample, docs, lambda h, p: text)
    assert len(rec["golds"]) == 2 and len(rec["page_texts"]) == 1


@pytest.mark.parametrize("mutation", ["duplicate_id", "bad_span", "repeated_key", "wrong_version", "missing_parent"])
def test_invalid_inputs_cannot_be_presented_as_reviewable(case, mutation):
    sample, docs, texts = case
    gold = sample["required_gold_evidence"][1]
    if mutation == "duplicate_id":
        gold["gold_id"] = sample["required_gold_evidence"][0]["gold_id"]
    elif mutation == "bad_span":
        gold["evidence_span"]["char_end"] -= 1
    elif mutation == "repeated_key":
        texts[2] += " " + texts[2]
    elif mutation == "wrong_version":
        gold["version_label"] = "Rev 2"
    else:
        sample["derived_from"] = "ms-0002"
    with pytest.raises(ValueError):
        multi_gold_review_record(sample, docs, lambda h, p: texts.get(p))


def test_missing_second_page_never_silently_drops_the_second_gold(case):
    sample, docs, texts = case
    del texts[2]
    assert multi_gold_review_record(sample, docs, lambda h, p: texts.get(p)) is None


def test_parent_question_is_preserved_without_parent_verdict(case):
    sample, docs, texts = case
    sample["derived_from"] = "ms-0002"
    parent = {"sample_id": "ms-0002", "query": "审计分级和后续措施是什么？", "review": {"status": "agreed"}}
    record = multi_gold_review_record(sample, docs, lambda h, p: texts.get(p), parent)
    assert record["parent_query"] == parent["query"] and '"review":' not in json.dumps(record)
