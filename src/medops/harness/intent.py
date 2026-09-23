"""Rule-based intent classification, version `intent-rules-v1` (Intent node first slice).

High-risk detection is deliberately narrow and first-person: individual dosing, diagnosis, prescription or an
acute personal emergency (INV-SAF-01). Regulatory questions that merely contain words like "emergency" stay
answerable. Skill routing keys on department vocabulary; anything else is `general_qa`. An LLM classifier
may later refine confidence, but it can never lower the risk floor enforced by the `Intent` model.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from medops.domain.common import RiskLevel
from medops.domain.intent import Entity, Intent, IntentType

INTENT_VERSION = "intent-rules-v1"

_HIGH_RISK = re.compile(
    r"我(?:该|該|应该|應該|能|可以|要|需要)(?:吃|服|用|打|注射|加|减|減)(?:多少|几|幾|什么|什麼|哪种|哪種)"
    r"|我(?:得|患|是不是得|是否患)(?:了|的)?(?:什么|什麼|啥)病"
    r"|(?:帮|幫|替)我(?:诊断|診斷|开药|開藥|开处方|開處方|调剂量|調劑量|调整剂量|調整劑量)"
    r"|(?:我|我家|家人|孩子|小孩|母亲|母親|父亲|父親|老婆|老公|太太|先生)(?:现在|現在|刚才|剛才|突然)?(?:胸痛|呼吸困难|呼吸困難|昏迷|抽搐|大出血|休克|过量|過量)"
    r"|\b(?:what|how much|which) (?:dose |medicine |drug )?should i (?:take|use|inject)\b"
    r"|\bdiagnose (?:me|my (?:symptoms|condition))\b"
    r"|\bprescribe (?:me|for me|something)\b"
    r"|\bmy (?:child|son|daughter|mother|father|wife|husband|baby) (?:has|is having|just took|swallowed)\b"
    r"|\bi (?:have|am having) (?:chest pain|trouble breathing|a seizure)\b"
    r"|\b(?:i|we) (?:took|swallowed|overdosed on) too (?:much|many)\b",
    re.I,
)
_AE_TOPIC = re.compile(
    r"不良事件|不良反應|不良反应|adverse (?:events?|reactions?|drug reactions?)|\bAEs?\b|\bSAEs?\b|\bADRs?\b", re.I
)
_AE_ACTION = re.compile(r"提取|抽取|线索|線索|识别|識別|找出|列出|extract|identify|pull out|list", re.I)
_OFF_LABEL = re.compile(
    r"超说明书|超說明書|超適應症|超适应症|off-?label|適應症外|适应症外|说明书外|說明書外|仿單外|未核准(?:的)?(?:適應症|适应症)",
    re.I,
)
_DEVIATION = re.compile(
    r"方案偏离|方案偏離|(?<![a-z])偏离|(?<![a-z])偏離|protocol deviations?|protocol violations?|\bdeviations?\b", re.I
)
_CITATION = re.compile(
    r"(?:这|這|该|該|此)(?:句话|句話|说法|說法|结论|結論|引用|陈述|陳述)(?:有|是否有|有没有|有沒有)(?:依据|依據|出处|出處|来源|來源|文献支持|文獻支持)"
    r"|核实(?:引用|出处)|核實(?:引用|出處)|引用(?:是否)?(?:正确|正確|准确|準確)"
    r"|verify (?:the |this |these )?(?:citations?|claims?|statements?|references?)"
    r"|is (?:this|the|that) (?:claim|statement|citation) (?:supported|correct|accurate)",
    re.I,
)
_LABEL = re.compile(
    r"仿單|仿单|说明书|說明書|药品标签|藥品標籤|\blabel(?:ing|s)?\b|\bSmPC\b|package insert|prescribing information"
    r"|禁忌|劑量|剂量|用法|用量|适应症|適應症|交互作用|相互作用|\bdos(?:e|age|ing)\b|contraindicat|interactions?|warnings?|precautions?",
    re.I,
)
_HAS_CONTENT = re.compile(r"[㐀-鿿A-Za-z]{2,}")


def classify(query: str, entities: Sequence[Entity] = ()) -> Intent:
    text = query.strip()
    ents = tuple(entities)
    if not _HAS_CONTENT.search(text) or len(text) < 4:
        return Intent(type=IntentType.unclear, risk=RiskLevel.low, entities=ents, confidence=0.3)
    if _HIGH_RISK.search(text):
        return Intent(type=IntentType.high_risk, risk=RiskLevel.high, entities=ents, confidence=0.9)
    if _OFF_LABEL.search(text):
        return Intent(
            type=IntentType.off_label_check,
            target_skill="off_label_check",
            risk=RiskLevel.high,
            entities=ents,
            confidence=0.7,
        )
    if _AE_TOPIC.search(text) and _AE_ACTION.search(text):
        return Intent(
            type=IntentType.ae_extraction,
            target_skill="ae_extraction",
            risk=RiskLevel.medium,
            entities=ents,
            confidence=0.7,
        )
    if _DEVIATION.search(text):
        return Intent(
            type=IntentType.protocol_deviation,
            target_skill="protocol_deviation",
            risk=RiskLevel.medium,
            entities=ents,
            confidence=0.7,
        )
    if _CITATION.search(text):
        return Intent(
            type=IntentType.citation_verification,
            target_skill="citation_verification",
            risk=RiskLevel.low,
            entities=ents,
            confidence=0.7,
        )
    if _LABEL.search(text):
        return Intent(
            type=IntentType.label_query, target_skill="label_query", risk=RiskLevel.low, entities=ents, confidence=0.6
        )
    return Intent(type=IntentType.general_qa, risk=RiskLevel.low, entities=ents, confidence=0.5)
