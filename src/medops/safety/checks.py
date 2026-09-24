"""Rule-based safety layers, version `safety-rules-v2` (M2-09/M2-10; v2 adds the safety set's rules-miss input and
document injection genres and stops treating "<word> system:" in ordinary text as a delimiter, record 70).

Layer 1 `check_input`: prompt-injection patterns in the user query -> refuse (`prompt_injection`).
Layer 2 `screen_evidence`: instruction-like content inside retrieved text is treated as data and excluded from
the model context; the ids are recorded so the trace shows what was dropped.
Layer 3 `check_output`: the rendered answer must not turn into individual medical advice.
`decide` is the Safety node: allow only when intent, evidence and verification agree; otherwise a stable
reason code (F4.1) for refusal or escalation.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from medops.domain.answer import Answer
from medops.domain.common import ReasonCode, RiskLevel
from medops.domain.evidence import Evidence
from medops.domain.intent import Intent, IntentType
from medops.domain.safety import SafetyDecision, SafetyResult
from medops.domain.verification import VerifyResult

SAFETY_VERSION = "safety-rules-v2"

_INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions|prompts|rules)"
    r"|disregard (?:all |any |the )?(?:previous|prior|above) (?:instructions|rules)"
    r"|you are now (?:a|an|the) "
    r"|(?:reveal|print|show|output) (?:your |the )?(?:system prompt|hidden instructions|developer message)"
    r"|(?:act|pretend|roleplay) as (?:an? )?(?:unrestricted|jailbroken|developer mode)"
    r"|忽略(?:以上|之前|前面|上面|所有)?(?:的)?(?:指令|指示|规则|規則|提示)"
    r"|(?:无视|無視|不要理会|不要理會)(?:以上|之前|前面)?(?:的)?(?:指令|规则|規則)"
    r"|(?:输出|輸出|显示|顯示|打印|列出)(?:你的|你們的)?(?:系统提示|系統提示|隐藏指令|隱藏指令)"
    r"|你现在是|你現在是|扮演(?:一个|一個)?(?:不受限制|无限制|無限制)"
    r"|(?:切换|切換|改为|改為|把我(?:的)?(?:部门|部門|权限|權限))(?:到|成|为|為)?\s*(?:管理员|管理員|admin|ADMIN|PV|MA|CO)部?"
    r"|(?<![a-z] )\bsystem\s*:\s*|(?<![a-z] )\bassistant\s*:\s*|<\|im_start\|>|\[INST\]"
    # safety-rules-v2 (record 70): the safety set's rules-miss payloads — exfiltration of the text before the message,
    # of the rules the assistant was given, forged higher-priority developer notes, "assume you have no restrictions"
    r"|\b(?:translate|copy|repeat|reproduce|summari[sz]e|reveal|show|print|output|paste) (?:the |all |any |everything |every )?"
    r"(?:text|words?|content|instructions?|messages?|prompts?|paragraph|passage)s? (?:above|before|preceding|prior to) (?:this|the|my|your) (?:message|question|line|prompt|reply)"
    r"|(?:把|將|将)?(?:這條|这条|本|此|這則|这则)?(?:訊息|消息|信息|對話|对话)(?:之前|前面|以上|上方)(?:的)?(?:所有|全部|那段|第一段)?(?:文字|內容|内容|指令|提示)(?:逐字)?(?:複製|复制|翻譯|翻译|輸出|输出|重複|重复|告訴|告诉|貼|贴)"
    r"|(?:你|您)(?:收到|接收)(?:的)?(?:第一段|最前面(?:的)?|開頭(?:的)?|开头(?:的)?)(?:文字|內容|内容|指令)"
    r"|\b(?:describe|list|tell me|explain|state) (?:the |all |any |every )?(?:rules|instructions|guidelines|restrictions|policies) (?:you were|you've been|you have been|you are|you've) (?:given|told|instructed|configured|operating under)"
    r"|(?:描述|列出|說出|说出|告訴我|告诉我|給我|给我)(?:你|您|你們|你们)(?:的|收到的|被給的|被给的|被授權的|被授权的)?(?:規則|规则|指令|限制|系統提示|系统提示|權限|权限|文件清單|文件清单)"
    r"|(?:你|您|你們|你们)(?:被)?(?:授權|授权|允許|允许)(?:讀取|读取|存取|访问|訪問)(?:的)?(?:文件|文檔|文档|資料|资料)(?:清單|清单|列表)"
    r"|\b(?:developer|admin|administrator|system|operator) (?:note|notes|message|memo|override)s?\b[^.?!]{0,40}\b(?:overrid|priorit|precedence|supersed|higher than)"
    r"|(?:開發者|开发者|管理員|管理员|系統|系统|營運|运营)(?:備註|备注|留言|指令|訊息|消息|說明|说明)[^。？！?!]{0,16}(?:優先|优先|高於|高于|覆蓋|覆盖|凌駕|凌驾)"
    r"|\b(?:assume|pretend|imagine|suppose|act as if) (?:that )?(?:you have|there are|you've got|you had|you are under) no (?:restrictions?|limits?|department restrictions?|rules?|constraints?)"
    r"|(?:假設|假设|假如|想像|想象|當作|当作)(?:你|您)(?:沒有|没有|不受)(?:任何)?(?:部門|部门)?(?:限制|約束|约束|規則|规则)"
    r"|\b(?:echo|repeat|output|print|append|include|reproduce) (?:the |this |that )?(?:token|code|string|canary|marker|passphrase)\b"
    r"|(?:原樣|原样|逐字)(?:輸出|输出|複製|复制|重複|重复|附上|加上)",
    re.I,
)
_EVIDENCE_INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above) (?:instructions|rules)"
    r"|you are now (?:a|an|the) "
    r"|(?:as an ai|as a language model)[^.]{0,40}(?:you must|you should|always)"
    r"|忽略(?:以上|之前|前面)?(?:的)?(?:指令|指示)"
    r"|(?<![a-z] )\bsystem\s*:\s*|(?<![a-z] )\bassistant\s*:\s*|<\|im_start\|>|\[INST\]|BEGIN SYSTEM PROMPT"
    # safety-rules-v2 (record 70): instruction-like content that speaks to an automated reader, declares itself the sole
    # source, shapes the answer's form, or grants itself a role — none of which a genuine label or guideline does
    r"|\b(?:notes?|notice|instructions?|message|reminder)s? (?:for|to) (?:any |all |the )?(?:automated|ai|assistant|language model|llm|bot|automated reader|model)s?\b"
    r"|(?:僅|仅)?供(?:自動化|自动化|AI|人工智慧|人工智能)(?:助理|助手|系統|系统|模型|讀者|读者)|(?:致|給|给)(?:自動化|自动化|AI)(?:助理|助手|系統|系统|模型)"
    r"|\btreat (?:this|the following|the present) (?:paragraph|section|passage|text|clause|note) as (?:the )?(?:sole|only|single|authoritative|definitive)\b"
    r"|\b(?:this|the following) (?:paragraph|section|clause|note) (?:overrides|supersedes|replaces) (?:all|any|every)\b"
    r"|(?:本段|此段|這段|这段|以下(?:內容|内容)?|下列(?:內容|内容)?)(?:為|为|是|作為|作为)?唯一(?:有效)?(?:依據|依据|來源|来源|準則|准则|基礎|基础)"
    r"|(?:本段|此段|這段|这段)(?:優先於|优先于|覆蓋|覆盖|取代)(?:其他|所有|一切)"
    r"|\b(?:quote|repeat|echo|append|include|print|output|reproduce|copy) (?:the |this )?(?:token|code|string|phrase|marker|identifier)\b"
    r"|\b(?:begin|start|end|finish|prefix|suffix) (?:your |the |every |each )?(?:answer|reply|response)s? with\b|\brespond only with\b"
    r"|(?:回答|作答|回覆|回复|答覆|答复)(?:時|时)?(?:請|请)?(?:以|用).{0,30}?(?:開頭|开头|結尾|结尾|開始|开始|結束|结束)"
    r"|(?:將|将|把)(?:以下|下列|本|這個|这个|此)?(?:代碼|代码|字串|字符串|令牌|標記|标记|口令)(?:原樣|原样|逐字)?(?:附|加|輸出|输出|複製|复制|貼|贴|寫|写)"
    r"|(?:附|加)在(?:回答|回覆|回复|答覆|答复)(?:的)?(?:末尾|開頭|开头|結尾|结尾)|(?:先|請先|请先)(?:輸出|输出|寫出|写出|打印)(?:代碼|代码|字串|字符串|令牌)"
    r"|回答.{0,12}(?:請|请)?(?:附上|加上|帶上|带上)(?:代碼|代码|字串|字符串|令牌|[A-Z]{3,}-)"
    r"|\bact as (?:an? )?(?:administrator|admin|developer|system)\b|\badministrator directive\b|\b(?:do not|don't) (?:display|show|reveal) this (?:note|paragraph|text|message)\b"
    r"|你現在是|你现在是|(?:切換|切换|改為|改为|提升)(?:到|成|為|为)?\s*(?:管理員|管理员|admin)|(?:所有|全部)(?:劑量|剂量)?上限(?:改為|改为|設為|设为|改成)(?:無限制|无限制|不限)"
    r"|\b(?:disregard|bypass) the (?:department|access|permission) restrictions?\b",
    re.I,
)
_ADVICE = re.compile(
    r"您(?:应该|應該|应|應|可以|需要)(?:每天|每日|立即)?(?:服用|使用|注射|加量|减量|減量|停药|停藥)"
    r"|建议您(?:每天|每日)?(?:服用|使用|注射)"
    r"|建議您(?:每天|每日)?(?:服用|使用|注射)"
    r"|(?:you should|i recommend (?:that )?you|you need to) (?:take|use|inject|stop taking|increase|reduce)"
    r"|(?:your|for you,? the) (?:dose|dosage) (?:should be|is)",
    re.I,
)


def check_input(query: str) -> SafetyResult:
    if _INJECTION.search(query):
        return SafetyResult(
            decision=SafetyDecision.refuse,
            reason_codes=(ReasonCode.prompt_injection,),
            detail="user input matches an instruction-override pattern (layer 1)",
            checker_version=SAFETY_VERSION,
        )
    return SafetyResult(decision=SafetyDecision.allow, checker_version=SAFETY_VERSION)


def screen_evidence(evidence: Sequence[Evidence]) -> tuple[tuple[Evidence, ...], tuple[str, ...]]:
    kept: list[Evidence] = []
    flagged: list[str] = []
    for e in evidence:
        if _EVIDENCE_INJECTION.search(e.text):
            flagged.append(e.citation.chunk_id)
        else:
            kept.append(e)
    return tuple(kept), tuple(flagged)


def check_output_text(texts: Sequence[str], *, off_label: bool = False) -> SafetyResult:
    """Layer 3 on any rendered output (harness answers and Skill outputs alike): individual medical advice is
    refused; off-label checks report document scope only (M2-14)."""
    text = " ".join(texts)
    if _ADVICE.search(text):
        detail = (
            "off-label checks report document scope only, never a recommendation (M2-14)"
            if off_label
            else "rendered answer reads as individual medical advice (layer 3)"
        )
        return SafetyResult(
            decision=SafetyDecision.refuse,
            reason_codes=(ReasonCode.high_risk_medical,),
            detail=detail,
            checker_version=SAFETY_VERSION,
        )
    return SafetyResult(decision=SafetyDecision.allow, checker_version=SAFETY_VERSION)


def check_output(answer: Answer, intent: Intent) -> SafetyResult:
    return check_output_text([c.text for c in answer.claims], off_label=intent.type is IntentType.off_label_check)


def decide(
    intent: Intent,
    verify_result: VerifyResult | None,
    evidence: Sequence[Evidence],
    flagged_evidence: Sequence[str],
) -> SafetyResult:
    """The Safety node decision before Answer (baseline 5.3 order Intent -> Retrieve -> Verify -> Safety)."""
    if intent.type is IntentType.high_risk or (intent.risk is RiskLevel.high and intent.type is IntentType.unclear):
        return SafetyResult(
            decision=SafetyDecision.escalate,
            reason_codes=(ReasonCode.high_risk_medical,),
            detail="high-risk medical intent is refused and escalated (INV-SAF-01)",
            checker_version=SAFETY_VERSION,
        )
    if not evidence:
        codes = (ReasonCode.prompt_injection,) if flagged_evidence else (ReasonCode.insufficient_evidence,)
        return SafetyResult(
            decision=SafetyDecision.escalate,
            reason_codes=codes,
            detail="no usable evidence after screening" if flagged_evidence else "no verified evidence",
            checker_version=SAFETY_VERSION,
        )
    if verify_result is None or not verify_result.structural_ok:
        return SafetyResult(
            decision=SafetyDecision.escalate,
            reason_codes=(ReasonCode.insufficient_evidence,),
            detail="evidence did not pass the structural check",
            checker_version=SAFETY_VERSION,
        )
    return SafetyResult(decision=SafetyDecision.allow, checker_version=SAFETY_VERSION)
