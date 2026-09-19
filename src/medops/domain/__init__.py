"""Domain contracts (baseline 4, M0-07). Import from here; no FastAPI, database or model SDK dependencies."""

from medops.domain.answer import Answer, Claim, Escalation
from medops.domain.common import DISCLAIMER, Dept, DocStatus, DocType, ReasonCode, RiskLevel
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.domain.intent import Entity, Intent, IntentType
from medops.domain.knowledge import Chunk, Document
from medops.domain.safety import SafetyDecision, SafetyResult
from medops.domain.state import AgentState, CandidateRef, SourceRank, TokenBudget, VersionSet
from medops.domain.verification import ElementKind, ElementSupport, Verdict, VerifyResult

__all__ = [
    "DISCLAIMER",
    "AgentState",
    "Answer",
    "CandidateRef",
    "Chunk",
    "Citation",
    "Claim",
    "Dept",
    "DocStatus",
    "DocType",
    "Document",
    "ElementKind",
    "ElementSupport",
    "Entity",
    "Escalation",
    "Evidence",
    "Intent",
    "IntentType",
    "ReasonCode",
    "RiskLevel",
    "SafetyDecision",
    "SafetyResult",
    "SourceRank",
    "TokenBudget",
    "UserContext",
    "Verdict",
    "VerifyResult",
    "VersionSet",
]
