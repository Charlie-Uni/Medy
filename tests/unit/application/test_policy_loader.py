"""Released policies as the runtime applies them (M4-03): retrieval overlay within the baseline caps, the answer prompt
override with its hash, version strings that reveal what is applied, and diff validation."""

from __future__ import annotations

import hashlib

import pytest

from medops.application.policy_loader import (
    SUPPORTED_RELEASE_TARGETS,
    PolicyDiffError,
    ReleasedPolicy,
    ReleasedPolicySet,
    apply_retrieval_diff,
    validate_diff,
)
from medops.retrieval.hybrid import HybridConfig

BASE = HybridConfig(k_lexical=20, k_vector=20, rrf_k=60.0, limit=20)


def released(*policies: ReleasedPolicy) -> ReleasedPolicySet:
    return ReleasedPolicySet(policies)


def test_empty_set_changes_nothing_and_keeps_the_base_versions():
    empty = ReleasedPolicySet.empty()
    assert empty.hybrid_config(BASE) == BASE and empty.rerank_output(8) == 8 and empty.answer_system("S") == "S"
    assert empty.policy_version("policy-m3-api-1") == "policy-m3-api-1" and empty.model_config_suffix() == ""
    assert not empty.retrieval_overridden()


def test_retrieval_overlay_applies_within_caps_and_marks_the_versions():
    p = ReleasedPolicy(
        "0123456789abcdef0123456789abcdef",
        "retrieval_params",
        "hybrid",
        "hybrid@v1",
        {"rrf_k": {"from": 60, "to": 40}, "k_lexical": {"from": 20, "to": 15}, "rerank_output": {"from": 8, "to": 6}},
    )
    rs = released(p)
    cfg = rs.hybrid_config(BASE)
    assert (cfg.k_lexical, cfg.k_vector, cfg.rrf_k, cfg.limit) == (15, 20, 40.0, 20) and rs.rerank_output(8) == 6
    assert rs.retrieval_overridden() and rs.policy_version("base") == "base+rel:01234567"
    with pytest.raises(PolicyDiffError):
        apply_retrieval_diff(BASE, {"k_vector": {"from": 20, "to": 30}})  # baseline cap: channel k <= 20
    with pytest.raises(PolicyDiffError):
        apply_retrieval_diff(BASE, {"batch": {"from": 8, "to": 16}})  # not a retrieval parameter
    with pytest.raises(PolicyDiffError):
        released(
            ReleasedPolicy("x", "retrieval_params", "hybrid", "v", {"rerank_output": {"from": 8, "to": 9}})
        ).rerank_output(8)


def test_prompt_override_checks_its_hash_and_changes_the_model_config():
    text = "只依据证据作答；不得补充证据以外的医学知识。"
    digest = hashlib.sha256(text.encode()).hexdigest()
    rs = released(
        ReleasedPolicy(
            "abcdefabcdefabcdefabcdefabcdefab",
            "prompt",
            "answer_system",
            "answer_system@v2",
            {"text": text, "text_sha256": digest},
        )
    )
    assert rs.answer_system("default") == text and rs.model_config_suffix() == ";prompt=" + digest[:8]
    bad = released(ReleasedPolicy("x", "prompt", "answer_system", "v", {"text": text, "text_sha256": "0" * 64}))
    with pytest.raises(PolicyDiffError):
        bad.answer_system("default")
    with pytest.raises(PolicyDiffError):
        released(ReleasedPolicy("x", "prompt", "answer_system", "v", {"text": "  "})).answer_system("default")


def test_several_released_policies_sort_into_one_policy_version():
    rs = released(
        ReleasedPolicy("ffffffff00000000ffffffff00000000", "prompt", "answer_system", "v", {"text": "t"}),
        ReleasedPolicy(
            "00000000ffffffff00000000ffffffff", "retrieval_params", "hybrid", "v", {"rrf_k": {"from": 60, "to": 30}}
        ),
    )
    assert rs.policy_version("p") == "p+rel:00000000,ffffffff"


