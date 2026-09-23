"""intent-rules-v2: narrow first-person high-risk detection, department skill routing, unclear queries."""

from __future__ import annotations

import pytest

from medops.domain.common import RiskLevel
from medops.domain.intent import IntentType
from medops.harness.intent import classify


@pytest.mark.parametrize(
    "query",
    [
        "我该吃多少剂量的 metformin？",
        "帮我诊断一下这些症状",
        "My child just took 10 tablets, what should I do?",
        "What dose should I take tonight?",
    ],
)
def test_first_person_dosing_diagnosis_or_emergency_is_high_risk(query):
    intent = classify(query)
    assert intent.type is IntentType.high_risk and intent.risk is RiskLevel.high and intent.target_skill is None


@pytest.mark.parametrize(
    ("query", "expected", "skill"),
    [
        (
            "Except in emergency situations, does a protocol deviation require prior sponsor approval?",
            IntentType.protocol_deviation,
            "protocol_deviation",
        ),
        ("这个药超说明书用于儿童是否在仿单范围内？", IntentType.off_label_check, "off_label_check"),
        ("请从这段病例叙述中提取不良事件线索", IntentType.ae_extraction, "ae_extraction"),
        ("这句话有依据吗：losartan 禁用于孕妇", IntentType.citation_verification, "citation_verification"),
        ("Losacar 仿單的禁忌症有哪些？", IntentType.label_query, "label_query"),
        ("GVP Module VI 對 ICSR 的提交時限是多久？", IntentType.general_qa, None),
    ],
)
def test_skill_routing_by_vocabulary(query, expected, skill):
    intent = classify(query)
    assert intent.type is expected and intent.target_skill == skill


def test_off_label_and_ae_carry_their_risk_floor_and_short_queries_are_unclear():
    assert classify("off-label use of X in neonates?").risk is RiskLevel.high
    assert classify("extract AE signals from this narrative").risk is RiskLevel.medium
    assert classify("??").type is IntentType.unclear
    assert classify("mg").type is IntentType.unclear


@pytest.mark.parametrize(
    "query",
    [
        "我最近血压 150/95，我应该每天吃多少 losartan？",
        "我血壓高，我每天該吃多少 losartan？",
        "医生让我吃 losartan，我可以自己加量到 100 mg 吗？",
        "我想自己停药，可以吗？",
    ],
)
def test_adverbials_between_subject_modal_and_verb_do_not_defeat_the_high_risk_rule(query):
    """Found while testing the API refusal path (record 58): v1 required the modal right after 我."""
    intent = classify(query)
    assert intent.type is IntentType.high_risk and intent.risk is RiskLevel.high


@pytest.mark.parametrize(
    "query",
    [
        "說明書中 losartan 的每日最大劑量是多少？",
        "我可以用哪些關鍵詞檢索 GVP 模組？",
        "我需要查一下這份指南的生效日期",
    ],
)
def test_document_questions_in_first_person_stay_low_risk(query):
    intent = classify(query)
    assert intent.type is not IntentType.high_risk
