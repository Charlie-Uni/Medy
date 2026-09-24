"""Rule-based intent classification, version `intent-rules-v3` (v1: Intent node first slice; v2: adverbials between
subject, modal and verb no longer defeat the first-person high-risk rule, record 58; v3: third-person patients, personal
situations wrapped as lookups, emergencies and diagnosis questions from the safety set, record 70).

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

INTENT_VERSION = "intent-rules-v3"

# intent-rules-v3 (record 70): the safety set's 13 paraphrases that v2 missed — digits between the subject and the
# modal, third-person patients and family members, a personal situation wrapped as a document lookup, acute personal
# emergencies phrased as "what do I do", and personal diagnosis questions. Every alternative keeps an individual marker
# (我 / a family member / a specific patient) so population-level document questions stay answerable; the main set's
# 614 queries and the safety set's other classes are the false-positive regression (evals/safety_set/tools/intent_sweep.py).
_FAMILY = (
    r"(?:我媽|我妈|我爸|我爺|我爷|我奶|我外婆|我外公|我家(?:的)?(?:老人|小孩|孩子|寶寶|宝宝)?|家[裡里](?:的)?(?:老人|小孩|孩子)?"
    r"|家人|孩子|小孩|母[親亲]|父[親亲]|老婆|老公|太太|先生|爺爺|爷爷|奶奶|阿嬤|阿公|我(?:的)?(?:病人|患者)|這位|这位"
    r"|(?<!其)(?:她|他)(?!人|們|们|方|們的))"
)
_ZH_MODAL = r"(?:该|該|应该|應該|应|應|能|能不能|可以|可不可以|可否|要|要不要|需要|需不需要|想|该不该|該不該|是否)"
_ZH_DOSE_VERB = r"(?:吃|服用|服|用|打|注射|加|减|減|停|换|換|改)"
_ZH_DOSE_OBJ = r"(?:量|药|藥|多少|几|幾|什么|什麼|哪种|哪種|半|倍|[到至成为為]\s*\d)"
_NB = r"[^，。？！,.?!；;]"  # stays inside one clause
_HIGH_RISK_ALTERNATIVES = (
    # first person: subject … modal … dose verb + object (digits / units between subject and modal are tolerated)
    r"我" + _NB + r"{0,14}?" + _ZH_MODAL + _NB + r"{0,6}?" + _ZH_DOSE_VERB + _ZH_DOSE_OBJ,
    r"我(?:得|患|是不是得|是否患)(?:了|的)?(?:什么|什麼|啥)病",
    r"(?:帮|幫|替)我(?:诊断|診斷|开药|開藥|开处方|開處方|开个?处方|開個?處方|调剂量|調劑量|调整剂量|調整劑量)",
    # a personal situation wrapped as a lookup: 像我這樣 … 要不要減半
    r"(?:像我(?:這樣|这样|這種|这种)|我(?:這種|这种|這樣|这样|的)(?:情況|情况|狀況|状况|體重|体重|年紀|年纪|腎|肾|肝))[^。？！?!]{0,30}"
    + _ZH_MODAL
    + r"[^。？！?!]{0,8}"
    + _ZH_DOSE_VERB,
    # a specific third person: dose change, co-medication, how many
    _FAMILY
    + r"[^。？！?!]{0,40}(?:[减減]半|加倍|加量|[减減]量|停[药藥]|换[药藥]|換[药藥]|一起吃|合用|併用|并用|同[時时]吃"
    + r"|一天(?:各)?[吃服][几幾]|每天(?:各)?[吃服][几幾]|[吃服][几幾][顆颗粒片])",
    r"(?:建[议議]|[给給])(?:(?<!其)(?:她|他)(?!人|們|们|方)|這位|这位|我(?:的)?(?:病人|患者|媽|妈|爸))[^。？！?!]{0,12}"
    r"(?:[减減]半|加倍|加量|[减減]量|停[药藥]|改成|換成|换成)",
    # acute personal emergency / overdose, first person or a family member
    _FAMILY
    + r"[^。？！?!]{0,12}(?:现在|現在|刚才|剛才|突然|昨晚|今天)?[^。？！?!]{0,8}"
    + r"(?:胸痛|呼吸困难|呼吸困難|昏迷|抽搐|大出血|休克|过量|過量|誤吞|误吞|吞了|吃了(?:兩|两|三|太多|一整|過量|过量|多))",
    r"我(?:现在|現在|刚才|剛才|突然|昨晚|今天)?"
    + _NB
    + r"{0,6}(?:胸痛|呼吸困难|呼吸困難|昏迷|抽搐|大出血|休克|过量|過量|誤吞|误吞|吃多了|吃錯|吃错)",
    r"(?:该怎么办|該怎麼辦|怎么处理|怎麼處理|要不要催吐|要不要去急[诊診]|要不要看医生|要不要看醫生|要不要就[医醫]|需要去急[诊診]|我要去急[诊診])",
    # personal diagnosis: my symptom / my result … is it (a disease / normal / serious)
    r"我(?:的)?"
    + _NB
    + r"{0,10}(?:症状|症狀|皮疹|心悸|頭痛|头痛|檢查|检查|報告|报告|心電圖|心电图|數值|数值|指標|指标|反應|反应)"
    + _NB
    + r"{0,10}(?:算不算|是不是|是否|算)(?:有病|正常|異常|异常|嚴重|严重|過敏|过敏|中毒|嚴重不良反應|严重不良反应)",
    r"我(?:這|这)是" + _NB + r"{0,8}(?:過敏|过敏|中毒|發作|发作|副作用|不良反應|不良反应)(?:嗎|吗)",
    r"我" + _NB + r"{0,10}(?:是不是|算不算)(?:得了|患了|有)" + _NB + r"{0,8}(?:病|症|炎|癌)",
    # english
    r"\b(?:what|how much|how many|which) (?:dose |medicine |drug |tablets? |pills? )?should i (?:take|use|inject|stop|skip)\b",
    r"\bshould i (?:stop|start|continue|skip|double|halve|take|increase|reduce) (?:the |my |this )?(?:drug|dose|medication|medicine|tablets?|pills?|treatment)\b",
    r"\b(?:is it|would it be) (?:safe|ok|okay|alright) for me (?:personally )?to (?:take|double|halve|stop|skip|increase|reduce|combine)\b",
    r"\bcan i (?:safely )?(?:take|double|halve|stop|skip|increase|reduce|combine) (?:my|the|this|these|both)\b",
    r"\bdiagnose (?:me|my (?:symptoms|condition))\b",
    r"\bprescribe (?:me|for me|something)\b",
    r"\bmy (?:child|son|daughter|mother|father|wife|husband|baby|grandmother|grandfather|patient) (?:has|is having|just took|swallowed|took)\b",
    r"\b(?:my|this|the) (?:grandmother|grandfather|mother|father|patient|participant|subject)(?:'s)?\b.{0,90}?"
    r"\b(?:safer|safe|enough|too much|too high|too low) for (?:her|him|them)\b",
    r"\b(?:this|my|the) (?:frail |elderly |old )?(?:patient|participant|subject) (?:needs|should get|should receive|can have|should take) "
    r"(?:half|less|more|a lower dose|a higher dose|double|\d)",
    r"\bi (?:have|am having) (?:chest pain|trouble breathing|a seizure)\b",
    r"\b(?:i|we) (?:took|swallowed|overdosed on) too (?:much|many)\b",
    r"\bwhat do i do\b",
)
_HIGH_RISK = re.compile("|".join(_HIGH_RISK_ALTERNATIVES), re.I)
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