def test_validate_diff_covers_every_kind_and_the_supported_targets_are_pinned():
    validate_diff("retrieval_params", "hybrid", {"limit": {"from": 20, "to": 12}}, base=BASE)
    with pytest.raises(PolicyDiffError):
        validate_diff("retrieval_params", "hybrid", {"limit": {"from": 20, "to": 20}}, base=BASE)
    validate_diff("prompt", "answer_system", {"text": "x"})
    with pytest.raises(PolicyDiffError):
        validate_diff("prompt", "answer_system", {"text": "x" * 6001})
    validate_diff("rule", "support_rules", {"add": ["in no event later than"]})
    with pytest.raises(PolicyDiffError):
        validate_diff("rule", "support_rules", {"remove": ["x"]})
    validate_diff("skill", "label_query", {"params": {"k": 1}})
    with pytest.raises(PolicyDiffError):
        validate_diff("prompt", "other", {"text": "x"})
    assert SUPPORTED_RELEASE_TARGETS == {("retrieval_params", "hybrid"), ("prompt", "answer_system")}


def test_glossary_is_a_retrieval_parameter_with_a_versioned_value():
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet

    rs = ReleasedPolicySet(
        (
            ReleasedPolicy(
                "g",
                "retrieval_params",
                "hybrid",
                "v",
                {"glossary": {"from": "glossary-none", "to": "glossary-20260926-0123456789ab"}},
            ),
        )
    )
    assert rs.glossary_version() == "glossary-20260926-0123456789ab"
    assert rs.hybrid_config(BASE) == BASE and rs.rerank_output(8) == 8 and rs.retrieval_overridden()
    assert ReleasedPolicySet().glossary_version() == "glossary-none"
    validate_diff(
        "retrieval_params",
        "hybrid",
        {"glossary": {"from": "glossary-none", "to": "glossary-20260926-0123456789ab"}},
        base=BASE,
    )
    with pytest.raises(PolicyDiffError):
        validate_diff("retrieval_params", "hybrid", {"glossary": {"from": "glossary-none", "to": "latest"}}, base=BASE)


def test_multi_query_is_a_boolean_retrieval_parameter():
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet

    rs = ReleasedPolicySet(
        (ReleasedPolicy("m", "retrieval_params", "hybrid", "v", {"multi_query": {"from": False, "to": True}}),)
    )
    assert rs.multi_query() is True and ReleasedPolicySet().multi_query() is False
    validate_diff("retrieval_params", "hybrid", {"multi_query": {"from": False, "to": True}}, base=BASE)
    with pytest.raises(PolicyDiffError):
        validate_diff("retrieval_params", "hybrid", {"multi_query": {"from": False, "to": "yes"}}, base=BASE)


def test_doc_focus_is_a_boolean_retrieval_parameter():
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet

    rs = ReleasedPolicySet(
        (ReleasedPolicy("f", "retrieval_params", "hybrid", "v", {"doc_focus": {"from": False, "to": True}}),)
    )
    assert rs.doc_focus() is True and ReleasedPolicySet().doc_focus() is False
    validate_diff("retrieval_params", "hybrid", {"doc_focus": {"from": False, "to": True}}, base=BASE)
    with pytest.raises(PolicyDiffError):
        validate_diff("retrieval_params", "hybrid", {"doc_focus": {"from": False, "to": 1}}, base=BASE)


def test_query_translation_is_an_allowlisted_model_and_marks_the_model_config():
    from medops.application.policy_loader import ReleasedPolicy, ReleasedPolicySet

    rs = ReleasedPolicySet(
        (
            ReleasedPolicy(
                "t", "retrieval_params", "hybrid", "v", {"query_translation": {"from": "off", "to": "gpt-6-luna"}}
            ),
        )
    )
    assert rs.query_translation() == "gpt-6-luna" and rs.model_config_suffix() == ";qt=gpt-6-luna"
    assert ReleasedPolicySet().query_translation() == "off" and ReleasedPolicySet().model_config_suffix() == ""
    validate_diff("retrieval_params", "hybrid", {"query_translation": {"from": "off", "to": "gpt-6-luna"}}, base=BASE)
    with pytest.raises(PolicyDiffError):
        validate_diff("retrieval_params", "hybrid", {"query_translation": {"from": "off", "to": "gpt-3.5"}}, base=BASE)
