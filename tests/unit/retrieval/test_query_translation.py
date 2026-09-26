"""Query translation (record 95): English questions are not translated, a good reply becomes the extra search query,
and every fault or malformed reply fails open to "no translation"."""

from __future__ import annotations

import pytest

from medops.infrastructure.llm.fake import FakeModelGateway, Truncated
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.retrieval.query_translation import QUERY_TRANSLATION_VERSION, QueryTranslator


def test_english_questions_skip_the_call_and_chinese_ones_are_translated():
    gw = FakeModelGateway(
        {"query_translation": [{"translation": "Under GVP Module XV, which system coordinates safety announcements?"}]}
    )
    t = QueryTranslator(gw, "gpt-6-luna")
    assert t.translate("Which system coordinates safety communication under GVP Module XV?") is None and gw.calls == []
    out = t.translate("按 GVP Module XV，欧盟监管网络应通过哪个系统交流和协调安全公告？")
    assert out.startswith("Under GVP Module XV") and t.version == f"{QUERY_TRANSLATION_VERSION}:gpt-6-luna"
    req = gw.calls[0]
    assert req.purpose == "query_translation" and req.model_id == "gpt-6-luna" and req.json_schema is not None
    assert req.max_output_tokens <= 300 and req.timeout_s <= 10


def test_faults_and_bad_replies_fail_open():
    gw = FakeModelGateway(
        {
            "query_translation": [
                ModelTimeout("slow"),
                {"translation": ""},
                {"translation": "仍然是中文"},
                Truncated('{"translation": "Under GVP'),
                {"translation": "x" * 500},
            ]
        }
    )
    t = QueryTranslator(gw, "gpt-6-luna")
    for _ in range(5):
        assert t.translate("按 GVP Module XV，安全公告？") is None
    assert len(gw.calls) == 5


def test_only_allowed_models():
    with pytest.raises(ValueError):
        QueryTranslator(FakeModelGateway(), "gpt-3.5")
