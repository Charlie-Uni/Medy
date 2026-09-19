import pytest

from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, RegexTokenizerV1

jieba = pytest.importorskip("jieba")


@pytest.fixture(scope="module")
def tok():
    return JiebaTokenizerV1()


def test_versions_are_exposed(tok):
    assert tok.tokenizer_version == "tok-jieba-v1"
    assert tok.dictionary_version.startswith("jieba-") and tok.normalization_version == "norm-v1"


def test_protocol_id_preserved_whole(tok):
    tokens = tok.tokenize("PROT-2024-017 方案里 SAE 要在多少小时内报告")
    assert "prot-2024-017" in tokens and "sae" in tokens


def test_registry_id_and_dose_tokens(tok):
    tokens = tok.tokenize("NCT04283461 受试者每次 0.5 g，每日 2 次，14 天内报告")
    assert "nct04283461" in tokens and "0.5" in tokens and "14" in tokens


def test_extraction_whitespace_and_fullwidth_do_not_change_tokens(tok):
    assert tok.tokenize("每 次 0.5 g，每 日 2 次") == tok.tokenize("每次 0.5 g,每日 2 次")
    assert tok.tokenize("１０ ｍｇ") == tok.tokenize("10 mg")


def test_cjk_case_is_untouched_and_ascii_folded(tok):
    tokens = tok.tokenize("CYP3A4 抑制剂")
    assert "cyp3a4" in tokens and "抑制剂" in tokens


def test_regex_tokenizer_is_separately_versioned():
    rt = RegexTokenizerV1()
    assert rt.tokenizer_version == "tok-regex-v1"
    assert rt.tokenize("孕妇禁用 PROT-2024-017") == ["孕", "妇", "禁", "用", "prot-2024-017"]


SYNTHETIC_TERM = "药物警戒专用合成术语"


def test_instances_with_different_dictionaries_do_not_pollute_each_other(tmp_path):
    plain = JiebaTokenizerV1()
    before = plain.tokenize(SYNTHETIC_TERM)
    user_dict = tmp_path / "terms.txt"
    user_dict.write_text(f"{SYNTHETIC_TERM} 100000000 nz\n", encoding="utf-8")
    custom = JiebaTokenizerV1(user_dictionary=user_dict)
    assert custom.tokenize(SYNTHETIC_TERM) == [SYNTHETIC_TERM]
    assert plain.tokenize(SYNTHETIC_TERM) == before and len(before) > 1
    assert custom.dictionary_version != plain.dictionary_version


def test_default_instance_is_unaffected_by_later_dictionary_loads(tmp_path):
    first = JiebaTokenizerV1()
    before, version = first.tokenize(SYNTHETIC_TERM), first.dictionary_version
    user_dict = tmp_path / "terms.txt"
    user_dict.write_text(f"{SYNTHETIC_TERM} 100000000 nz\n", encoding="utf-8")
    JiebaTokenizerV1(user_dictionary=user_dict)
    assert first.tokenize(SYNTHETIC_TERM) == before
    assert first.dictionary_version == version
    assert JiebaTokenizerV1().tokenize(SYNTHETIC_TERM) == before
