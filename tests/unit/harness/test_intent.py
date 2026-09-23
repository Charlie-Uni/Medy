"""intent-rules-v1: narrow first-person high-risk detection, department skill routing, unclear queries."""

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
