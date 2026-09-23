"""Rule-based safety layers, version `safety-rules-v1` (M2-09/M2-10 first slice).

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

SAFETY_VERSION = "safety-rules-v1"

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
    r"|\bsystem\s*:\s*|\bassistant\s*:\s*|<\|im_start\|>|\[INST\]",
    re.I,
)
_EVIDENCE_INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above) (?:instructions|rules)"
    r"|you are now (?:a|an|the) "
    r"|(?:as an ai|as a language model)[^.]{0,40}(?:you must|you should|always)"
    r"|忽略(?:以上|之前|前面)?(?:的)?(?:指令|指示)"
    r"|\bsystem\s*:\s*|\bassistant\s*:\s*|<\|im_start\|>|\[INST\]|BEGIN SYSTEM PROMPT",
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
